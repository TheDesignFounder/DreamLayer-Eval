"""Frozen planning, content-addressed imports and restartable local execution."""

from __future__ import annotations

import copy
import json
import shutil
import threading
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .composition import interpret
from .contracts import digest, file_hash, record, redact
from .judges import judge, rubric_validate
from .media import probe
from .metrics import REGISTRY, cache_key, dependencies, evaluate
from .store import Store
from .types import JsonObject, PathLike


def managed_asset(path: PathLike, media_root: PathLike) -> JsonObject:
    "Copy a validated media file into content-addressed local storage."
    path = Path(path).resolve()
    sha = file_hash(path)
    metadata = probe(path)
    dest = Path(media_root) / (sha + path.suffix.lower())
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copyfile(path, dest)
    if file_hash(dest) != sha:
        raise ValueError("Managed media content mismatch")
    return {
        "sha256": sha,
        "locator": str(dest.resolve()),
        "original_filename": path.name,
        "media": metadata,
    }


def validate_config(config: JsonObject) -> JsonObject:
    "Validate an experiment configuration and return the supplied object."
    if not isinstance(config, dict):
        raise ValueError("Experiment configuration must be a JSON object")
    if config.get("schema_version") != 1 or not config.get("name"):
        raise ValueError("Experiment needs schema_version=1 and name")
    prompts = config.get("prompts", [])
    if not prompts or len({p["id"] for p in prompts}) != len(prompts):
        raise ValueError("Unique prompts required")
    splits = {}
    for prompt in prompts:
        if prompt.get("split", "exploratory") not in {
            "train",
            "development",
            "test",
            "exploratory",
        }:
            raise ValueError("Invalid prompt split")
        group = prompt.get("group_id", prompt["id"])
        split = prompt.get("split", "exploratory")
        if group in splits and splits[group] != split:
            raise ValueError("Prompt family leakage across splits")
        splits[group] = split
    models = config.get("models", ["imported"])
    if not models or len(set(models)) != len(models):
        raise ValueError("Unique model labels required")
    if not 1 <= config.get("repetitions", 1) <= 1000:
        raise ValueError("Repetitions must be 1–1000")
    if not 1 <= config.get("concurrency", 1) <= 8:
        raise ValueError("Concurrency must be 1–8")
    if not 0 <= config.get("rate_limit_seconds", 0) <= 30:
        raise ValueError("Trial start interval must be 0–30 seconds")
    for metric in config.get("metrics", []):
        if metric["id"] not in REGISTRY:
            raise ValueError(f"Unknown evaluator: {metric['id']}")
    for config_judge in config.get("judges", []):
        rubric_validate(config_judge["rubric"])
    if config.get("generation") and config.get("assets"):
        raise ValueError("Use separate experiment versions for imported and generated trial plans")
    return config


