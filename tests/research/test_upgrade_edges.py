"""Legacy evaluator identity and retries must not silently merge configurations."""

import copy
from pathlib import Path

import pytest
from PIL import Image

from research import analysis, bundles, experiments, metrics, upgrades
from research.contracts import digest, file_hash
from research.store import Store


def study(tmp_path, configured):
    paths = []
    for i in range(4):
        path = tmp_path / f"image-{i}.png"
        Image.new("RGB", (16, 16), (i * 50, 10, 20)).save(path)
        paths.append(path)
    config = {
        "schema_version": 1,
        "name": "Upgrade edge fixture",
        "models": ["m"],
        "prompts": [{"id": str(i), "text": "two cars", "group_id": str(i)} for i in range(2)],
        "assets": [
            {"path": str(p), "prompt_id": str(i), "model": "m"} for i, p in enumerate(paths[:2])
        ],
        "references": [{"path": str(p)} for p in paths[2:]],
        "metrics": configured,
    }
    store = Store(tmp_path / "study.sqlite3")
    eid = experiments.create(store, config, tmp_path / "media")["id"]
    return store, eid


def legacy_run(
    monkeypatch, store, eid, root, status="success", raw_settings=False, failed_setting=None
):
    """Write historical-shaped rows, omitting the later configured-metric hash."""
    configured = store.get(eid)["config"]["metrics"]

    def evaluator(metric_id, assets, prompt="", config=None, references=(), experiment_id=None):
        settings = dict(config or {})
        if not raw_settings:
            settings = metrics.evaluator_config(metric_id, settings)
        state = (
            status
            if failed_setting is None or config.get("threshold") == failed_setting
            else "success"
        )
        out = metrics.result(
            metric_id,
            assets,
            experiment_id,
            settings,
            status=state,
            score=0.5 if state == "success" else None,
            reason=None if state == "success" else "Deliberate old evaluator failure",
        )
        out["reference_hash"] = metrics.membership(references) if references else None
        if config.get("weights") and Path(config["weights"]).is_file():
            out["details"] = {"detector": {"weights_sha256": file_hash(config["weights"])}}
        return out

    with monkeypatch.context() as old:
        for metric_id in {m["id"] for m in configured}:
            old.setitem(metrics.REGISTRY[metric_id], "version", "legacy-fixture")
        old.setattr(experiments, "evaluate", evaluator)
        old.setattr(upgrades, "annotate", lambda output, *args, **kwargs: output)
        experiments.execute(store, eid, root)
    return copy.deepcopy(store.list("result", eid))


@pytest.mark.parametrize("metric_id", ["pixel_luminance", "fid"])
@pytest.mark.parametrize("status", ["failed_evaluation", "unavailable_dependency"])
def test_rerun_failed_alone_crosses_version_for_all_failed_unit(
    tmp_path, monkeypatch, metric_id, status
):
    store, eid = study(tmp_path, [{"id": metric_id}])
    before = legacy_run(monkeypatch, store, eid, tmp_path / "media", status=status)

    def healthy(metric, assets, prompt="", config=None, references=(), experiment_id=None):
        out = metrics.result(
            metric,
            assets,
            experiment_id,
            metrics.evaluator_config(metric, config or {}),
            status="success",
            score=0.75,
            reason=None,
        )
        out["reference_hash"] = metrics.membership(references) if references else None
        return out

    monkeypatch.setattr(experiments, "evaluate", healthy)
    job = experiments.execute(store, eid, tmp_path / "media", rerun_failed=True)
    assert job["resume_warnings"][0]["action"] == "retry_failed_units"
    current = analysis.current_results(store.list("result", eid))
    assert len(current) == len(before) and all(
        r["status"] == "success" and r["evaluation_attempt"] == 2 for r in current
    )
    assert {x for r in current for x in r["supersedes_ids"]} == {r["id"] for r in before}
    assert all("Explicit retry" in r["upgrade_reason"] for r in current)
    assert [store.get(r["id"]) for r in before] == before
    bundles.export_bundle(store, eid, tmp_path / "retry.zip")
    replay = Store(tmp_path / "replay.sqlite3")
    bundles.import_bundle(replay, tmp_path / "retry.zip", tmp_path / "replay-media")
    expected = analysis.summarize(store, eid)
    monkeypatch.setattr(
        experiments,
        "evaluate",
        lambda *a, **k: pytest.fail("Resume must use the new successful results"),
    )
    experiments.execute(replay, eid, tmp_path / "replay-media", rerun_failed=True)
    assert analysis.summarize(replay, eid) == expected


