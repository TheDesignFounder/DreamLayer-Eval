import copy
from collections import Counter

import pytest
from PIL import Image

from research import analysis, bundles, comparison, experiments, judges, metrics
from research.api import create_app
from research.composition import evaluate_criteria, interpret
from research.contracts import digest
from research.store import Store


def fixture(tmp_path, missing=False, duplicates=False):
    config = {
        "schema_version": 1,
        "name": "Follow-up fixture",
        "models": ["a", "b"],
        "prompts": [{"id": "p", "text": "two dogs", "group_id": "p", "split": "exploratory"}],
        "assets": [],
        "metrics": [{"id": "pixel_luminance"}],
    }
    for i, model in enumerate(config["models"]):
        path = tmp_path / f"{model}.png"
        if not (missing and i == 1):
            Image.new("RGB", (20, 20), (0 if duplicates else i * 100, 10, 20)).save(path)
        config["assets"].append({"path": str(path), "prompt_id": "p", "model": model})
    store = Store(tmp_path / "study.sqlite3")
    exp = experiments.create(store, config, tmp_path / "media")
    return store, exp["id"], config


def test_resume_preserves_old_evaluator_and_upgrade_supersedes(tmp_path, monkeypatch):
    store, eid, _ = fixture(tmp_path)
    original = metrics.REGISTRY["pixel_luminance"]["version"]
    with monkeypatch.context() as old:
        old.setitem(metrics.REGISTRY["pixel_luminance"], "version", "old-fixture")
        experiments.execute(store, eid, tmp_path / "media")
    before = copy.deepcopy(store.list("result", eid))
    summary = analysis.summarize(store, eid)
    with monkeypatch.context() as forbidden:
        forbidden.setattr(
            experiments,
            "evaluate",
            lambda *a, **kw: pytest.fail("Plain resume must not re-evaluate an older version"),
        )
        job = experiments.execute(store, eid, tmp_path / "media")
    assert job["resume_warnings"][0]["action"] == "preserve_recorded_results"
    assert store.list("result", eid) == before and analysis.summarize(store, eid) == summary
    plan = experiments.plan(store, eid)
    assert (
        next(w for w in plan["warnings"] if w.get("kind") == "evaluator_version_change")[
            "available_version"
        ]
        == original
    )
    upgraded = experiments.execute(store, eid, tmp_path / "media", upgrade_evaluators=True)
    assert upgraded["resume_warnings"][0]["action"] == "reevaluate_and_supersede"
    results = store.list("result", eid)
    current = analysis.current_results(results)
    assert len(results) == 4 and len(current) == 2
    assert all(
        r["metric_version"] == original and r["evaluation_attempt"] == 2 and r["supersedes_ids"]
        for r in current
    )
    assert [store.get(r["id"]) for r in before] == before
    stable = analysis.summarize(store, eid)
    bundles.export_bundle(store, eid, tmp_path / "upgraded.zip")
    replay = Store(tmp_path / "replayed.sqlite3")
    bundles.import_bundle(replay, tmp_path / "upgraded.zip", tmp_path / "replay-media")
    experiments.execute(replay, eid, tmp_path / "replay-media")
    assert analysis.summarize(replay, eid) == stable and len(replay.list("result", eid)) == 4


def test_explicit_upgrade_resolves_preexisting_duplicate_versions(tmp_path, monkeypatch):
    store, eid, _ = fixture(tmp_path)
    with monkeypatch.context() as old:
        old.setitem(metrics.REGISTRY["pixel_luminance"], "version", "old")
        experiments.execute(store, eid, tmp_path / "media")
    # Reproduce the first remediation's unlinked old/new result groups.
    for asset in store.list("asset", eid):
        result = metrics.evaluate("pixel_luminance", [asset], experiment_id=eid)
        result["trial_id"] = asset["trial_id"]
        store.cache("unlinked-" + asset["id"], result)
    assert len(analysis.current_results(store.list("result", eid))) == 4
    experiments.execute(store, eid, tmp_path / "media", upgrade_evaluators=True)
    current = analysis.current_results(store.list("result", eid))
    assert len(current) == 2 and all(len(r["supersedes_ids"]) == 2 for r in current)


def test_fid_cache_change_has_its_own_version(tmp_path, monkeypatch):
    store, _, config = fixture(tmp_path)
    config["metrics"] = [{"id": "fid"}]
    eid = experiments.create(store, config, tmp_path / "media")["id"]
    assert metrics.REGISTRY["fid"]["version"] == "1.1.0"
    with monkeypatch.context() as old:
        old.setitem(metrics.REGISTRY["fid"], "version", "1.0.0")
        experiments.execute(store, eid, tmp_path / "media")
    before = len(store.list("result", eid))
    with monkeypatch.context() as forbidden:
        forbidden.setattr(
            experiments, "evaluate", lambda *a, **kw: pytest.fail("Unexpected FID extraction")
        )
        experiments.execute(store, eid, tmp_path / "media")
    assert len(store.list("result", eid)) == before
    experiments.execute(store, eid, tmp_path / "media", upgrade_evaluators=True)
    assert all(
        r["metric_version"] == "1.1.0" and r["supersedes"]
        for r in analysis.current_results(store.list("result", eid))
    )