def create(store: Store, config: JsonObject, media_root: PathLike) -> JsonObject:
    "Freeze configuration, import media, and persist planned experiment records."
    config = copy.deepcopy(validate_config(config))
    for configured_judge in config.get("judges", []):
        configured_judge.setdefault("judge_protocol_version", 2)
    resolved, references, failures = [], [], []
    for source in config.get("assets", []):
        item = {k: v for k, v in source.items() if k != "path"}
        try:
            item.update(managed_asset(source["path"], media_root))
            item["original_filename"] = source.get("original_filename", item["original_filename"])
        except (ValueError, OSError) as exc:
            item.update(
                error=f"{type(exc).__name__}: {Path(source['path']).name}: media unavailable",
                original_filename=Path(source["path"]).name,
            )
            failures.append({"filename": item["original_filename"], "reason": str(exc)})
        resolved.append(item)
    for source in config.get("references", []):
        prompt_ids = source.get("prompt_ids", [])
        if not isinstance(prompt_ids, list) or set(prompt_ids) - {
            p["id"] for p in config["prompts"]
        }:
            raise ValueError("Reference prompt_ids must identify configured prompts")
        references.append(
            {**managed_asset(source["path"], media_root), "prompt_source_ids": prompt_ids}
        )
    # Freeze portable config; local locators live only on asset records.
    config["assets"] = [{k: v for k, v in a.items() if k != "locator"} for a in resolved]
    config["references"] = [{k: v for k, v in a.items() if k != "locator"} for a in references]
    for prompt in config["prompts"]:
        prompt.setdefault("criteria", interpret(prompt["text"])["criteria"])
        prompt.setdefault("group_id", prompt["id"])
        prompt.setdefault("split", "exploratory")
        prompt.setdefault("negative_prompt", "")
    generation = config.get("generation")
    if generation and "workflow_path" in generation:
        workflow = json.loads(Path(generation.pop("workflow_path")).read_text())
        generation["workflow"] = redact(workflow)
        generation["workflow_hash"] = digest(generation["workflow"])
    config = redact(config)
    experiment = record(
        "experiment",
        config=config,
        config_hash=digest(config),
        purpose=config.get("purpose", "exploratory infrastructure"),
        hypothesis=config.get("hypothesis"),
    )
    eid = experiment["id"]
    experiment["experiment_id"] = eid
    records = [experiment]
    prompt_map = {}
    for prompt in config["prompts"]:
        p = record(
            "prompt",
            eid,
            **{k: v for k, v in prompt.items() if k != "id"},
            source_id=prompt["id"],
            id=digest([eid, "prompt", prompt["id"]]),
        )
        prompt_map[prompt["id"]] = p
        records.append(p)
    models = config.get("models", ["imported"])
    if not resolved:
        resolved = [
            {"prompt_id": p["id"], "model": m, "repeat_index": r}
            for p in config["prompts"]
            for m in models
            for r in range(config.get("repetitions", 1))
        ]
    seen, membership_splits, sha_assets = set(), {}, {}
    for source in resolved:
        prompt = prompt_map[source["prompt_id"]]
        model, repeat = source.get("model", models[0]), source.get("repeat_index", 0)
        key = (prompt["id"], model, repeat)
        if key in seen:
            raise ValueError("Duplicate trial prompt/model/repeat; assign an explicit repeat index")
        if model not in models or not isinstance(repeat, int) or repeat < 0:
            raise ValueError("Invalid model or repeat index")
        seen.add(key)
        trial = record(
            "trial",
            eid,
            id=digest([eid, *key]),
            prompt_id=prompt["id"],
            model=model,
            repeat_index=repeat,
            requested_parameters=config.get("parameters", {}).get(model, {}),
            input_error=source.get("error"),
            source_sha256=source.get("sha256"),
            generation=config.get("generation"),
            group_id=prompt["group_id"],
            split=prompt["split"],
        )
        records.append(trial)
        if source.get("sha256"):
            sha = source["sha256"]
            if sha in membership_splits and membership_splits[sha] != prompt["split"]:
                raise ValueError("Duplicate content leaks across splits")
            membership_splits[sha] = prompt["split"]
            asset = record(
                "asset",
                eid,
                **{k: source[k] for k in ("sha256", "locator", "original_filename", "media")},
                trial_id=trial["id"],
                id=digest([trial["id"], sha]),
                parent_sha256=source.get("parent_sha256"),
                transformations=source.get("transformations", []),
                provider_identity=source.get(
                    "provider_identity",
                    {"provider": None, "model": None, "endpoint": None, "version": None},
                ),
                requested_parameters=source.get("requested_parameters", {}),
                accepted_parameters=source.get("accepted_parameters", {}),
                unverified_parameters=source.get("unverified_parameters", {}),
                generation_timestamp=source.get("generation_timestamp"),
            )
            sha_assets[sha] = asset
            records.append(asset)
    for a in [r for r in records if r["kind"] == "asset"]:
        parent = a.get("parent_sha256")
        if parent:
            if parent not in sha_assets:
                raise ValueError("Derived asset parent is missing")
            parent_trial = next(t for t in records if t["id"] == sha_assets[parent]["trial_id"])
            own_trial = next(t for t in records if t["id"] == a["trial_id"])
            if (parent_trial["split"], parent_trial["group_id"]) != (
                own_trial["split"],
                own_trial["group_id"],
            ):
                raise ValueError("Derived assets must share the parent split and independent group")
            a["parent_asset_id"] = sha_assets[parent]["id"]
    for ref in references:
        asset = record(
            "asset",
            eid,
            **ref,
            role="reference",
            trial_id=None,
            parent_asset_id=None,
            transformations=[],
        )
        records.append(asset)
        for prompt in prompt_map.values():
            if not ref["prompt_source_ids"] or prompt["source_id"] in ref["prompt_source_ids"]:
                prompt.setdefault("reference_asset_ids", []).append(asset["id"])
    store.put_many(records)
    store.job(eid)
    return experiment