@pytest.mark.parametrize("raw_settings", [False, True])
def test_legacy_duplicate_ids_match_thresholds_and_frozen_criteria(
    tmp_path, monkeypatch, raw_settings
):
    weights = tmp_path / "detector.pt"
    weights.write_bytes(b"fixture weights")
    configured = [
        {"id": "object_criteria", "weights": str(weights), "threshold": threshold}
        for threshold in [0.2, 0.8]
    ]
    store, eid = study(tmp_path, configured)
    before = legacy_run(monkeypatch, store, eid, tmp_path / "media", raw_settings=raw_settings)
    assert len(before) == 4 and all("configured_metric_hash" not in r for r in before)
    # A changed current file must not destroy a match to the recorded old hash.
    weights.write_bytes(b"updated fixture weights")
    monkeypatch.setattr(
        experiments,
        "evaluate",
        lambda *a, **k: pytest.fail("Plain resume must preserve each legacy configuration"),
    )
    experiments.execute(store, eid, tmp_path / "media")
    assert store.list("result", eid) == before
    assert not any(
        w.get("kind") == "unresolved_legacy_metric_settings"
        for w in experiments.plan(store, eid)["warnings"]
    )
    for asset in [a for a in store.list("asset", eid) if a.get("trial_id")]:
        refs = [a for a in store.list("asset", eid) if not a.get("trial_id")]
        matches = [
            upgrades.previous_results(store, eid, m, [asset], refs, trial_id=asset["trial_id"])
            for m in configured
        ]
        assert (
            all(len(rows) == 1 for rows in matches) and matches[0][0]["id"] != matches[1][0]["id"]
        )


def test_distinct_weight_paths_preserved_after_files_removed(tmp_path, monkeypatch):
    paths = [tmp_path / "one.pt", tmp_path / "two.pt"]
    for path in paths:
        path.write_bytes(path.name.encode())
    store, eid = study(tmp_path, [{"id": "object_criteria", "weights": str(p)} for p in paths])
    before = legacy_run(monkeypatch, store, eid, tmp_path / "media")
    for path in paths:
        path.unlink()
    monkeypatch.setattr(
        experiments,
        "evaluate",
        lambda *a, **k: pytest.fail("Unavailable old weights do not authorize re-evaluation"),
    )
    experiments.execute(store, eid, tmp_path / "media")
    assert store.list("result", eid) == before


def test_retry_only_failed_config_leaves_other_success_unchanged(tmp_path, monkeypatch):
    configured = [{"id": "pixel_luminance", "threshold": t} for t in [0.2, 0.8]]
    store, eid = study(tmp_path, configured)
    before = legacy_run(
        monkeypatch, store, eid, tmp_path / "media", status="failed_evaluation", failed_setting=0.2
    )
    successful = [r for r in before if r["status"] == "success"]
    failed = [r for r in before if r["status"] != "success"]
    job = experiments.execute(store, eid, tmp_path / "media", rerun_failed=True)
    assert job["resume_warnings"][0]["action"] == "retry_failed_units"
    current = analysis.current_results(store.list("result", eid))
    assert len(current) == 4 and all(r in current for r in successful)
    assert {r["supersedes"] for r in current if r.get("supersedes")} == {r["id"] for r in failed}
    assert all(
        r["configured_metric_hash"] == digest(configured[0]) for r in current if r.get("supersedes")
    )


def test_mixed_terminal_and_failed_unit_requires_explicit_upgrade(tmp_path, monkeypatch):
    store, eid = study(tmp_path, [{"id": "pixel_luminance"}])
    before = legacy_run(monkeypatch, store, eid, tmp_path / "media")
    old = before[0]
    failed = {
        **old,
        "id": "additional-old-failure",
        "status": "failed_evaluation",
        "score": None,
        "reason": "Legacy failure",
        "created_at": "2090-01-01T00:00:00+00:00",
    }
    store.put(failed)
    monkeypatch.setattr(
        experiments,
        "evaluate",
        lambda *a, **k: pytest.fail(
            "A terminal old result protects the unit from implicit upgrade"
        ),
    )
    experiments.execute(store, eid, tmp_path / "media", rerun_failed=True)
    assert len(store.list("result", eid)) == 3


