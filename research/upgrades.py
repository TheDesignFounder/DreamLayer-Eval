"""Explicit evaluator upgrades preserve previous evidence and avoid surprise work."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence

from .analysis import current_results
from .contracts import digest, membership
from .metrics import REGISTRY, evaluator_config
from .store import Store
from .types import JsonObject

RETRYABLE_STATUSES = {"failed_evaluation", "unavailable_dependency"}


class UpgradeRefused(ValueError):
    """An unsuccessful evaluator upgrade must not replace recorded success."""


def _legacy_owner(store, result, configured, cache):
    """Identify one frozen configuration, without guessing between equal weights."""
    candidates = {digest(m): m for m in configured if m["id"] == result["metric_id"]}
    explicit = result.get("configured_metric_hash")
    if explicit is not None:
        return explicit, set()
    if len(candidates) == 1:
        return next(iter(candidates)), set()
    matches = set()
    for identity, metric in candidates.items():
        key = (identity, result.get("trial_id"))
        if key not in cache:
            settings = {k: v for k, v in metric.items() if k != "id"}
            if metric["id"] == "object_criteria" and result.get("trial_id"):
                trial = store.get(result["trial_id"])
                prompt = store.get(trial["prompt_id"])
                settings.setdefault("criteria", prompt["criteria"])
            cache[key] = {"settings": settings, "hashes": {digest(settings)}}
        if result["preprocessing_hash"] in cache[key]["hashes"]:
            matches.add(identity)
    if len(matches) == 1:
        return next(iter(matches)), set()
    if matches:
        return None, matches
    # A frozen weight locator uniquely identifies the configuration when only
    # one configured evaluator uses it, even if the file is now unavailable.
    same_weights = {
        identity for identity, m in candidates.items() if m.get("weights") == result.get("weights")
    }
    if len(same_weights) == 1:
        return next(iter(same_weights)), set()
    possible = same_weights or set(candidates)
    recorded_sha = result.get("details", {}).get("detector", {}).get("weights_sha256")
    for identity in possible:
        cached = cache[(identity, result.get("trial_id"))]
        settings = cached["settings"]
        if "normalized" not in cached:
            try:
                cached["normalized"] = evaluator_config(result["metric_id"], settings)
            except OSError:
                cached["normalized"] = settings
        variants = [settings, cached["normalized"]]
        if (
            settings.get("weights")
            and isinstance(recorded_sha, str)
            and re.fullmatch("[0-9a-f]{64}", recorded_sha)
        ):
            variants += [{**v, "weights_sha256": recorded_sha} for v in variants]
        if result["preprocessing_hash"] in {digest(v) for v in variants}:
            matches.add(identity)
    return (next(iter(matches)), set()) if len(matches) == 1 else (None, matches or possible)


def warnings(
    store: Store, eid: str, upgrade: bool = False, rerun_failed: bool = False
) -> list[JsonObject]:
    "Describe version changes and unresolved legacy configuration provenance."
    configured = store.get(eid)["config"].get("metrics", [])
    ids = {m["id"] for m in configured}
    results = [r for r in current_results(store.list("result", eid)) if r["metric_id"] in ids]
    groups = Counter(
        (r["metric_id"], r["metric_version"])
        for r in results
        if r["metric_version"] != REGISTRY[r["metric_id"]]["version"]
    )
    output = [
        {
            "kind": "evaluator_version_change",
            "metric_id": metric,
            "recorded_version": version,
            "available_version": REGISTRY[metric]["version"],
            "recorded_results": count,
            "action": "reevaluate_and_supersede"
            if upgrade
            else "retry_failed_units"
            if rerun_failed
            else "preserve_recorded_results",
            "message": f"{metric} {version} → {REGISTRY[metric]['version']}: "
            + (
                "explicit upgrade will re-evaluate matched units and retain superseded records; "
                "it will not replace successful results with unavailable or failed evaluations, "
                "and stops with an error if such an upgrade cannot run"
                if upgrade
                else "rerun-failed uses the available version only for matched units whose prior results are all failed/unavailable; other units are preserved"
                if rerun_failed
                else "resume preserves existing results; use --upgrade-evaluators to re-evaluate, or --rerun-failed for units with only failed/unavailable results"
            ),
        }
        for (metric, version), count in sorted(groups.items())
    ]
    cache = {}
    for result in results:
        owner, possible = _legacy_owner(store, result, configured, cache)
        if owner is None:
            output.append(
                {
                    "kind": "unresolved_legacy_metric_settings",
                    "metric_id": result["metric_id"],
                    "record_id": result["id"],
                    "possible_configuration_hashes": sorted(possible),
                    "action": "preserve_unresolved_units",
                    "message": f"{result['metric_id']}: legacy settings cannot be uniquely matched for record {result['id']}; affected units are preserved without re-evaluation, including with retry/upgrade flags. Inspect the legacy provenance or create a new experiment.",
                }
            )
    return output


def previous_results(
    store: Store,
    eid: str,
    metric: JsonObject,
    assets: Sequence[JsonObject],
    references: Sequence[JsonObject],
    trial_id: str | None = None,
    model: str | None = None,
    configured: Sequence[JsonObject] | None = None,
) -> list[JsonObject] | None:
    """Return matched prior rows, or None if this unit has ambiguous provenance."""
    if configured is None:
        configured = store.get(eid)["config"].get("metrics", [])
    config_hash = digest(metric)
    members = membership(assets)
    reference_hash = membership(references) if references else None
    candidates = [
        r
        for r in current_results(
            store.list("result", eid, metric_id=metric["id"], trial_id=trial_id, model=model)
        )
        if r["metric_id"] == metric["id"]
        and r.get("trial_id") == trial_id
        and r.get("model") == model
        and r["membership_hash"] == members
        and r.get("reference_hash") == reference_hash
    ]
    matched = []
    cache = {}
    for result in candidates:
        owner, possible = _legacy_owner(store, result, configured, cache)
        if owner == config_hash:
            matched.append(result)
        elif owner is None and config_hash in possible:
            return None
    return matched


def retry_failed_unit(prior: Sequence[JsonObject] | None, rerun_failed: bool) -> bool:
    "Allow explicit recovery only when every matched current result is retryable."
    return bool(rerun_failed and prior and all(r["status"] in RETRYABLE_STATUSES for r in prior))


def should_preserve(
    prior: Sequence[JsonObject] | None, metric_id: str, upgrade: bool, rerun_failed: bool = False
) -> bool:
    "Protect old or ambiguous evidence unless a supported retry or upgrade is explicit."
    # Changed weights within the same evaluator version remain a distinct identity.
    if prior is None:
        return True
    return bool(
        prior
        and not upgrade
        and not retry_failed_unit(prior, rerun_failed)
        and all(r["metric_version"] != REGISTRY[metric_id]["version"] for r in prior)
    )


def has_upgrade(prior: Sequence[JsonObject], metric_id: str) -> bool:
    "Detect whether matched results use a different evaluator version."
    return any(r["metric_version"] != REGISTRY[metric_id]["version"] for r in prior)


def annotate(
    output: JsonObject,
    metric: JsonObject,
    prior: Sequence[JsonObject],
    upgrade: bool,
    rerun_failed: bool = False,
) -> JsonObject:
    "Attach frozen configuration identity and auditable supersession links to a result."
    output["configured_metric_hash"] = digest(metric)
    if (upgrade or retry_failed_unit(prior, rerun_failed)) and has_upgrade(prior, metric["id"]):
        if output["status"] in RETRYABLE_STATUSES and any(r["status"] == "success" for r in prior):
            # This guard runs before cache insertion for both per-asset and dataset
            # evaluators. Import checks alone cannot detect missing/corrupt weights
            # or model-loading failures. Keep the recorded success and its cache.
            raise UpgradeRefused(
                f"Evaluator upgrade for {metric['id']} to {output['metric_version']} was not "
                f"applied ({output['status']}: {output.get('reason') or 'Evaluator could not run'}). "
                "Successful recorded results remain current. Fix the evaluator environment "
                "or weights, then rerun with --upgrade-evaluators."
            )
        output.update(
            supersedes=prior[-1]["id"],
            supersedes_ids=[r["id"] for r in prior],
            evaluation_attempt=max(r.get("evaluation_attempt", 1) for r in prior) + 1,
            upgrade_reason="Explicit evaluator upgrade"
            if upgrade
            else "Explicit retry of failed/unavailable evaluations using the available evaluator version",
            prior_evaluator_versions=sorted({r["metric_version"] for r in prior}),
        )
    return output