def test_paired_metrics_include_unannotated_and_missing_outputs(tmp_path):
    store, eid, _ = fixture(tmp_path, missing=True)
    before = comparison.analysis_input(store, eid, "paired")
    assert Counter(r["status"] for r in before) == {"not_evaluated": 1, "missing_output": 1}
    experiments.execute(store, eid, tmp_path / "media")
    rows = comparison.analysis_input(store, eid, "paired")
    assert len(rows) == 2 and not store.list("annotation", eid)
    assert analysis.paired_difference(rows, "a", "b")["excluded_unpaired_or_missing"] == 1
    with pytest.raises(ValueError, match="human-label filters"):
        comparison.analysis_input(store, eid, "paired", filters={"rater_id": "rater"})
    client = create_app(store.path, tmp_path / "media").test_client()
    assert (
        len(
            client.post(
                f"/api/research/experiments/{eid}/analysis-input/paired", json={}
            ).get_json()
        )
        == 2
    )


def test_paired_metrics_without_annotations_can_compare_models(tmp_path):
    store, eid, _ = fixture(tmp_path)
    experiments.execute(store, eid, tmp_path / "media")
    rows = comparison.analysis_input(store, eid, "paired")
    assert len(rows) == 2 and analysis.paired_difference(rows, "a", "b")["paired_tasks"] == 1


def test_pairwise_plan_counts_units_and_imported_repeat_indices(tmp_path):
    store, _, config = fixture(tmp_path)
    config["judges"] = [
        {
            "provider": "synthetic",
            "model": "fixture",
            "mode": "pairwise",
            "rubric": {"version": "1", "criteria": [{"id": "task", "description": "task"}]},
        }
    ]
    config["metrics"] = []
    for asset in config["assets"]:
        asset["repeat_index"] = 7
    eid = experiments.create(store, config, tmp_path / "media")["id"]
    assert experiments.plan(store, eid)["maximum_judge_calls"] == 2
    experiments.execute(store, eid, tmp_path / "media")
    assert len([r for r in store.list("judge_call", eid) if r["phase"] == "request"]) == 1
    config["assets"] = config["assets"][:1]
    incomplete = experiments.create(store, config, tmp_path / "media")["id"]
    assert experiments.plan(store, incomplete)["maximum_judge_calls"] == 0
    config["judges"][0].update(protocol="two_pass", budget={"calls": 3})
    assert (
        experiments.judge_units(
            [{"prompt_id": "p", "repeat_index": 7, "model": m} for m in ["a", "b", "c"]],
            config,
            config["judges"][0],
        )
        == 1
    )


@pytest.mark.parametrize("text", ["2 of the dogs", "two of those dogs", "two of three dogs"])
def test_nonadjacent_counts_never_degrade_to_presence(text):
    criterion = interpret(text)["criteria"][0]
    assert criterion["kind"] == "unsupported" and criterion["count_mode"] == "unresolved"
    assert criterion["minimum"] is None and criterion["maximum"] is None


def test_unknown_detector_vocabulary_does_not_assert_absence():
    criteria = interpret("a dog")["criteria"]
    for vocabulary in (None, []):
        result = evaluate_criteria(criteria, [], vocabulary=vocabulary)
        assert result["score"] is None and result["criteria"][0]["label"] == "uncertain"
        assert "detected" not in result["criteria"][0]
    assert evaluate_criteria(criteria, [], vocabulary=["dog"])["score"] == 0


def test_legacy_content_collision_is_recorded_without_calls(tmp_path, monkeypatch):
    store, eid, _ = fixture(tmp_path, duplicates=True)
    assets = store.list("asset", eid)
    rubric = {"version": "1", "criteria": [{"id": "task", "description": "task"}]}
    config = {
        "provider": "synthetic",
        "model": "old-fixture",
        "mode": "pointwise",
        "rubric": rubric,
        "synthetic_response": {
            "labels": {"task": "pass"},
            "explanation": "Legacy synthetic evidence",
            "evidence": [],
        },
    }
    judges.judge(store, eid, assets[:1], "two dogs", config)
    key = digest(
        {
            "assets": [assets[0]["sha256"]],
            "references": [],
            "prompt": "two dogs",
            "config": config,
            "experiment_id": eid,
        }
    )
    legacy = Store(tmp_path / "legacy.sqlite3")
    for row in store.list(experiment_id=eid):
        if row["kind"] == "experiment":
            row["config"]["judges"] = [config]
            row["config_hash"] = digest(row["config"])
        if row["kind"] == "judge_call":
            row["protocol_key"] = key
            row.pop("order_policy", None)
            row.pop("implementation_version", None)
        legacy.put(row)
    with monkeypatch.context() as forbidden:
        forbidden.setattr(
            judges,
            "call_adapter",
            lambda *a, **kw: pytest.fail("Legacy duplicate must not re-spend"),
        )
        assert experiments.execute(legacy, eid, tmp_path / "media")["state"] == "complete"
        assert experiments.execute(legacy, eid, tmp_path / "media")["state"] == "complete"
    assert len(legacy.list("judge_call", eid)) == 2
    warnings = analysis.summarize(legacy, eid)["judge_provenance_warnings"]
    assert len(warnings) == 1 and warnings[0]["asset_ids"] == [assets[1]["id"]]
    assert warnings[0]["legacy_asset_ids"] == [assets[0]["id"]]