def test_ambiguous_legacy_provenance_is_preserved_with_warning(tmp_path, monkeypatch):
    store, eid = study(
        tmp_path,
        [{"id": "pixel_luminance", "threshold": 0.2}, {"id": "pixel_luminance", "threshold": 0.8}],
    )
    before = legacy_run(monkeypatch, store, eid, tmp_path / "media")
    # Simulate a historical fingerprint whose settings cannot be reconstructed.
    legacy = Store(tmp_path / "ambiguous.sqlite3")
    for row in store.list(experiment_id=eid):
        if row["kind"] == "result":
            row["preprocessing_hash"] = digest("unrecoverable legacy settings")
        legacy.put(row)
    monkeypatch.setattr(
        experiments,
        "evaluate",
        lambda *a, **k: pytest.fail("Ambiguous settings must never trigger hidden work"),
    )
    for flags in ({}, {"rerun_failed": True}, {"upgrade_evaluators": True}):
        job = experiments.execute(legacy, eid, tmp_path / "media", **flags)
        assert job["state"] == "complete" and len(legacy.list("result", eid)) == len(before)
        warning = next(
            w for w in job["resume_warnings"] if w["kind"] == "unresolved_legacy_metric_settings"
        )
        assert (
            warning["action"] == "preserve_unresolved_units"
            and len(warning["possible_configuration_hashes"]) == 2
        )


def test_dataset_duplicate_settings_match_legacy_fingerprints(tmp_path, monkeypatch):
    store, eid = study(tmp_path, [{"id": "fid", "device": "cpu"}, {"id": "fid", "device": "cuda"}])
    before = legacy_run(monkeypatch, store, eid, tmp_path / "media")
    monkeypatch.setattr(
        experiments,
        "evaluate",
        lambda *a, **k: pytest.fail("Duplicate dataset evaluator settings must be preserved"),
    )
    experiments.execute(store, eid, tmp_path / "media")
    assert len(before) == 2 and store.list("result", eid) == before


def test_explicit_upgrade_supersedes_only_matching_legacy_configuration(tmp_path, monkeypatch):
    configured = [{"id": "pixel_luminance", "threshold": t} for t in [0.2, 0.8]]
    store, eid = study(tmp_path, configured)
    before = legacy_run(monkeypatch, store, eid, tmp_path / "media")
    experiments.execute(store, eid, tmp_path / "media", upgrade_evaluators=True)
    current = analysis.current_results(store.list("result", eid))
    assert len(current) == 4 and len(store.list("result", eid)) == 8
    for row in current:
        old = next(r for r in before if r["id"] == row["supersedes"])
        assert row["supersedes_ids"] == [old["id"]]
        assert row["preprocessing_hash"] == old["preprocessing_hash"]
        assert row["trial_id"] == old["trial_id"]
    monkeypatch.setattr(
        experiments, "evaluate", lambda *a, **k: pytest.fail("Upgraded results must be cached")
    )
    experiments.execute(store, eid, tmp_path / "media")
    assert len(store.list("result", eid)) == 8