def preview(config: JsonObject) -> JsonObject:
    "Interpret editable prompt criteria without freezing an experiment."
    config = copy.deepcopy(validate_config(config))
    interpretations = []
    for prompt in config["prompts"]:
        interpreted = interpret(prompt["text"])
        supplied = "criteria" in prompt
        prompt.setdefault("criteria", interpreted["criteria"])
        interpretations.append(
            {"prompt_id": prompt["id"], **interpreted, "edited_criteria_preserved": supplied}
        )
    return {"config": config, "interpretations": interpretations, "frozen": False}


def plan(store: Store, experiment_id: str) -> JsonObject:
    "Report planned work, dependency checks, call bounds and resume warnings."
    exp = store.get(experiment_id)
    config = exp["config"]
    trials = store.list("trial", experiment_id)
    assets = store.list("asset", experiment_id)
    from .upgrades import warnings as upgrade_warnings

    warnings = upgrade_warnings(store, experiment_id)
    from .preflight import inspect

    preflight = inspect(config)
    for metric in config.get("metrics", []):
        missing = dependencies(metric["id"])
        if missing:
            warnings.append({"metric": metric["id"], "missing_dependencies": missing})
    hashes = [a["sha256"] for a in assets if a.get("role") != "reference"]
    if len(set(hashes)) != len(hashes):
        warnings.append(
            {
                "duplicate_content": len(hashes) - len(set(hashes)),
                "reason": "Repeated bytes are not independent media",
            }
        )
    return {
        "experiment_id": experiment_id,
        "config_hash": exp["config_hash"],
        "trials": trials,
        "expected_trials": len(trials),
        "expected_metric_evaluations": sum(
            len(config.get("models", ["imported"]))
            if REGISTRY[m["id"]]["scope"] == "dataset"
            else len(trials)
            for m in config.get("metrics", [])
        ),
        "maximum_judge_calls": sum(
            judge_units(trials, config, j)
            * min(
                j.get("budget", {}).get("calls", 1000000),
                (2 if j.get("protocol") == "two_pass" else 1)
                * (1 + j.get("retry", {}).get("max_retries", 1)),
            )
            for j in config.get("judges", [])
        ),
        "expected_generation_calls": len(trials) if config.get("generation") else 0,
        "cost": None,
        "warnings": warnings,
        "preflight": preflight,
        "parameters": config.get("parameters", {}),
        "generation": config.get("generation"),
        "note": "Provider cost and parameter enforcement unknown until an actual response; matching seed integers are not matched randomness",
    }


_locks = {}
_locks_guard = threading.Lock()


def judge_units(trials: Sequence[JsonObject], config: JsonObject, judge_config: JsonObject) -> int:
    "Count complete trial or paired units eligible for a judge configuration."
    if judge_config.get("mode", "pointwise") != "pairwise":
        return len(trials)
    pair = judge_config.get("model_pair", config.get("models", [])[:2])
    if len(pair) != 2 or len(set(pair)) != 2:
        raise ValueError("Pairwise judges require two distinct model labels")
    grouped = {}
    for trial in trials:
        grouped.setdefault((trial["prompt_id"], trial["repeat_index"]), set()).add(trial["model"])
    return sum(set(pair) <= models for models in grouped.values())


