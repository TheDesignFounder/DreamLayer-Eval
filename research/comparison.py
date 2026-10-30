"""Join experiment evidence by identity, preserving rubric, rater and missingness."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from .analysis import agreement, binary_errors, cluster_interval, correlations, current_results
from .contracts import digest
from .labels import select_annotations
from .store import Store
from .types import JsonObject


def final_assessments(store: Store, eid: str) -> list[tuple[JsonObject, JsonObject | None]]:
    "Select the last request and response for each protocol round."
    calls = store.list("judge_call", eid)
    requests = [c for c in calls if c.get("phase") == "request"]
    responses = {c["request_record_id"]: c for c in calls if c.get("phase") == "response"}
    latest = {}
    for request in requests:
        latest[request["protocol_key"]] = request
    return [(request, responses.get(request["id"])) for request in latest.values()]


def joined_rows(
    store: Store, eid: str, label_view: str = "raw", filters: Mapping[str, Any] | None = None
) -> JsonObject:
    "Join current metrics, judge verdicts and human labels by exact evidence units."
    filters = filters or {}
    allowed = {
        "prompt_id",
        "group_id",
        "repeat_index",
        "split",
        "category",
        "model",
        "rater_id",
        "criterion",
        "rubric_hash",
        "mode",
        "metric_id",
        "metric_version",
        "preprocessing_hash",
        "reference_hash",
        "selector_id",
        "judge_provider",
        "judge_model",
        "judge_config_hash",
        "judge_rubric_hash",
        "match_status",
        "synthetic",
        "operator_reconciled",
    }
    if set(filters) - allowed:
        raise ValueError("Unknown comparison filters: " + ", ".join(sorted(set(filters) - allowed)))
    assets = {a["id"]: a for a in store.list("asset", eid)}
    trials = {t["id"]: t for t in store.list("trial", eid)}
    prompts = {p["id"]: p for p in store.list("prompt", eid)}
    assignments = {a["id"]: a for a in store.list("assignment", eid)}
    annotations, warnings = select_annotations(store, eid, label_view)
    warnings.extend(
        r
        for r in store.list("judge_reconciliation", eid)
        if r.get("resolution") == "legacy_content_key_collision"
    )
    metrics = defaultdict(list)
    for result in current_results(store.list("result", eid)):
        if result["scope"] == "dataset":
            continue
        for aid in result.get("asset_ids", []):
            metrics[aid].append(result)
    judges = defaultdict(list)
    for request, response in final_assessments(store, eid):
        judges[tuple(sorted(request["order_mapping"].values()))].append((request, response))
    metric_rows, judge_rows = [], []
    for annotation in annotations:
        assignment = assignments[annotation["assignment_id"]]
        unit = tuple(sorted(assignment["asset_ids"]))
        asset = assets[unit[0]]
        trial = trials[asset["trial_id"]]
        prompt = prompts[trial["prompt_id"]]
        for criterion, human in annotation["labels"].items():
            if human in {"A", "B"}:
                human = assignment["asset_ids"][0 if human == "A" else 1]
            base = {
                "experiment_id": eid,
                "prompt_id": prompt["id"],
                "group_id": prompt["group_id"],
                "repeat_index": trial["repeat_index"],
                "split": prompt["split"],
                "category": prompt.get("category", "unspecified"),
                "model": trial["model"],
                "asset_ids": list(unit),
                "trial_id": trial["id"],
                "rater_id": annotation["rater_id"],
                "criterion": criterion,
                "rubric_hash": annotation["rubric_hash"],
                "human": human,
                "annotation_id": annotation["id"],
                "adjudication_id": annotation.get("adjudication_id"),
                "label_view": label_view,
                "source_annotation_ids": annotation.get(
                    "source_annotation_ids", [annotation["id"]]
                ),
                "mode": assignment["mode"],
            }
            if any(base.get(key) != value for key, value in filters.items() if key in base):
                continue
            if len(unit) == 1:
                for result in metrics[unit[0]]:
                    row = {
                        **base,
                        "row_type": "metric_human",
                        "asset_id": unit[0],
                        "result_id": result["id"],
                        "metric_id": result["metric_id"],
                        "metric_version": result["metric_version"],
                        "preprocessing_hash": result["preprocessing_hash"],
                        "reference_hash": result.get("reference_hash"),
                        "direction": result["direction"],
                        "status": result["status"],
                        "score": result["score"] if result["status"] == "success" else None,
                        "human_binary": 1 if human == "pass" else 0 if human == "fail" else None,
                        "selector_id": f"{result['metric_id']}@{result['metric_version']}#{result['preprocessing_hash'][:12]}",
                    }
                    if all(row.get(k) == v for k, v in filters.items() if k in row):
                        metric_rows.append(row)
            for request, response in judges[unit]:
                supplied = (
                    response.get("mapped_labels", response.get("parsed", {}).get("labels", {}))
                    if response and response.get("parsed")
                    else {}
                )
                matching = (
                    request["rubric_hash"] == annotation["rubric_hash"] and criterion in supplied
                )
                verdict = supplied.get(criterion) if matching else None

                # Pair labels use stable model identities for cross-task nominal agreement.
                def model_label(value):
                    return trials[assets[value]["trial_id"]]["model"] if value in assets else value

                row = {
                    **base,
                    "row_type": "judge_human",
                    "request_id": request["id"],
                    "response_id": response["id"] if response else None,
                    "protocol_key": request["protocol_key"],
                    "judge_provider": request["provider"],
                    "judge_model": request["model"],
                    "judge_config_hash": digest(
                        {
                            k: v
                            for k, v in request["settings"].items()
                            if k not in {"budget", "pricing"}
                        }
                    ),
                    "judge_rubric_hash": request["rubric_hash"],
                    "judge": verdict,
                    "status": response["status"] if response else "pending",
                    "match_status": "matched"
                    if matching
                    else "rubric_mismatch"
                    if request["rubric_hash"] != annotation["rubric_hash"]
                    else "missing_judge_label",
                    "synthetic": bool(response and response.get("synthetic")),
                    "operator_reconciled": bool(response and response.get("reconciliation_id")),
                    "human_model_preference": model_label(human),
                    "judge_model_preference": model_label(verdict),
                }
                if all(row.get(k) == v for k, v in filters.items() if k in row):
                    judge_rows.append(row)
    return {
        "label_view": label_view,
        "metric_rows": metric_rows,
        "judge_rows": judge_rows,
        "warnings": warnings,
        "join_policy": "Exact asset unit and criterion; judge/human rubric hashes must match. Raters are never implicitly averaged.",
        "dataset_metrics_excluded": sum(
            r["scope"] == "dataset" for r in current_results(store.list("result", eid))
        ),
    }


def compare(
    store: Store,
    eid: str,
    label_view: str = "raw",
    filters: Mapping[str, Any] | None = None,
    seed: int = 0,
) -> JsonObject:
    "Compute judge/human and metric/human summaries from explicit joined rows."
    data = joined_rows(store, eid, label_view, filters)
    judge_groups, metric_groups = defaultdict(list), defaultdict(list)
    for row in data["judge_rows"]:
        keys = (
            "judge_provider",
            "judge_model",
            "judge_config_hash",
            "rater_id",
            "rubric_hash",
            "criterion",
            "mode",
            "split",
            "category",
        )
        judge_groups[tuple(row[k] for k in keys)].append(row)
    judge_summaries = []
    for group, rows in sorted(judge_groups.items()):
        info = dict(
            zip(
                (
                    "provider",
                    "model",
                    "config_hash",
                    "rater_id",
                    "rubric_hash",
                    "criterion",
                    "mode",
                    "split",
                    "category",
                ),
                group,
            )
        )
        summary = {
            **info,
            "rows": len(rows),
            "matched": sum(r["match_status"] == "matched" for r in rows),
            "mismatched_rubric": sum(r["match_status"] == "rubric_mismatch" for r in rows),
            "synthetic": all(r["synthetic"] for r in rows),
            "operator_reconciled": any(r["operator_reconciled"] for r in rows),
        }
        if info["mode"] == "pointwise":
            summary["binary"] = binary_errors(rows)
            decided = [
                r for r in rows if r["human"] in {"pass", "fail"} and r["judge"] in {"pass", "fail"}
            ]
            summary["accuracy"] = cluster_interval(
                [
                    {"group_id": r["group_id"], "value": int(r["human"] == r["judge"])}
                    for r in decided
                ],
                seed=seed,
            )
        else:
            summary["preference_agreement"] = agreement(
                [(r["human_model_preference"], r["judge_model_preference"]) for r in rows]
            )
            summary["preference_agreement"]["limitation"] = (
                "Nominal model preferences; uncertainty/tie are retained, missing judgments excluded"
            )
        judge_summaries.append(summary)
    for row in data["metric_rows"]:
        keys = (
            "metric_id",
            "metric_version",
            "preprocessing_hash",
            "model",
            "rater_id",
            "rubric_hash",
            "criterion",
            "split",
            "category",
        )
        metric_groups[tuple(row[k] for k in keys)].append(row)
    metric_summaries = []
    for group, rows in sorted(metric_groups.items()):
        info = dict(
            zip(
                (
                    "metric_id",
                    "metric_version",
                    "preprocessing_hash",
                    "model",
                    "rater_id",
                    "rubric_hash",
                    "criterion",
                    "split",
                    "category",
                ),
                group,
            )
        )
        metric_summaries.append(
            {
                **info,
                "rows": len(rows),
                "score_missing": sum(r["score"] is None for r in rows),
                "human_nonbinary": sum(r["human_binary"] is None for r in rows),
                "correlations": correlations(
                    [r["score"] for r in rows], [r["human_binary"] for r in rows]
                ),
                "limitation": "Association with one rater/criterion; no implicit correctness threshold or pooled rater truth",
            }
        )
    return {
        "experiment_id": eid,
        "label_view": label_view,
        "seed": seed,
        "filters": filters or {},
        "judge_vs_human": judge_summaries,
        "metric_vs_human": metric_summaries,
        "warnings": data["warnings"],
        "join_policy": data["join_policy"],
        "source_rows": {"judge": len(data["judge_rows"]), "metric": len(data["metric_rows"])},
        "dataset_metrics_excluded": data["dataset_metrics_excluded"],
    }


def paired_metric_rows(
    store: Store, eid: str, filters: Mapping[str, Any] | None = None
) -> list[JsonObject]:
    """All trial outputs, including unannotated and missing outcomes."""
    from .metrics import REGISTRY

    filters = filters or {}
    allowed = {
        "prompt_id",
        "group_id",
        "repeat_index",
        "split",
        "category",
        "model",
        "trial_id",
        "asset_id",
        "metric_id",
        "metric_version",
        "preprocessing_hash",
        "reference_hash",
    }
    if set(filters) - allowed:
        raise ValueError(
            "Paired metric export accepts metric/task filters, not human-label filters: "
            + ", ".join(sorted(set(filters) - allowed))
        )
    prompts = {p["id"]: p for p in store.list("prompt", eid)}
    assets = defaultdict(list)
    for asset in store.list("asset", eid):
        if asset.get("trial_id"):
            assets[asset["trial_id"]].append(asset)
    results = defaultdict(list)
    for result in current_results(store.list("result", eid)):
        if result["scope"] != "dataset":
            for aid in result.get("asset_ids", []):
                results[(aid, result["metric_id"])].append(result)
    metric_ids = sorted(
        {
            m["id"]
            for m in store.get(eid)["config"].get("metrics", [])
            if REGISTRY[m["id"]]["scope"] != "dataset"
        }
    )
    rows = []
    for trial in store.list("trial", eid):
        prompt = prompts[trial["prompt_id"]]
        for asset in assets[trial["id"]] or [None]:
            for metric_id in metric_ids:
                aid = asset["id"] if asset else None
                for result in results[(aid, metric_id)] or [None]:
                    row = {
                        "row_type": "paired_metric",
                        "experiment_id": eid,
                        "trial_id": trial["id"],
                        "asset_id": aid,
                        "prompt_id": prompt["id"],
                        "group_id": prompt["group_id"],
                        "split": prompt["split"],
                        "category": prompt.get("category", "unspecified"),
                        "model": trial["model"],
                        "repeat_index": trial["repeat_index"],
                        "metric_id": metric_id,
                        "metric_version": result["metric_version"] if result else None,
                        "preprocessing_hash": result["preprocessing_hash"] if result else None,
                        "reference_hash": result.get("reference_hash") if result else None,
                        "result_id": result["id"] if result else None,
                        "score": result["score"]
                        if result and result["status"] == "success"
                        else None,
                        "status": result["status"]
                        if result
                        else "not_evaluated"
                        if asset
                        else "missing_output",
                        "population": "all_trial_outputs; no human-label requirement",
                    }
                    # Missing results remain in the denominator of a selected evaluator.
                    if all(
                        row[k] == v
                        or (
                            result is None
                            and k in {"metric_version", "preprocessing_hash", "reference_hash"}
                        )
                        for k, v in filters.items()
                    ):
                        rows.append(row)
    if not rows:
        raise ValueError("No matching per-asset metric tasks")
    for field in ("metric_id", "metric_version", "preprocessing_hash", "split"):
        values = {r[field] for r in rows if r[field] is not None}
        if len(values) > 1:
            raise ValueError("Ambiguous paired metrics; filter to one " + field)
    return rows


def analysis_input(
    store: Store,
    eid: str,
    operation: str,
    label_view: str = "raw",
    filters: Mapping[str, Any] | None = None,
) -> JsonObject | list[JsonObject]:
    "Produce experiment-backed inputs for the named statistical operation."
    if operation == "paired":
        return paired_metric_rows(store, eid, filters)
    data = joined_rows(store, eid, label_view, filters)
    rows = data["judge_rows"] if operation == "binary" else data["metric_rows"]
    if not rows:
        raise ValueError(
            "No matching experiment-backed rows; select a rater/criterion and compatible evidence"
        )

    def require_unique(fields):
        if len({tuple(r[k] for k in fields) for r in rows}) != 1:
            raise ValueError("Ambiguous analysis inputs; filter to one " + ", ".join(fields))

    require_unique(["rater_id", "criterion", "rubric_hash"])
    if operation == "binary":
        require_unique(["judge_provider", "judge_model", "judge_config_hash", "mode", "split"])
        if rows[0]["mode"] != "pointwise":
            raise ValueError("Binary errors require pointwise judgments")
        return rows
    if operation in {"correlations", "paired"}:
        require_unique(["metric_id", "metric_version", "preprocessing_hash", "split"])
        if operation == "correlations":
            return {
                "x": [r["score"] for r in rows],
                "y": [r["human_binary"] for r in rows],
                "source_rows": rows,
            }
        return rows
    if operation == "selection":
        require_unique(["split"])
        pool = {}
        for r in rows:
            a = pool.setdefault(
                r["asset_id"],
                {
                    "id": r["asset_id"],
                    "prompt_id": r["prompt_id"],
                    "group_id": r["group_id"],
                    "split": r["split"],
                    "scores": {},
                    "human": r["human"],
                    "annotation_id": r["annotation_id"],
                },
            )
            if r["selector_id"] in a["scores"]:
                raise ValueError(
                    "Multiple results for one selector and candidate; filter evaluator versions"
                )
            a["scores"][r["selector_id"]] = r["score"]
        return list(pool.values())
    raise ValueError("Supported exports: binary, correlations, paired, selection")
