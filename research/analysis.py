"""Explicit denominators, paired comparisons, and independent-group uncertainty."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from scipy import stats

from .contracts import digest
from .store import Store
from .types import JsonObject


def divide(a: float, b: float) -> float | None:
    "Return a ratio, or null when its denominator is zero."
    return a / b if b else None


def binary_errors(rows: Sequence[JsonObject]) -> JsonObject:
    "Count observed binary outcomes with explicit coverage and denominators."
    eligible = [r for r in rows if r.get("human") in {"pass", "fail"}]
    judged = [r for r in eligible if r.get("judge") in {"pass", "fail"}]
    tp = sum(r["human"] == r["judge"] == "pass" for r in judged)
    tn = sum(r["human"] == r["judge"] == "fail" for r in judged)
    fp = sum(r["human"] == "fail" and r["judge"] == "pass" for r in judged)
    fn = sum(r["human"] == "pass" and r["judge"] == "fail" for r in judged)
    return {
        "human_binary": len(eligible),
        "judged_binary": len(judged),
        "excluded_human_uncertain": len(rows) - len(eligible),
        "abstained": len(eligible) - len(judged),
        "coverage": divide(len(judged), len(eligible)),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "p_judge_pass_given_human_fail": {"value": divide(fp, fp + tn), "denominator": fp + tn},
        "p_human_fail_given_judge_pass": {"value": divide(fp, fp + tp), "denominator": fp + tp},
        "false_rejection": {"value": divide(fn, tp + fn), "denominator": tp + fn},
        "precision": divide(tp, tp + fp),
        "recall": divide(tp, tp + fn),
        "limitation": "Conditional on observed binary labels; enriched failure sets do not estimate production prevalence",
    }


def correlations(x: Sequence[float | None], y: Sequence[float | None]) -> JsonObject:
    "Compute complete-pair rank correlations, rejecting small or constant samples."
    pairs = [(a, b) for a, b in zip(x, y, strict=True) if a is not None and b is not None]
    if len(pairs) < 3 or len({p[0] for p in pairs}) < 2 or len({p[1] for p in pairs}) < 2:
        return {
            "n": len(pairs),
            "spearman": None,
            "kendall_tau_b": None,
            "reason": "Insufficient or constant paired observations",
        }
    a, b = zip(*pairs)
    return {
        "n": len(pairs),
        "spearman": float(stats.spearmanr(a, b).statistic),
        "kendall_tau_b": float(stats.kendalltau(a, b, variant="b").statistic),
        "ties": "average Spearman ranks; Kendall tau-b",
    }


def cluster_interval(
    rows: Sequence[JsonObject],
    value: str = "value",
    seed: int = 0,
    iterations: int = 2000,
    strata: str | None = None,
) -> JsonObject:
    """Percentile CI for an observation mean, resampling whole independent groups."""
    clean = [r for r in rows if r.get(value) is not None]
    groups = defaultdict(list)
    for row in clean:
        groups[row["group_id"]].append(row)
    point = float(np.mean([r[value] for r in clean])) if clean else None
    if len(groups) < 2:
        return {
            "mean": point,
            "low": None,
            "high": None,
            "groups": len(groups),
            "n": len(clean),
            "reason": "Fewer than two independent groups",
        }
    partitions = defaultdict(list)
    for group, items in sorted(groups.items()):
        labels = {r.get(strata) for r in items} if strata else {None}
        if len(labels) != 1:
            raise ValueError("A cluster cannot cross bootstrap strata")
        partitions[next(iter(labels))].append(group)
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(iterations):
        drawn = [
            g
            for partition in partitions.values()
            for g in rng.choice(partition, len(partition), replace=True)
        ]
        samples.append(float(np.mean([r[value] for g in drawn for r in groups[g]])))
    return {
        "mean": point,
        "low": float(np.quantile(samples, 0.025)),
        "high": float(np.quantile(samples, 0.975)),
        "groups": len(groups),
        "n": len(clean),
        "seed": seed,
        "iterations": iterations,
        "method": "95% percentile bootstrap of independent prompt/template groups, observation-weighted mean",
        "strata": strata,
    }


def paired_difference(
    rows: Sequence[JsonObject], model_a: str, model_b: str, seed: int = 0
) -> JsonObject:
    "Compare complete model/task pairs using independent-group bootstrap intervals."
    tasks = defaultdict(dict)
    for row in rows:
        key = (row["prompt_id"], row["repeat_index"])
        if row["model"] in tasks[key]:
            raise ValueError(
                "Duplicate model/task observation; choose evaluator version and trial attempt explicitly"
            )
        tasks[key][row["model"]] = row
    paired = []
    for task in tasks.values():
        a, b = task.get(model_a), task.get(model_b)
        if a and b and a.get("score") is not None and b.get("score") is not None:
            if a["group_id"] != b["group_id"]:
                raise ValueError("Paired observations have different groups")
            paired.append({"group_id": a["group_id"], "value": a["score"] - b["score"]})
    return {
        "model_a": model_a,
        "model_b": model_b,
        "paired_tasks": len(paired),
        "total_tasks": len(tasks),
        "excluded_unpaired_or_missing": len(tasks) - len(paired),
        "difference": cluster_interval(paired, seed=seed),
    }


def agreement(pairs: Sequence[tuple[Any, Any]]) -> JsonObject:
    "Compute nominal agreement and kappa; retain uncertainty and exclude missing labels."
    clean = [(a, b) for a, b in pairs if a is not None and b is not None]
    if not clean:
        return {"n": 0, "observed_agreement": None, "cohen_kappa": None}
    left, right = Counter(a for a, _ in clean), Counter(b for _, b in clean)
    observed = sum(a == b for a, b in clean) / len(clean)
    expected = sum(left[k] * right[k] for k in left.keys() | right.keys()) / len(clean) ** 2
    return {
        "n": len(clean),
        "observed_agreement": observed,
        "cohen_kappa": (observed - expected) / (1 - expected)
        if expected < 1 and len(clean) >= 2
        else None,
        "reason": "Fewer than two paired units"
        if len(clean) < 2
        else "Constant marginal labels"
        if expected == 1
        else None,
        "definition": "Nominal Cohen kappa on paired annotations; uncertainty retained as a category, missing excluded",
    }


def selection(
    candidates: Sequence[JsonObject],
    selectors: Mapping[str, Any],
    n_values: Sequence[int],
    seed: int = 0,
) -> JsonObject:
    """Shared nested candidate pools; human labels used only after selection."""
    if any(v not in {"higher", "lower"} for v in selectors.values()) or any(
        not isinstance(n, int) or n < 1 for n in n_values
    ):
        raise ValueError("Selectors need directions and positive integer pool sizes")
    if len({r["id"] for r in candidates}) != len(candidates):
        raise ValueError("Duplicate candidate identity")
    rng = np.random.default_rng(seed)
    groups = defaultdict(list)
    for row in candidates:
        groups[row["prompt_id"]].append(row)
    output = []
    for prompt, rows in sorted(groups.items()):
        ordered = sorted(rows, key=lambda x: x["id"])
        order = rng.permutation(len(ordered))
        for n in n_values:
            pool = [ordered[i] for i in order[:n]]
            if not pool:
                continue
            for selector, direction in {"random": "random", **selectors}.items():
                available = (
                    pool
                    if selector == "random"
                    else [r for r in pool if r.get("scores", {}).get(selector) is not None]
                )
                if not available:
                    chosen = None
                elif selector == "random":
                    chosen = available[int(rng.integers(len(available)))]
                else:
                    best = (max if direction == "higher" else min)(
                        r["scores"][selector] for r in available
                    )
                    tied = [r for r in available if r["scores"][selector] == best]
                    chosen = tied[int(rng.integers(len(tied)))]
                independent_groups = {r.get("group_id", prompt) for r in rows}
                if len(independent_groups) != 1:
                    raise ValueError("Candidates for a prompt must share an independent group")
                output.append(
                    {
                        "prompt_id": prompt,
                        "group_id": next(iter(independent_groups)),
                        "n": n,
                        "actual_pool": len(pool),
                        "missing_candidates": max(0, n - len(pool)),
                        "pool_hash": digest([r["id"] for r in pool]),
                        "selector": selector,
                        "available_scores": len(available),
                        "selected": chosen["id"] if chosen else None,
                        "human": chosen.get("human") if chosen else None,
                    }
                )
    summaries = []
    for n, selector in sorted({(r["n"], r["selector"]) for r in output}):
        rows = [r for r in output if r["n"] == n and r["selector"] == selector]
        observed = [
            {"group_id": r["group_id"], "value": int(r["human"] == "pass")}
            for r in rows
            if r["human"] in {"pass", "fail"}
        ]
        summaries.append(
            {
                "n": n,
                "selector": selector,
                "prompts": len(rows),
                "human_binary": len(observed),
                "human_missing_or_uncertain": len(rows) - len(observed),
                "task_pass_rate": cluster_interval(observed, seed=seed),
            }
        )
    return {
        "seed": seed,
        "tie_handling": "seeded uniform random among ties",
        "results": output,
        "summary": summaries,
        "limitation": "Fixed imported candidate pool; human labels do not enter selection or tuning",
    }


def choose_threshold(
    rows: Sequence[JsonObject], thresholds: Sequence[float], direction: str = "higher"
) -> JsonObject:
    """Development-only threshold fitting; held-out labels are rejected, not filtered away."""
    if not rows or any(r.get("split") not in {"train", "development"} for r in rows):
        raise ValueError(
            "Threshold fitting requires explicitly train/development-only observations"
        )
    if direction not in {"higher", "lower"} or not thresholds:
        raise ValueError("Explicit thresholds and score direction required")
    candidates = []
    for threshold in thresholds:
        scored = [
            {
                "human": r.get("human"),
                "judge": "uncertain"
                if r.get("score") is None
                else "pass"
                if (r["score"] >= threshold if direction == "higher" else r["score"] <= threshold)
                else "fail",
            }
            for r in rows
        ]
        errors = binary_errors(scored)
        candidates.append(
            {
                "threshold": threshold,
                "errors": errors,
                "accuracy": divide(errors["tp"] + errors["tn"], errors["judged_binary"]),
            }
        )
    valid = [c for c in candidates if c["accuracy"] is not None]
    chosen = max(valid, key=lambda c: c["accuracy"]) if valid else None
    return {
        "selected_threshold": chosen["threshold"] if chosen else None,
        "direction": direction,
        "tie_rule": "first supplied threshold",
        "candidates": candidates,
        "fitting_split": "train/development",
        "held_out_labels_used": False,
    }


def annotation_agreement(
    store: Store, eid: str, annotations: Sequence[JsonObject]
) -> list[JsonObject]:
    """Keep raters and criteria separate; never replace disagreements with a vote."""
    assignments = {r["id"]: r for r in store.list("assignment", eid)}
    units = defaultdict(dict)
    for label in annotations:
        assignment = assignments[label["assignment_id"]]
        for criterion, verdict in label["labels"].items():
            if verdict in {"A", "B"}:
                verdict = assignment["asset_ids"][0 if verdict == "A" else 1]
            key = (tuple(sorted(assignment["asset_ids"])), label["rubric_hash"], criterion)
            units[key][label["rater_id"]] = verdict
    raters = sorted({r for labels in units.values() for r in labels})
    output = []
    for i, first in enumerate(raters):
        for second in raters[i + 1 :]:
            for rubric_hash, criterion in sorted({(key[1], key[2]) for key in units}):
                relevant = [
                    labels for key, labels in units.items() if key[1:] == (rubric_hash, criterion)
                ]
                output.append(
                    {
                        "rater_a": first,
                        "rater_b": second,
                        "rubric_hash": rubric_hash,
                        "criterion": criterion,
                        "available_units": len(relevant),
                        **agreement([(r.get(first), r.get(second)) for r in relevant]),
                        "duplicate_policy": "latest_created_at_then_id",
                    }
                )
                if any(
                    a.get("independent") is False and a["rater_id"] in {first, second}
                    for a in annotations
                ):
                    output[-1].update(
                        cohen_kappa=None,
                        reason="Adjudicated agreement is descriptive; adjudication is not independent rater evidence",
                    )
                elif any(
                    assignments[a["assignment_id"]]["mode"] == "pairwise"
                    and a["rubric_hash"] == rubric_hash
                    for a in annotations
                ):
                    output[-1].update(
                        cohen_kappa=None,
                        reason="Pairwise human agreement uses unit-specific asset identities; pooled nominal kappa is not defined here",
                    )
    return output


def current_results(results: Sequence[JsonObject]) -> list[JsonObject]:
    """Select the newest attempt per exact evaluator cache identity, retaining versions."""
    superseded = {r["supersedes"] for r in results if r.get("supersedes")}
    superseded.update(old for r in results for old in r.get("supersedes_ids", []))
    return [r for r in results if r["id"] not in superseded]


def summarize(
    store: Store, experiment_id: str, seed: int = 0, label_view: str = "raw"
) -> JsonObject:
    "Summarize current experiment evidence without modifying any records."
    if label_view not in {"raw", "adjudicated"}:
        raise ValueError("label_view must be raw or adjudicated")
    records = store.list(experiment_id=experiment_id)
    kinds = defaultdict(list)
    for r in records:
        kinds[r["kind"]].append(r)
    trial_ids = {r["id"] for r in kinds["trial"]}
    success_trials = {r["trial_id"] for r in kinds["attempt"] if r["status"] == "success"}
    failed_trials = {
        r["trial_id"] for r in kinds["attempt"] if r["status"] in {"failed", "rejected"}
    } - success_trials
    metrics = defaultdict(list)
    trials = {r["id"]: r for r in kinds["trial"]}
    prompts = {r["id"]: r for r in kinds["prompt"]}
    effective_results = current_results(kinds["result"])
    for r in effective_results:
        trial = trials.get(r.get("trial_id"), {})
        prompt = prompts.get(trial.get("prompt_id"), {})
        model = trial.get("model", r.get("model", "dataset"))
        metrics[
            (
                r["metric_id"],
                r["metric_version"],
                r["preprocessing_hash"],
                model,
                prompt.get("category", "unspecified"),
                prompt.get("split", "dataset"),
            )
        ].append(r)
    summaries = []
    for (metric, version, preprocessing, model, category, split), rows in sorted(metrics.items()):
        scores = []
        for r in rows:
            if r["status"] != "success" or r["score"] is None:
                continue
            trial = trials.get(r.get("trial_id"), {})
            prompt = prompts.get(trial.get("prompt_id"), {})
            scores.append(
                {"value": r["score"], "group_id": prompt.get("group_id", r["membership_hash"])}
            )
        summaries.append(
            {
                "metric_id": metric,
                "version": version,
                "preprocessing_hash": preprocessing,
                "model": model,
                "category": category,
                "split": split,
                "scope": rows[0]["scope"],
                "statuses": dict(Counter(r["status"] for r in rows)),
                "denominator": len(rows),
                "summary": cluster_interval(scores, seed=seed)
                if rows[0]["scope"] != "dataset"
                else None,
                "dataset_results": [
                    {
                        "score": r["score"],
                        "membership_hash": r["membership_hash"],
                        "status": r["status"],
                    }
                    for r in rows
                ]
                if rows[0]["scope"] == "dataset"
                else None,
            }
        )
    from .comparison import compare
    from .labels import select_annotations

    annotations, label_warnings = select_annotations(store, experiment_id, label_view)
    calls = [r for r in kinds["judge_call"] if r.get("phase") == "response"]
    request_calls = [r for r in kinds["judge_call"] if r.get("phase") == "request"]
    # Reconciliation may append a recovered response for the same HTTP request.
    # Count the request once; a supplied response has no measured network latency.
    calls = list({r["request_record_id"]: r for r in calls}.values())
    tradeoffs = []
    for provider, model in sorted({(r["provider"], r["configured_model"]) for r in calls}):
        selected = [r for r in calls if (r["provider"], r["configured_model"]) == (provider, model)]
        actual_requests = [
            r for r in request_calls if (r["provider"], r["model"]) == (provider, model)
        ]
        latencies = [r["elapsed_ms"] for r in selected if not r.get("reconciliation_id")]
        tradeoffs.append(
            {
                "provider": provider,
                "model": model,
                "calls": len(actual_requests),
                "responses": len(selected),
                "statuses": dict(Counter(r["status"] for r in selected)),
                "mean_latency_ms": float(np.mean(latencies)) if latencies else None,
                "latency_observations": len(latencies),
                "cost": sum(r["cost"] for r in selected)
                if len(selected) == len(actual_requests)
                and all(r.get("cost") is not None for r in selected)
                else None,
                "estimated_cost": sum(r["estimated_cost"] for r in selected)
                if selected
                and len(selected) == len(actual_requests)
                and all(r.get("estimated_cost") is not None for r in selected)
                else None,
                "estimated_cost_calls": sum(r.get("estimated_cost") is not None for r in selected),
                "synthetic": all(r.get("synthetic") for r in selected),
            }
        )
    return {
        "planned": len(trial_ids),
        "generated": len(success_trials),
        "failed": len(failed_trials),
        "pending": len(trial_ids - success_trials - failed_trials),
        "scored": sum(r["status"] == "success" for r in effective_results),
        "unavailable": sum(r["status"] == "unavailable_dependency" for r in effective_results),
        "annotations": len(annotations),
        "label_view": label_view,
        "annotation_records": len(kinds["annotation"]),
        "annotation_selection_warnings": label_warnings,
        "evaluation_attempts": len(kinds["result"]),
        "superseded_evaluations": len(kinds["result"]) - len(effective_results),
        "metrics": summaries,
        "seed": seed,
        "judge_calls": len(request_calls),
        "known_cost": sum(r["cost"] for r in calls)
        if calls and all(r.get("cost") is not None for r in calls)
        else None,
        "cost_known_calls": sum(r.get("cost") is not None for r in calls),
        "judge_tradeoffs": tradeoffs,
        "rater_agreement": annotation_agreement(store, experiment_id, annotations),
        "judge_provenance_warnings": [
            r
            for r in kinds["judge_reconciliation"]
            if r.get("resolution") == "legacy_content_key_collision"
        ],
        "comparisons": compare(store, experiment_id, label_view=label_view, seed=seed),
        "historical_rankings": kinds["historical_ranking"],
        "assumptions": "Independent prompt/template groups; repeated generations remain clustered. No population inference across unspecified models. No combined quality score.",
    }
