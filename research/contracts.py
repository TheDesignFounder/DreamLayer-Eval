"""Portable identities and strict, JSON-safe research records."""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from .types import JsonObject, PathLike

SCHEMA_VERSION = 1
STATUSES = {
    "success",
    "not_applicable",
    "insufficient_data",
    "unavailable_dependency",
    "failed_evaluation",
    "abstention",
    "invalid_legacy_result",
}
KINDS = {
    "experiment",
    "prompt",
    "trial",
    "attempt",
    "asset",
    "result",
    "assignment",
    "annotation",
    "analysis",
    "judge_call",
    "judge_reconciliation",
    "historical_ranking",
    "legacy",
}
SECRET = re.compile(
    r"^(?:authorization|api[-_]?key|.*_api_key|access_token|refresh_token|password|secret|headers|credential.*)$",
    re.I,
)


def now() -> str:
    "Return an ISO-8601 timestamp in UTC."
    return datetime.now(UTC).isoformat()


def canonical(value: Any) -> str:
    "Encode deterministic JSON and reject nonfinite floating-point values."
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(value: Any) -> str:
    "Hash the canonical JSON representation with SHA-256."
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path: PathLike) -> str:
    "Hash a local file in bounded-memory chunks."
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def redact(value: Any) -> Any:
    "Recursively replace credential fields and recognizable bearer tokens."
    if isinstance(value, dict):
        return {
            str(k): "[REDACTED]" if SECRET.match(str(k)) else redact(v) for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return re.sub(r"(?i)(bearer\s+|sk-)[A-Za-z0-9_.-]{8,}", "[REDACTED]", value)
    return value


def record(kind: str, experiment_id: str | None = None, **data: Any) -> JsonObject:
    "Construct and validate a timestamped, redacted schema-1 record."
    item = {
        "schema_version": SCHEMA_VERSION,
        "id": str(uuid.uuid4()),
        "kind": kind,
        "experiment_id": experiment_id,
        "created_at": now(),
        **redact(data),
    }
    validate(item)
    return item


def validate(item: JsonObject) -> JsonObject:
    "Validate record semantics and return the original object without mutation."
    canonical(item)  # Reject nonfinite values recursively before they reach SQLite/API.
    if item.get("schema_version") != SCHEMA_VERSION or item.get("kind") not in KINDS:
        raise ValueError("Unsupported record kind or schema version")
    if not isinstance(item.get("id"), str) or not item["id"]:
        raise ValueError("A stable record ID is required")
    kind = item["kind"]
    required = {
        "experiment": ["config", "config_hash"],
        "prompt": ["text", "group_id", "split"],
        "trial": ["prompt_id", "repeat_index", "model"],
        "attempt": ["trial_id", "status"],
        "asset": ["sha256", "locator", "original_filename", "media"],
        "result": [
            "metric_id",
            "metric_version",
            "scope",
            "status",
            "score",
            "membership_hash",
            "implementation",
            "weights",
            "preprocessing_hash",
            "units",
            "direction",
            "elapsed_ms",
        ],
        "assignment": ["rater_id", "asset_ids", "rubric", "seed", "mode"],
        "annotation": ["assignment_id", "rater_id", "labels", "rubric_hash"],
        "analysis": ["config", "output"],
        "judge_reconciliation": ["request_record_id", "resolution", "note"],
        "historical_ranking": [
            "source_sha256",
            "source_row",
            "original",
            "numeric_score",
            "asset_id",
        ],
    }.get(kind, [])
    for field in required:
        if field not in item:
            raise ValueError(f"{kind}: missing {field}")
    if kind == "experiment" and digest(item["config"]) != item["config_hash"]:
        raise ValueError("Experiment config hash mismatch")
    if kind == "prompt" and item["split"] not in {"train", "development", "test", "exploratory"}:
        raise ValueError("Invalid split")
    if kind == "asset" and not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
        raise ValueError("Asset identity must be a SHA-256 digest")
    if kind == "result":
        if item["status"] not in STATUSES:
            raise ValueError("Invalid result status")
        if item["scope"] not in {"image", "video", "criterion", "pair", "dataset"}:
            raise ValueError("Invalid result scope")
        score = item["score"]
        if score is not None and (
            isinstance(score, bool)
            or not isinstance(score, (float, int))
            or not math.isfinite(score)
        ):
            raise ValueError("Scores must be finite numbers or null")
        if item["status"] != "success" and score is not None:
            raise ValueError("An unsuccessful evaluation cannot have a score")
        if item["status"] != "success" and not item.get("reason"):
            raise ValueError("Unsuccessful results require a reason")
        if (
            item["status"] == "success"
            and score is None
            and item.get("special_value") != "positive_infinity"
        ):
            raise ValueError(
                "Successful numeric results require a score or documented positive infinity"
            )
        if item["metric_id"] in {"fid", "fvd"} and item["scope"] != "dataset":
            raise ValueError("FID/FVD are dataset-level results")
    if kind == "attempt" and item["status"] not in {
        "started",
        "success",
        "failed",
        "rejected",
        "interrupted",
        "cancelled",
        "unknown",
    }:
        raise ValueError("Invalid generation status")
    if kind == "annotation":
        allowed = {"pass", "fail", "uncertain", "not_applicable", "A", "B", "tie"}
        if not item["labels"] or any(v not in allowed for v in item["labels"].values()):
            raise ValueError("Invalid annotation label")
        for interval in item.get("intervals", []):
            if len(interval) != 2 or not 0 <= interval[0] <= interval[1]:
                raise ValueError("Invalid failure interval")
        rating = item.get("aesthetic_rating")
        if rating is not None and (
            isinstance(rating, bool) or not isinstance(rating, int) or not 1 <= rating <= 5
        ):
            raise ValueError("Ordinal aesthetic rating must be 1–5 or null")
    return item


def membership(assets: Sequence[JsonObject | PathLike]) -> str:
    """Order-independent set identity; repeated bytes are not independent samples."""
    hashes = [a["sha256"] if isinstance(a, dict) else file_hash(a) for a in assets]
    if len(hashes) != len(set(hashes)):
        raise ValueError("Duplicate content in dataset membership")
    return digest(sorted(hashes))