def execute(
    store: Store,
    experiment_id: str,
    media_root: PathLike,
    limit: int | None = None,
    rerun_failed: bool = False,
    upgrade_evaluators: bool = False,
) -> JsonObject:
    "Run or resume a POSIX-locked experiment with explicit retry and upgrade rules."
    from .platforms import require_supported_platform

    require_supported_platform()
    import fcntl

    from . import upgrades

    with _locks_guard:
        lock = _locks.setdefault((str(store.path), experiment_id), threading.Lock())
    if not lock.acquire(blocking=False):
        return store.job(experiment_id)
    process_lock = open(
        store.path.with_name(store.path.name + "." + digest(experiment_id)[:16] + ".lock"), "a"
    )
    try:
        fcntl.flock(process_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        process_lock.close()
        lock.release()
        return store.job(experiment_id)
    try:
        config = store.get(experiment_id)["config"]
        resume_warnings = upgrades.warnings(store, experiment_id, upgrade_evaluators, rerun_failed)
        store.job(experiment_id, state="running", cancel=0, error=None)
        trials = sorted(store.list("trial", experiment_id), key=lambda t: t["id"])
        prompts = {p["id"]: p for p in store.list("prompt", experiment_id)}
        references = [a for a in store.list("asset", experiment_id) if a.get("role") == "reference"]
        if limit is not None:
            trials = trials[:limit]
        rate_lock = threading.Lock()
        next_start = [0.0]

        def work(trial):
            with rate_lock:
                delay = max(0, next_start[0] - time.monotonic())
                if delay:
                    time.sleep(delay)
                next_start[0] = time.monotonic() + config.get("rate_limit_seconds", 0)
            if store.job(experiment_id)["cancel"]:
                return
            assets = store.list("asset", experiment_id, trial_id=trial["id"])
            attempts = store.list("attempt", experiment_id, trial_id=trial["id"])
            if not attempts or (trial.get("generation") and not assets):
                if trial.get("generation") and not assets:
                    from .generation import generate

                    generate(store, experiment_id, trial, prompts[trial["prompt_id"]], media_root)
                    assets = store.list("asset", experiment_id, trial_id=trial["id"])
                else:
                    store.put(
                        record(
                            "attempt",
                            experiment_id,
                            id=digest([trial["id"], "import", 0]),
                            trial_id=trial["id"],
                            attempt_index=0,
                            retry_of=None,
                            status="success" if assets else "failed",
                            reason=trial.get("input_error")
                            or (None if assets else "No imported output"),
                            provider_request_id=None,
                            provider_version=None,
                            accepted_parameters={},
                            unverified_parameters=trial["requested_parameters"],
                        )
                    )
            if not assets:
                return
            prompt = prompts[trial["prompt_id"]]
            task_references = [
                a
                for a in references
                if not a.get("prompt_source_ids") or prompt["source_id"] in a["prompt_source_ids"]
            ]
            for metric in config.get("metrics", []):
                if store.job(experiment_id)["cancel"]:
                    return
                if REGISTRY[metric["id"]]["scope"] == "dataset":
                    continue
                settings = {k: v for k, v in metric.items() if k != "id"}
                if metric["id"] == "object_criteria":
                    settings.setdefault("criteria", prompt["criteria"])
                for asset in assets:
                    prior = upgrades.previous_results(
                        store,
                        experiment_id,
                        metric,
                        [asset],
                        task_references,
                        trial_id=trial["id"],
                        configured=config.get("metrics", []),
                    )
                    if upgrades.should_preserve(
                        prior, metric["id"], upgrade_evaluators, rerun_failed
                    ):
                        continue
                    key = digest(
                        [
                            trial["id"],
                            cache_key(
                                metric["id"], [asset], prompt["text"], settings, task_references
                            ),
                        ]
                    )
                    cached = store.cached(key)
                    upgrading = (
                        upgrade_evaluators or upgrades.retry_failed_unit(prior, rerun_failed)
                    ) and upgrades.has_upgrade(prior, metric["id"])
                    if (
                        cached
                        and not upgrading
                        and not (
                            rerun_failed
                            and cached["status"] in {"failed_evaluation", "unavailable_dependency"}
                        )
                    ):
                        continue
                    output = evaluate(
                        metric["id"],
                        [asset],
                        prompt["text"],
                        settings,
                        task_references,
                        experiment_id,
                    )
                    output["trial_id"] = trial["id"]
                    upgrades.annotate(output, metric, prior, upgrade_evaluators, rerun_failed)
                    slot = digest(
                        [trial["id"], asset["id"], metric, REGISTRY[metric["id"]]["version"]]
                    )
                    store.cache(key, output, slot=slot)
            for judge_config in config.get("judges", []):
                if store.job(experiment_id)["cancel"]:
                    return
                if judge_config.get("mode", "pointwise") == "pairwise":
                    continue
                judge(
                    store, experiment_id, assets[:1], prompt["text"], judge_config, task_references
                )

        with ThreadPoolExecutor(max_workers=config.get("concurrency", 1)) as pool:
            list(pool.map(work, trials))
        if not store.job(experiment_id)["cancel"] and limit is None:
            assets = [a for a in store.list("asset", experiment_id) if a.get("role") != "reference"]
            for metric in config.get("metrics", []):
                if REGISTRY[metric["id"]]["scope"] != "dataset":
                    continue
                for model in config.get("models", ["imported"]):
                    ids = {t["id"] for t in trials if t["model"] == model}
                    selected = list(
                        {a["sha256"]: a for a in assets if a.get("trial_id") in ids}.values()
                    )
                    settings = {k: v for k, v in metric.items() if k != "id"}
                    prior = upgrades.previous_results(
                        store,
                        experiment_id,
                        metric,
                        selected,
                        references,
                        model=model,
                        configured=config.get("metrics", []),
                    )
                    if upgrades.should_preserve(
                        prior, metric["id"], upgrade_evaluators, rerun_failed
                    ):
                        continue
                    key = digest(
                        [
                            experiment_id,
                            model,
                            cache_key(metric["id"], selected, "", settings, references),
                        ]
                    )
                    cached = store.cached(key)
                    upgrading = (
                        upgrade_evaluators or upgrades.retry_failed_unit(prior, rerun_failed)
                    ) and upgrades.has_upgrade(prior, metric["id"])
                    if (
                        not cached
                        or upgrading
                        or (
                            rerun_failed
                            and cached["status"] in {"failed_evaluation", "unavailable_dependency"}
                        )
                    ):
                        out = evaluate(
                            metric["id"],
                            selected,
                            config=settings,
                            references=references,
                            experiment_id=experiment_id,
                        )
                        out["model"] = model
                        upgrades.annotate(out, metric, prior, upgrade_evaluators, rerun_failed)
                        slot = digest(
                            [experiment_id, model, metric, REGISTRY[metric["id"]]["version"]]
                        )
                        store.cache(key, out, slot=slot)
            for judge_config in config.get("judges", []):
                if judge_config.get("mode") != "pairwise":
                    continue
                pairs = judge_config.get("model_pair", config.get("models", [])[:2])
                for prompt_id in prompts:
                    for repeat in sorted(
                        {t["repeat_index"] for t in trials if t["prompt_id"] == prompt_id}
                    ):
                        pair = []
                        for model in pairs:
                            tids = {
                                t["id"]
                                for t in trials
                                if t["model"] == model
                                and t["prompt_id"] == prompt_id
                                and t["repeat_index"] == repeat
                            }
                            match = [a for a in assets if a.get("trial_id") in tids]
                            if match:
                                pair.append(match[0])
                        if len(pair) == 2:
                            task_references = [
                                a
                                for a in references
                                if not a.get("prompt_source_ids")
                                or prompts[prompt_id]["source_id"] in a["prompt_source_ids"]
                            ]
                            judge(
                                store,
                                experiment_id,
                                pair,
                                prompts[prompt_id]["text"],
                                judge_config,
                                task_references,
                            )
        state = (
            "cancelled"
            if store.job(experiment_id)["cancel"]
            else "partial"
            if limit is not None
            else "complete"
        )
        return {**store.job(experiment_id, state=state), "resume_warnings": resume_warnings}
    except Exception as exc:
        store.job(experiment_id, state="failed", error=str(exc))
        raise
    finally:
        fcntl.flock(process_lock.fileno(), fcntl.LOCK_UN)
        process_lock.close()
        lock.release()
