import copy
import json
import subprocess
import threading
import time
from fractions import Fraction
from pathlib import Path

import av
import pytest
from PIL import Image

from research import analysis, bundles, experiments, human, judges, media, metrics
from research.composition import COCO, evaluate_criteria, interpret
from research.contracts import digest, record
from research.generation import generate, resolve_workflow
from research.store import Store


def setup(tmp_path, fixture_media):
    store = Store(tmp_path / "db.sqlite3")
    exp = experiments.create(store, copy.deepcopy(fixture_media[1]), tmp_path / "media")
    return store, exp["id"]


def test_criteria_range():
    criteria = interpret("Between two and four dogs")["criteria"]
    assert criteria[0]["count_mode"] == "range"
    assert evaluate_criteria(criteria, [{"class_name": "dog"}] * 3, vocabulary=COCO)["score"] == 1
    assert evaluate_criteria(criteria, [{"class_name": "dog"}] * 5, vocabulary=COCO)["score"] == 0


def test_two_pass_budget_resume_does_not_duplicate_calls(tmp_path, fixture_media):
    store, eid = setup(tmp_path, fixture_media)
    asset = next(a for a in store.list("asset", eid) if a["original_filename"] == "moving.webm")
    config = {
        "provider": "synthetic",
        "model": "fixture-v1",
        "protocol": "two_pass",
        "sparse_frames": 4,
        "dense_frames": 16,
        "budget": {"frames": 4},
        "rubric": {"version": "1", "criteria": [{"id": "task", "description": "Visible task"}]},
    }
    first = judges.judge(store, eid, [asset], "prompt", config)
    assert first["reason"] == "budget_stop"
    calls = store.list("judge_call", eid)
    assert len(calls) == 2
    config["budget"]["frames"] = 20
    second = judges.judge(store, eid, [asset], "prompt", config)
    assert second["round"] == 1 and second["status"] == "abstention"
    after = store.list("judge_call", eid)
    assert len(after) == 4 and {r["id"] for r in calls}.issubset({r["id"] for r in after})


def test_reference_evidence_and_truncated_response(tmp_path, fixture_media):
    store, eid = setup(tmp_path, fixture_media)
    assets = [a for a in store.list("asset", eid) if a["media"]["modality"] == "image"]
    config = {
        "provider": "synthetic",
        "model": "fixture-v1",
        "rubric": {"version": "1", "criteria": [{"id": "task", "description": "Task"}]},
    }
    result = judges.judge(store, eid, assets[:1], "prompt", config, references=assets[1:])
    assert [o["role"] for o in result["evidence"]] == ["candidate", "reference"]

    class Response:
        ok = True
        status_code = 200
        headers = {}

        def json(self):
            return {
                "status": "incomplete",
                "output": [{"content": [{"type": "output_text", "text": '{"labels":'}]}],
            }

    response = judges.call_adapter(
        "openai", "explicit", {}, "url", transport=lambda *a, **kw: Response()
    )
    assert response["reason"] == "truncated_output"


def test_content_and_weights_invalidate_cache(tmp_path, fixture_media):
    store, eid = setup(tmp_path, fixture_media)
    asset = store.list("asset", eid)[0]
    weights = tmp_path / "weights.bin"
    weights.write_bytes(b"first")
    first = metrics.cache_key("object_criteria", [asset], "prompt", {"weights": str(weights)})
    weights.write_bytes(b"second")
    second = metrics.cache_key("object_criteria", [asset], "prompt", {"weights": str(weights)})
    assert first != second
    assert metrics.cache_key("pixel_luminance", [asset], "prompt", {}) != metrics.cache_key(
        "pixel_luminance", [{**asset, "sha256": "changed"}], "prompt", {}
    )


def test_cancellation_then_resume_without_duplicate_trials(tmp_path, fixture_media, monkeypatch):
    config = copy.deepcopy(fixture_media[1])
    config["concurrency"] = 1
    store = Store(tmp_path / "cancel.db")
    exp = experiments.create(store, config, tmp_path / "media")
    eid = exp["id"]
    real_evaluate = experiments.evaluate
    entered = threading.Event()

    def delayed(*args, **kwargs):
        entered.set()
        time.sleep(0.05)
        return real_evaluate(*args, **kwargs)

    monkeypatch.setattr(experiments, "evaluate", delayed)
    worker = threading.Thread(target=experiments.execute, args=(store, eid, tmp_path / "media"))
    worker.start()
    assert entered.wait(5)
    store.job(eid, cancel=1)
    worker.join(10)
    assert not worker.is_alive() and store.job(eid)["state"] == "cancelled"
    experiments.execute(store, eid, tmp_path / "media")
    assert store.job(eid)["state"] == "complete"
    assert len(store.list("trial", eid)) == 5
    results = store.list("result", eid)
    assert len({r["cache_key"] for r in results}) == len(results)