def test_api_rerun_failed_warning_matches_executed_recovery(tmp_path, monkeypatch):
    import time

    from research.api import create_app

    store, eid = study(tmp_path, [{"id": "pixel_luminance"}])
    before = legacy_run(monkeypatch, store, eid, tmp_path / "media", status="failed_evaluation")
    app = create_app(tmp_path / "study.sqlite3", tmp_path / "media")
    response = app.test_client().post(
        f"/api/research/experiments/{eid}/run", json={"rerun_failed": True}
    )
    assert response.status_code == 202
    warning = response.json["resume_warnings"][0]
    assert warning["action"] == "retry_failed_units" and "available version" in warning["message"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if len(store.list("result", eid)) == 4 and store.job(eid)["state"] == "complete":
            break
        time.sleep(0.01)
    current = analysis.current_results(store.list("result", eid))
    assert len(current) == 2 and all(r["status"] == "success" for r in current)
    assert {r["supersedes"] for r in current} == {r["id"] for r in before}


@pytest.mark.parametrize("metric_id", ["pixel_luminance", "fid"])
@pytest.mark.parametrize("failure", ["missing_dependency", "model_load_error"])
@pytest.mark.parametrize("rerun_failed", [False, True])
def test_unrunnable_upgrade_keeps_success_and_can_recover(
    tmp_path, monkeypatch, metric_id, failure, rerun_failed
):
    from research import fid

    store, eid = study(tmp_path, [{"id": metric_id}])
    before = legacy_run(monkeypatch, store, eid, tmp_path / "media")
    expected = analysis.summarize(store, eid)

    def broken(*args, **kwargs):
        raise OSError("Fixture model weights cannot load")

    with monkeypatch.context() as unavailable:
        unavailable.setattr(
            metrics,
            "dependencies",
            lambda _: ["fixture_missing_module"] if failure == "missing_dependency" else [],
        )
        if failure == "model_load_error":
            if metric_id == "fid":
                unavailable.setattr(fid, "calculate", broken)
            else:
                unavailable.setattr(metrics.media, "image_evidence", broken)
        with pytest.raises(ValueError, match="Successful recorded results remain current"):
            experiments.execute(
                store,
                eid,
                tmp_path / "media",
                upgrade_evaluators=True,
                rerun_failed=rerun_failed,
            )
    assert store.job(eid)["state"] == "failed"
    assert metric_id in store.job(eid)["error"]
    assert store.list("result", eid) == before
    assert analysis.summarize(store, eid) == expected

    bundles.export_bundle(store, eid, tmp_path / "blocked.zip")
    replay = Store(tmp_path / "blocked-replay.sqlite3")
    bundles.import_bundle(replay, tmp_path / "blocked.zip", tmp_path / "replay-media")
    with monkeypatch.context() as preserved:
        preserved.setattr(
            experiments, "evaluate", lambda *a, **k: pytest.fail("Resume must retain old success")
        )
        experiments.execute(replay, eid, tmp_path / "replay-media")
    assert analysis.summarize(replay, eid) == expected
    assert replay.list("result", eid) == before

    # Provisioning the evaluator permits an explicit upgrade; the blocked attempt
    # must not have poisoned its cache or introduced a current null result.
    monkeypatch.setattr(metrics, "dependencies", lambda _: [])
    if metric_id == "fid":
        monkeypatch.setattr(fid, "calculate", lambda *a, **k: (0.25, {"fixture": True}))
    experiments.execute(store, eid, tmp_path / "media", upgrade_evaluators=True)
    current = analysis.current_results(store.list("result", eid))
    assert len(current) == len(before) and all(r["status"] == "success" for r in current)
    assert {i for r in current for i in r["supersedes_ids"]} == {r["id"] for r in before}


def test_api_upgrade_warning_and_durable_error_preserve_success(tmp_path, monkeypatch):
    import time

    from research.api import create_app

    store, eid = study(tmp_path, [{"id": "pixel_luminance"}])
    before = legacy_run(monkeypatch, store, eid, tmp_path / "media")
    monkeypatch.setattr(metrics, "dependencies", lambda _: ["fixture_missing_module"])
    client = create_app(store.path, tmp_path / "media").test_client()
    response = client.post(
        f"/api/research/experiments/{eid}/run", json={"upgrade_evaluators": True}
    )
    assert response.status_code == 202
    assert "will not replace successful results" in response.json["resume_warnings"][0]["message"]
    deadline = time.monotonic() + 5
    while store.job(eid)["state"] != "failed" and time.monotonic() < deadline:
        time.sleep(0.01)
    detail = client.get(f"/api/research/experiments/{eid}").json
    assert detail["job"]["state"] == "failed"
    assert "Successful recorded results remain current" in detail["job"]["error"]
    assert store.list("result", eid) == before


def test_cli_upgrade_unavailable_detector_preserves_success(tmp_path, monkeypatch):
    import subprocess
    import sys

    store, eid = study(
        tmp_path, [{"id": "object_criteria", "weights": str(tmp_path / "missing.pt")}]
    )
    before = legacy_run(monkeypatch, store, eid, tmp_path / "media")
    response = subprocess.run(
        [
            sys.executable,
            "-m",
            "research",
            "--db",
            str(store.path),
            "run",
            eid,
            "--upgrade-evaluators",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert response.returncode == 1
    assert response.stdout == ""
    assert "Traceback" not in response.stderr
    errors = [line for line in response.stderr.splitlines() if line.startswith("error:")]
    assert len(errors) == 1
    assert errors[0] == "error: " + " ".join(store.job(eid)["error"].split())
    assert "will not replace successful results" in response.stderr
    assert "Successful recorded results remain current" in response.stderr
    assert store.job(eid)["state"] == "failed"
    assert store.list("result", eid) == before
