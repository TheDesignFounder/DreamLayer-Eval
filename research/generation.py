"""Configurable ComfyUI workflow execution; uncertain submissions are never repeated."""

from __future__ import annotations

import copy
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from .contracts import digest, record, redact
from .experiments import managed_asset
from .store import Store
from .types import JsonObject, PathLike


def resolve_workflow(
    generation: JsonObject, prompt: JsonObject, parameters: JsonObject
) -> tuple[JsonObject, JsonObject, JsonObject]:
    "Bind declared parameters and report values absent from the workflow bindings."
    workflow = copy.deepcopy(generation["workflow"])
    bindings = generation.get("bindings", {})
    supplied = {
        "prompt": prompt["text"],
        "negative_prompt": prompt.get("negative_prompt", ""),
        **parameters,
    }
    accepted, unsupported = {}, {}
    for name, value in supplied.items():
        if name not in bindings:
            unsupported[name] = value
            continue
        targets = bindings[name]
        if not isinstance(targets, list) or not targets:
            raise ValueError("Parameter binding must list node/input pairs")
        for node, input_name in targets:
            workflow[str(node)]["inputs"][input_name] = value
        accepted[name] = value
    return workflow, accepted, unsupported


def generate(
    store: Store,
    eid: str,
    trial: JsonObject,
    prompt: JsonObject,
    media_root: PathLike,
    retry: bool = False,
    transport: Any = requests,
) -> JsonObject:
    "Submit or reconcile one local ComfyUI trial while preserving delivery uncertainty."
    generation = trial["generation"]
    attempts = store.list("attempt", eid, trial_id=trial["id"])
    completed = [a for a in attempts if a["status"] == "success"]
    if completed:
        return completed[-1]
    submitted = [a for a in attempts if a.get("provider_request_id") and a["status"] == "started"]
    if attempts and not submitted and not retry:
        return attempts[-1]  # Unknown delivery/failure requires explicit retry command.
    if not generation.get("allow_provider_calls", False):
        return store.put(
            record(
                "attempt",
                eid,
                trial_id=trial["id"],
                attempt_index=len(attempts),
                status="rejected",
                reason="Generation disabled in config; imported-media execution is available",
                provider_request_id=None,
                retry_of=None,
            )
        )
    base = generation.get("base_url", "http://127.0.0.1:8188").rstrip("/")
    if urlparse(base).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("ComfyUI workflow adapter requires a local endpoint")
    workflow, submitted_parameters, unsupported = resolve_workflow(
        generation, prompt, trial["requested_parameters"]
    )
    job = submitted[-1]["provider_request_id"] if submitted else None
    attempt_index = max([a.get("attempt_index", 0) for a in attempts], default=-1) + (
        0 if submitted else 1
    )
    claim = digest([trial["id"], "generation", attempt_index])
    metadata = {
        "trial_id": trial["id"],
        "attempt_index": attempt_index,
        "retry_of": attempts[-1]["id"] if retry and attempts else None,
        "provider_identity": generation.get(
            "identity", {"provider": "ComfyUI", "model": None, "endpoint": base, "version": None}
        ),
        "workflow_hash": digest(redact(workflow)),
        "workflow": redact(workflow),
        "requested_parameters": trial["requested_parameters"],
        "submitted_parameters": submitted_parameters,
        "supported_parameters": list(generation.get("bindings", {})),
        "unsupported_parameters": unsupported,
        "accepted_parameters": {},
        "unverified_parameters": submitted_parameters,
    }
    try:
        if not job:
            if not store.claim(claim):
                return store.put(
                    record(
                        "attempt",
                        eid,
                        **metadata,
                        status="unknown",
                        provider_request_id=None,
                        reason="Submission already claimed; reconcile ComfyUI queue before explicit retry",
                    )
                )
            store.put(
                record("attempt", eid, **metadata, status="started", provider_request_id=None)
            )
            response = transport.post(
                base + "/prompt", json={"prompt": workflow, "client_id": claim}, timeout=30
            )
            response.raise_for_status()
            body = response.json()
            if not body.get("prompt_id"):
                raise ValueError("ComfyUI rejected workflow: " + str(redact(body)))
            job = body["prompt_id"]
            store.put(
                record(
                    "attempt",
                    eid,
                    **metadata,
                    status="started",
                    provider_request_id=job,
                    phase="submitted",
                )
            )
        deadline = time.monotonic() + min(generation.get("timeout_seconds", 300), 3600)
        while time.monotonic() < deadline:
            if store.job(eid)["cancel"]:
                return store.put(
                    record(
                        "attempt",
                        eid,
                        **metadata,
                        status="cancelled",
                        provider_request_id=job,
                        reason="Local polling cancelled; queued provider work may still finish",
                    )
                )
            response = transport.get(base + "/history/" + job, timeout=30)
            response.raise_for_status()
            entry = response.json().get(job)
            if entry:
                if entry.get("status", {}).get("status_str") == "error":
                    raise ValueError(
                        "ComfyUI execution failed: " + str(redact(entry.get("status")))
                    )
                outputs = [
                    item
                    for node in entry.get("outputs", {}).values()
                    for kind in ("images", "gifs", "videos")
                    for item in node.get(kind, [])
                ]
                if not outputs:
                    raise ValueError("Workflow completed without image/video outputs")
                for output in outputs:
                    downloaded = transport.get(
                        base + "/view",
                        params={
                            k: output[k] for k in ("filename", "subfolder", "type") if k in output
                        },
                        timeout=60,
                    )
                    downloaded.raise_for_status()
                    staging = (
                        Path(media_root) / "staging" / trial["id"] / Path(output["filename"]).name
                    )
                    staging.parent.mkdir(parents=True, exist_ok=True)
                    staging.write_bytes(downloaded.content)
                    asset = managed_asset(staging, media_root)
                    asset_id = digest([trial["id"], asset["sha256"]])
                    if any(a["id"] == asset_id for a in store.list("asset", eid)):
                        continue
                    store.put(
                        record(
                            "asset",
                            eid,
                            **asset,
                            id=asset_id,
                            trial_id=trial["id"],
                            provider_identity=metadata["provider_identity"],
                            parent_asset_id=None,
                            transformations=[],
                            generation_timestamp=None,
                        )
                    )
                return store.put(
                    record(
                        "attempt",
                        eid,
                        **metadata,
                        status="success",
                        provider_request_id=job,
                        raw_provider_response=redact(entry),
                        provider_prompt_rewrite=None,
                    )
                )
            time.sleep(min(generation.get("poll_seconds", 1), 10))
        return store.put(
            record(
                "attempt",
                eid,
                **metadata,
                status="interrupted",
                provider_request_id=job,
                reason="Polling deadline; resume by job ID",
            )
        )
    except requests.Timeout:
        return store.put(
            record(
                "attempt",
                eid,
                **metadata,
                status="unknown",
                provider_request_id=job,
                reason="Timeout; delivery unknown; no automatic paid resubmission",
            )
        )
    except (requests.RequestException, ValueError, KeyError) as exc:
        return store.put(
            record(
                "attempt",
                eid,
                **metadata,
                status="failed",
                provider_request_id=job,
                reason=str(exc),
            )
        )