def test_vfr_timestamps_and_rotation(tmp_path, fixture_media):
    path = tmp_path / "variable.mp4"
    with av.open(str(path), "w") as output:
        stream = output.add_stream("mpeg4", rate=10)
        stream.width = 64
        stream.height = 32
        stream.pix_fmt = "yuv420p"
        for pts in [0, 1, 3, 6]:
            frame = av.VideoFrame.from_image(Image.new("RGB", (64, 32), (pts * 30, 0, 0)))
            frame.pts = pts
            frame.time_base = Fraction(1, 10)
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    frames, p = media.sample_video(path, count=4)
    assert p["timestamps"] == pytest.approx([0, 0.1, 0.3, 0.6])
    rotated = tmp_path / "rotated.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-display_rotation",
            "90",
            "-i",
            str(path),
            "-c",
            "copy",
            str(rotated),
        ],
        check=True,
    )
    frames, r = media.sample_video(rotated, count=4)
    assert frames[0].size == (32, 64)
    assert abs(r["rotation"]) == 90


def test_missing_weights_corrupt_and_empty_prompt(tmp_path, fixture_media):
    store, eid = setup(tmp_path, fixture_media)
    asset = next(a for a in store.list("asset", eid) if a["media"]["modality"] == "image")
    assert metrics.evaluate("clip_cosine", [asset], prompt="")["status"] == "not_applicable"
    result = metrics.evaluate(
        "object_criteria", [asset], prompt="two dogs", config={"weights": "missing.pt"}
    )
    assert result["status"] == "unavailable_dependency" and result["score"] is None
    damaged = {**asset, "locator": str(fixture_media[0] / "corrupt.png")}
    result = metrics.evaluate("pixel_luminance", [damaged])
    assert result["status"] == "failed_evaluation"
    assert metrics.evaluate("fid", [asset], references=[asset])["status"] == "insufficient_data"


def test_threshold_test_split_guard_and_all_abstain():
    with pytest.raises(ValueError):
        analysis.choose_threshold([{"split": "test", "score": 1, "human": "pass"}], [0.5])
    fitted = analysis.choose_threshold(
        [
            {"split": "development", "score": 0, "human": "fail"},
            {"split": "development", "score": 1, "human": "pass"},
        ],
        [0, 0.5, 1],
    )
    assert fitted["selected_threshold"] == 0.5 and not fitted["held_out_labels_used"]
    empty = analysis.choose_threshold(
        [{"split": "development", "score": None, "human": "fail"}], [0.5]
    )
    assert empty["selected_threshold"] is None


def test_generation_parameter_enforcement_is_not_fabricated():
    generation = {
        "workflow": {"1": {"inputs": {"text": "old", "seed": 0}, "class_type": "Fixture"}},
        "bindings": {"prompt": [["1", "text"]], "seed": [["1", "seed"]]},
    }
    workflow, submitted, unsupported = resolve_workflow(
        generation, {"text": "actual"}, {"seed": 0, "steps": 20}
    )
    assert workflow["1"]["inputs"]["text"] == "actual" and submitted["seed"] == 0
    assert unsupported["steps"] == 20
    assert generation["workflow"]["1"]["inputs"]["text"] == "old"


def test_actual_generation_adapter_against_local_test_transport(tmp_path, fixture_media):
    """Exercises the real adapter with an explicitly synthetic ComfyUI service contract."""
    config = {
        "schema_version": 1,
        "name": "synthetic-generation",
        "models": ["fixture"],
        "prompts": [{"id": "p", "text": "task"}],
        "metrics": [],
        "generation": {
            "allow_provider_calls": True,
            "workflow": {"1": {"class_type": "Fixture", "inputs": {"text": ""}}},
            "bindings": {"prompt": [["1", "text"]]},
            "poll_seconds": 0,
        },
    }
    store = Store(tmp_path / "generation.db")
    exp = experiments.create(store, config, tmp_path / "media")
    trial = store.list("trial", exp["id"])[0]

    class Response:
        def __init__(self, data=None, content=None):
            self.data = data
            self.content = content

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    class Transport:
        posts = 0

        def post(self, *args, **kwargs):
            self.posts += 1
            return Response({"prompt_id": "synthetic-job"})

        def get(self, url, **kwargs):
            if "/history/" in url:
                return Response(
                    {
                        "synthetic-job": {
                            "outputs": {
                                "2": {
                                    "images": [
                                        {
                                            "filename": "fixture.png",
                                            "type": "output",
                                            "subfolder": "",
                                        }
                                    ]
                                }
                            }
                        }
                    }
                )
            return Response(content=(fixture_media[0] / "zero café.png").read_bytes())

    transport = Transport()
    output = generate(
        store,
        exp["id"],
        trial,
        store.get(trial["prompt_id"]),
        tmp_path / "media",
        transport=transport,
    )
    assert output["status"] == "success" and output["provider_request_id"] == "synthetic-job"
    assert (
        output["accepted_parameters"] == {} and output["unverified_parameters"]["prompt"] == "task"
    )
    generate(
        store,
        exp["id"],
        trial,
        store.get(trial["prompt_id"]),
        tmp_path / "media",
        transport=transport,
    )
    assert transport.posts == 1


def test_legacy_zero_and_negative_aggregation(monkeypatch):
    from dream_layer_backend.dream_layer_backend_utils.clip_score_metrics import ClipScoreCalculator

    calculator = ClipScoreCalculator()
    values = iter([0, -0.5, None])
    monkeypatch.setattr(calculator, "compute_clip_score", lambda *args: next(values))
    result = calculator.compute_metrics_for_batch("prompt", ["a", "b", "c"])
    assert result["clip_score_mean"] == -0.25 and result["clip_score_max"] == 0


def test_report_schema_roundtrip_missing_and_zero(tmp_path):
    from dream_layer_backend.dream_layer_backend_utils.report_schema import (
        ReportDataManager,
        RunMetrics,
    )

    manager = ReportDataManager(str(tmp_path))
    rows = [
        RunMetrics("zero", clip_score_mean=0, status="success", reason=""),
        RunMetrics("missing"),
    ]
    manager.save_run_metrics(rows)
    restored = manager.load_run_metrics()
    assert restored[0].clip_score_mean == 0 and restored[1].clip_score_mean is None
    assert restored[0].status == "success" and restored[1].status == "not_evaluated"


def test_annotations_invalid_duplicate_import_rejected(tmp_path, fixture_media):
    store, eid = setup(tmp_path, fixture_media)
    rubric = {"version": "1", "criteria": [{"id": "task", "description": "Task"}]}
    assignment = human.assign(store, eid, "rater", rubric)[0]
    annotation = human.annotate(
        store, assignment["id"], {"rater_id": "rater", "labels": {"task": "pass"}}
    )
    with pytest.raises(ValueError):
        human.import_annotations(store, json.dumps({**annotation, "id": "another"}))
    with pytest.raises(ValueError):
        human.import_annotations(store, json.dumps({**annotation, "labels": {"task": "A"}}))


def test_blind_video_duration_and_practice_validation(tmp_path, fixture_media):
    store, eid = setup(tmp_path, fixture_media)
    rubric = {"version": "1", "criteria": [{"id": "task", "description": "Motion"}]}
    assignments = human.assign(store, eid, "r", rubric, practice=["video"])
    a = next(a for a in assignments if store.get(a["asset_ids"][0])["media"]["modality"] == "video")
    assert a["practice"]
    duration = store.get(a["asset_ids"][0])["media"]["duration"]
    assert duration is not None
    with pytest.raises(ValueError, match="duration"):
        human.annotate(
            store,
            a["id"],
            {"rater_id": "r", "labels": {"task": "fail"}, "intervals": [[0, duration + 1]]},
        )


def test_legacy_composition_versions_preserve_raw_history(tmp_path, fixture_media):
    from dream_layer_backend.data.scripts.database import DreamLayerDB
    from research.legacy import composition

    db = DreamLayerDB(str(tmp_path / "legacy.db"))
    path = fixture_media[0] / "zero café.png"
    first = {
        "object_criteria_result": {"status": "success", "score": 0, "reason": None},
        "target_objects": [],
        "criterion_pass_rate": 0,
    }
    assert db.upsert_composition_metrics("legacy-run", "now", "task", str(path), first)
    second = {
        **first,
        "object_criteria_result": {
            "status": "unavailable_dependency",
            "score": None,
            "reason": "weights missing",
        },
        "criterion_pass_rate": None,
    }
    assert db.upsert_composition_metrics("legacy-run", "later", "task", str(path), second)
    assert len(Store(db.db_path).list("result")) == 2
    with db.get_connection() as conn:
        assert composition(conn, "legacy-run")["criterion_pass_rate"] is None


def test_unfinished_judge_claim_survives_portable_import(tmp_path, fixture_media):
    store, eid = setup(tmp_path, fixture_media)
    # An interrupted request has no response. Copying its experiment must not make
    # the same potentially paid delivery eligible for automatic resubmission.
    key = digest("unknown delivery")
    store.claim(key)
    store.put(record("judge_call", eid, phase="request", request_key=key))
    bundle = bundles.export_bundle(store, eid, tmp_path / "claim.zip")
    destination = Store(tmp_path / "fresh.db")
    bundles.import_bundle(destination, bundle, tmp_path / "fresh-media")
    assert destination.claim(key) is False


def test_recorded_donut_and_hydrant_interpretation():
    donuts = interpret("A man preparing donuts")["criteria"]
    assert next(c for c in donuts if c["entity"] == "donut")["maximum"] is None
    counts = [{"class_name": "person"}] + [{"class_name": "donut"}] * 47
    assert evaluate_criteria(donuts, counts, vocabulary=COCO)["score"] == 1
    task = interpret("A dog sniffs the base of a fire hydrant")
    result = evaluate_criteria(
        task["criteria"], [{"class_name": "dog"}, {"class_name": "fire hydrant"}], vocabulary=COCO
    )
    assert result["score"] == 1 and "actions" in task["unsupported"]


def test_real_legacy_image_route_uses_shared_metrics_for_unicode_path(
    tmp_path, fixture_media, monkeypatch
):
    import sys
    from urllib.parse import quote

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dream_layer_backend"))
    monkeypatch.setenv("DREAMLAYER_RESEARCH_DB", str(tmp_path / "route.db"))
    import dream_layer

    monkeypatch.setattr(
        dream_layer, "get_directories", lambda: (str(fixture_media[0]), str(tmp_path / "input"))
    )
    client = dream_layer.app.test_client()
    assert client.get("/api/research/health").json["schema_version"] == 1
    response = client.post(
        "/api/calculate-metrics",
        json={"image_url": "http://localhost/api/images/" + quote("zero café.png"), "prompt": ""},
    )
    assert response.status_code == 200
    values = response.json["metrics"]
    assert values["pixel_luminance"] == 0
    assert values["fid_score"] is None and values["fid_status"] == "not_applicable"
    assert values["clip_score_mean"] is None
    assert values["object_criteria_result"]["status"] == "not_applicable"
    assert client.get("/api/image-metrics-cache/zero.png").status_code == 404


def test_prompt_specific_references_follow_metrics_judges_and_humans(tmp_path, fixture_media):
    config = copy.deepcopy(fixture_media[1])
    config["references"] = [
        {"path": str(fixture_media[0] / "two circles.png"), "prompt_ids": ["image"]}
    ]
    store = Store(tmp_path / "refs.db")
    exp = experiments.create(store, config, tmp_path / "media")
    eid = exp["id"]
    experiments.execute(store, eid, tmp_path / "media")
    prompts = {p["id"]: p for p in store.list("prompt", eid)}
    trials = {t["id"]: t for t in store.list("trial", eid)}
    for result in store.list("result", eid):
        if result.get("trial_id"):
            source = prompts[trials[result["trial_id"]]["prompt_id"]]["source_id"]
            assert bool(result["reference_hash"]) == (source == "image")
    rubric = {"version": "1", "criteria": [{"id": "task", "description": "Task"}]}
    for assignment in human.assign(store, eid, "r", rubric):
        asset = store.get(assignment["asset_ids"][0])
        source = prompts[trials[asset["trial_id"]]["prompt_id"]]["source_id"]
        assert bool(assignment["reference_ids"]) == (source == "image")
    for call in store.list("judge_call", eid):
        candidate = next(o for o in call["evidence"] if o["role"] == "candidate")
        modality = store.get(candidate["asset_id"])["media"]["modality"]
        assert any(o["role"] == "reference" for o in call["evidence"]) == (modality == "image")
