import copy
import json
from collections import Counter
from datetime import UTC
from pathlib import Path

import pytest
import requests
from PIL import Image

from research import analysis, bundles, comparison, experiments, human, judges, media, metrics
from research.api import create_app
from research.composition import interpret
from research.contracts import file_hash, record
from research.pricing import estimate
from research.store import Store

RUBRIC = {
    "version": "review-1",
    "criteria": [{"id": "task", "description": "Visible task fulfillment"}],
}
VERDICT = {"labels": {"task": "pass"}, "explanation": "Fixture response", "evidence": []}


def setup(tmp_path, pairs=1, metric=True):
    assets = []
    for n in range(pairs):
        for i, model in enumerate(("a", "b")):
            path = tmp_path / f"{n}-{model}.png"
            Image.new("RGB", (24, 24), (n + i * 80, 30, 40)).save(path)
            assets.append({"path": str(path), "prompt_id": str(n), "model": model})
    config = {
        "schema_version": 1,
        "name": "review regression",
        "models": ["a", "b"],
        "prompts": [
            {"id": str(n), "text": "two red cars", "group_id": str(n), "split": "exploratory"}
            for n in range(pairs)
        ],
        "assets": assets,
        "metrics": [{"id": "pixel_luminance"}] if metric else [],
    }
    store = Store(tmp_path / "study.db")
    exp = experiments.create(store, config, tmp_path / "media")
    return store, exp["id"], config


def judge_config(**changes):
    return {
        "provider": "openai",
        "model": "fixture",
        "rubric": RUBRIC,
        "retry": {"max_retries": 1, "initial_backoff_seconds": 0},
        **changes,
    }


class Response:
    def __init__(self, code=200, text=None):
        self.status_code = code
        self.ok = 200 <= code < 300
        self.headers = {}
        self.text = "fixture HTTP response"
        self.body = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": text or json.dumps(VERDICT)}],
                }
            ],
            "usage": {"input_tokens": 100, "output_tokens": 20},
            "model": "fixture",
            "id": "fixture-request",
        }

    def json(self):
        return self.body


class Transport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, *args, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    __call__ = post


def test_counterbalanced_pairs_and_bundle_resume(tmp_path):
    store, eid, _ = setup(tmp_path, pairs=12, metric=False)
    assets = store.list("asset", eid)
    trials = {t["id"]: t for t in store.list("trial", eid)}
    config = judge_config(
        provider="synthetic",
        mode="pairwise",
        seed=0,
        synthetic_response={**VERDICT, "labels": {"task": "A"}},
    )
    winners = []
    for prompt in store.list("prompt", eid):
        pair = [a for a in assets if trials[a["trial_id"]]["prompt_id"] == prompt["id"]]
        result = judges.judge(store, eid, pair, prompt["text"], config)
        winners.append(trials[store.get(result["order_mapping"]["A"])["trial_id"]]["model"])
        assert result["mapped_labels"]["task"] == result["order_mapping"]["A"]
        assert judges.judge(store, eid, pair, prompt["text"], config)["id"] == result["id"]
    assert Counter(winners) == {"a": 6, "b": 6}
    bundles.export_bundle(store, eid, tmp_path / "pairs.zip")
    replay = Store(tmp_path / "replay.db")
    bundles.import_bundle(replay, tmp_path / "pairs.zip", tmp_path / "replay-media")
    assert (
        judges.judge(replay, eid, [replay.get(a["id"]) for a in pair], prompt["text"], config)["id"]
        == result["id"]
    )
    assert len(replay.list("judge_call", eid)) == 24


def test_failed_metric_rerun_keeps_history_and_annotations(tmp_path):
    store, eid, _ = setup(tmp_path)
    assignment = human.assign(store, eid, "rater", RUBRIC)[0]
    label = human.annotate(
        store, assignment["id"], {"rater_id": "rater", "labels": {"task": "pass"}}
    )
    asset = store.get(assignment["asset_ids"][0])
    path = Path(asset["locator"])
    original = path.read_bytes()
    path.write_bytes(b"broken image")
    experiments.execute(store, eid, tmp_path / "media")
    failed = next(r for r in store.list("result", eid) if r["status"] == "failed_evaluation")
    path.write_bytes(original)
    experiments.execute(store, eid, tmp_path / "media")
    assert len(store.list("result", eid)) == 2
    experiments.execute(store, eid, tmp_path / "media", rerun_failed=True)
    newer = next(r for r in store.list("result", eid) if r.get("supersedes"))
    assert (
        newer["supersedes"] == failed["id"]
        and newer["evaluation_attempt"] == 2
        and newer["status"] == "success"
    )
    assert store.get(label["id"]) == label
    summary = analysis.summarize(store, eid)
    assert summary["scored"] == 2 and summary["superseded_evaluations"] == 1
    bundles.export_bundle(store, eid, tmp_path / "retry.zip")
    replay = Store(tmp_path / "retry.db")
    bundles.import_bundle(replay, tmp_path / "retry.zip", tmp_path / "retry-media")
    assert analysis.summarize(replay, eid) == summary
    experiments.execute(replay, eid, tmp_path / "retry-media")
    assert len(replay.list("result", eid)) == 3


def test_rate_limit_bounded_retry_and_structured_request(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    store, eid, _ = setup(tmp_path)
    asset = store.list("asset", eid)[:1]
    transport = Transport(Response(429), Response())
    result = judges.judge(store, eid, asset, "task", judge_config(), transport=transport)
    assert result["status"] == "success" and len(transport.calls) == 2
    assert transport.calls[0]["json"]["text"]["format"]["type"] == "json_schema"
    requests_saved = [r for r in store.list("judge_call", eid) if r["phase"] == "request"]
    assert requests_saved[1]["retry_of"] == requests_saved[0]["id"]
    assert requests_saved[1]["order_mapping"] == requests_saved[0]["order_mapping"]
    assert (
        judges.judge(store, eid, asset, "task", judge_config(), transport=Transport())["id"]
        == result["id"]
    )


def test_exhausted_retries_explicit_recovery(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    store, eid, _ = setup(tmp_path)
    asset = store.list("asset", eid)[:1]
    config = judge_config()
    failed = judges.judge(
        store, eid, asset, "task", config, transport=Transport(Response(429), Response(429))
    )
    assert failed["status"] == "failed_evaluation"
    assert (
        judges.judge(store, eid, asset, "task", config, transport=Transport())["id"] == failed["id"]
    )
    result = judges.retry_request(
        store, failed["request_record_id"], "Rate limit cleared", transport=Transport(Response())
    )
    assert result["status"] == "success" and result["attempt_index"] == 2
    assert len(store.list("judge_reconciliation", eid)) == 1
    assert len(store.list("judge_call", eid)) == 6


@pytest.mark.parametrize(
    "failure", [requests.Timeout("ambiguous"), requests.ConnectionError("ambiguous"), Response(503)]
)
def test_ambiguous_delivery_requires_reconciliation(tmp_path, monkeypatch, failure):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    store, eid, _ = setup(tmp_path)
    asset = store.list("asset", eid)[:1]
    transport = Transport(failure)
    result = judges.judge(store, eid, asset, "task", judge_config(), transport=transport)
    assert len(transport.calls) == 1 and result["delivery"] == "unknown"
    with pytest.raises(ValueError, match="Unknown delivery"):
        judges.retry_request(
            store, result["request_record_id"], "Investigated", transport=Transport()
        )
    judges.reconcile_request(
        store, result["request_record_id"], "not_delivered", "Provider confirmed no execution"
    )
    assert (
        judges.retry_request(
            store,
            result["request_record_id"],
            "Delivery reconciled",
            transport=Transport(Response()),
        )["status"]
        == "success"
    )


def test_recovered_response_and_abandon_are_durable(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    store, eid, _ = setup(tmp_path)
    assets = store.list("asset", eid)
    config = judge_config()
    failure = judges.judge(
        store, eid, assets[:1], "task", config, transport=Transport(requests.Timeout())
    )
    judges.reconcile_request(
        store, failure["request_record_id"], "completed", "Recovered from provider log", VERDICT
    )
    result = judges.judge(store, eid, assets[:1], "task", config, transport=Transport())
    assert (
        result["status"] == "success"
        and result["reconciliation_id"]
        and result["delivery"] == "operator_reconciled"
    )
    failure = judges.judge(
        store, eid, assets[1:], "task", config, transport=Transport(requests.Timeout())
    )
    judges.reconcile_request(store, failure["request_record_id"], "abandon", "Excluded with reason")
    assert (
        judges.judge(store, eid, assets[1:], "task", config, transport=Transport())["reason"]
        == "operator_abandoned"
    )


def test_fenced_json_parse_and_invalid_labels():
    assert (
        judges.parse("```json\n" + json.dumps(VERDICT) + "\n```", RUBRIC, "pointwise", [])
        == VERDICT
    )
    with pytest.raises(ValueError):
        judges.parse(json.dumps({**VERDICT, "labels": ["task"]}), RUBRIC, "pointwise", [])


def test_retry_after_expiry_is_recoverable():
    from datetime import datetime, timedelta

    old = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    config = {"retry": {"initial_backoff_seconds": 0}}
    assert judges.retry_delay({"retry_after": "120", "created_at": old}, 0, config) == 0
    assert judges.retry_delay({"retry_after": "inf"}, 0, config) == 0


def test_reviewed_empty_criteria_stay_empty(tmp_path):
    store, eid, _ = setup(tmp_path)
    result = metrics.evaluate(
        "object_criteria", store.list("asset", eid)[:1], "two red cars", {"criteria": []}
    )
    assert result["status"] == "not_applicable" and result["score"] is None


def test_duplicate_units_and_adjudicated_overlay(tmp_path):
    store, eid, _ = setup(tmp_path)
    a = human.assign(store, eid, "a", RUBRIC, seed=1)
    b = human.assign(store, eid, "b", RUBRIC, seed=2)
    assert {x["id"] for x in human.assign(store, eid, "a", RUBRIC, seed=42)} == {x["id"] for x in a}
    for assignment in a + b:
        human.annotate(
            store,
            assignment["id"],
            {
                "rater_id": assignment["rater_id"],
                "labels": {"task": "pass" if assignment["rater_id"] == "a" else "fail"},
            },
        )
    # Imported historical duplicate assignment: newer label wins without destroying either record.
    duplicate = {**a[0], "id": "duplicate-unit", "created_at": "2099-01-01T00:00:00+00:00"}
    store.put(duplicate)
    duplicate_label = human.annotate(
        store, duplicate["id"], {"rater_id": "a", "labels": {"task": "fail"}}
    )
    raw = analysis.summarize(store, eid)
    assert (
        raw["annotations"] == 4
        and raw["annotation_selection_warnings"][0]["kind"] == "duplicate_rater_unit"
    )
    paired = next(x for x in b if set(x["asset_ids"]) == set(a[0]["asset_ids"]))
    other = next(x for x in store.list("annotation", eid) if x["assignment_id"] == paired["id"])
    human.annotate(
        store,
        duplicate["id"],
        {
            "rater_id": "a",
            "labels": {"task": "pass"},
            "adjudicates": [duplicate_label["id"], other["id"]],
        },
    )
    adjudicated = analysis.summarize(store, eid, label_view="adjudicated")
    assert adjudicated["annotations"] == 4 and adjudicated["annotation_records"] == 6
    assert adjudicated["rater_agreement"][0]["cohen_kappa"] is None
    assert analysis.summarize(store, eid)["rater_agreement"] == raw["rater_agreement"]


@pytest.mark.parametrize(
    "text,minimum,maximum",
    [
        ("two red cars", 2, 2),
        ("three large dogs", 3, 3),
        ("at least two small dogs", 2, None),
        ("no large dogs", 0, 0),
        ("between two and four red cars", 2, 4),
    ],
)
def test_adjective_counts(text, minimum, maximum):
    criterion = interpret(text)["criteria"][0]
    assert (criterion["minimum"], criterion["maximum"]) == (minimum, maximum)
    assert criterion["kind"] == "count"


def test_unsupported_modifier_does_not_erase_count():
    criterion = interpret("two fantastically fluffy dogs")["criteria"][0]
    assert criterion["kind"] == "unsupported" and criterion["count_mode"] == "unresolved"
    assert interpret("two or three red cars")["criteria"][0]["kind"] == "unsupported"
    assert interpret("about two dogs")["criteria"][0]["kind"] == "unsupported"
    orange = interpret("two orange cars")["criteria"]
    assert len(orange) == 1 and orange[0]["entity"] == "car" and orange[0]["minimum"] == 2


def test_detector_vocabulary_controls_absence(tmp_path, monkeypatch):
    store, eid, _ = setup(tmp_path)
    asset = store.list("asset", eid)[:1]
    monkeypatch.setattr(metrics, "dependencies", lambda _: [])
    monkeypatch.setattr(
        metrics,
        "detect",
        lambda *a, **kw: ([], {"classes": {0: "custom-widget"}, "weights_sha256": "fixture"}),
    )
    result = metrics.evaluate("object_criteria", asset, "a dog")
    assert result["status"] == "not_applicable" and result["score"] is None
    assert result["details"]["criteria"][0]["label"] == "uncertain"


def test_comparison_joins_and_analysis_exports(tmp_path):
    store, eid, _ = setup(tmp_path, pairs=2)
    experiments.execute(store, eid, tmp_path / "media")
    assignments = human.assign(store, eid, "rater", RUBRIC)
    for i, assignment in enumerate(assignments):
        human.annotate(
            store,
            assignment["id"],
            {"rater_id": "rater", "labels": {"task": "pass" if i % 2 else "fail"}},
        )
        judges.judge(
            store,
            eid,
            [store.get(assignment["asset_ids"][0])],
            assignment["prompt_text"],
            judge_config(provider="synthetic", synthetic_response=VERDICT),
        )
    data = comparison.joined_rows(store, eid)
    assert len(data["judge_rows"]) == len(data["metric_rows"]) == 4
    summary = comparison.compare(store, eid)
    assert (
        summary["judge_vs_human"][0]["binary"]["fp"] == 2
        and summary["judge_vs_human"][0]["binary"]["tp"] == 2
    )
    assert len(comparison.analysis_input(store, eid, "binary")) == 4
    paired = comparison.analysis_input(store, eid, "paired")
    assert analysis.paired_difference(paired, "a", "b")["paired_tasks"] == 2
    selection = comparison.analysis_input(store, eid, "selection")
    selector = next(iter(selection[0]["scores"]))
    assert len(analysis.selection(selection, {selector: "higher"}, [2])["results"]) == 4
    mismatched = copy.deepcopy(RUBRIC)
    mismatched["version"] = "different"
    human.annotate(
        store,
        human.assign(store, eid, "other", mismatched)[0]["id"],
        {"rater_id": "other", "labels": {"task": "pass"}},
    )
    row = comparison.joined_rows(store, eid, filters={"rater_id": "other"})["judge_rows"][0]
    assert row["match_status"] == "rubric_mismatch" and row["judge"] is None
    with pytest.raises(ValueError, match="Ambiguous"):
        comparison.analysis_input(store, eid, "binary")


def test_preview_blinded_export_and_api_comparison(tmp_path):
    store, eid, config = setup(tmp_path)
    app = create_app(store.path, tmp_path / "media")
    client = app.test_client()
    preview = client.post("/api/research/preview", json=config).get_json()
    assert (
        preview["frozen"] is False
        and preview["config"]["prompts"][0]["criteria"][0]["minimum"] == 2
    )
    assert len(store.list("experiment")) == 1
    assignment = human.assign(store, eid, "private-rater", RUBRIC)[0]
    human.annotate(
        store, assignment["id"], {"rater_id": "private-rater", "labels": {"task": "pass"}}
    )
    exported = client.get(f"/api/research/experiments/{eid}/annotations?blinded=1").get_data(
        as_text=True
    )
    assert "private-rater" not in exported
    assert client.get(f"/api/research/experiments/{eid}/comparison").status_code == 200
    assert client.get(f"/api/research/experiments/{eid}/comparison-rows").status_code == 200
    assert analysis.agreement([("pass", "fail")])["cohen_kappa"] is None


def test_legacy_image_settings_forwarding_and_retry(tmp_path, fixture_media, monkeypatch):
    import sys
    from urllib.parse import quote

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "dream_layer_backend"))
    import dream_layer

    monkeypatch.setattr(
        dream_layer, "get_directories", lambda: (str(fixture_media[0]), str(tmp_path / "input"))
    )
    monkeypatch.setenv("DREAMLAYER_CLIP_REVISION", "server-revision")
    monkeypatch.setenv("DREAMLAYER_YOLO_WEIGHTS", "server-weights")
    called = []

    def evaluator(metric, assets, prompt, config):
        called.append((metric, config))
        return metrics.result(
            metric,
            assets,
            config=config,
            status="unavailable_dependency",
            score=None,
            reason="Explicit test fixture",
        )

    monkeypatch.setattr(metrics, "evaluate", evaluator)
    client = dream_layer.app.test_client()
    body = {
        "image_url": "http://localhost/api/images/" + quote("zero café.png"),
        "prompt": "a dog",
        "evaluator_settings": {
            "clip_cosine": {"revision": "client-revision"},
            "object_criteria": {"weights": "client-weights"},
        },
    }
    assert client.post("/api/calculate-metrics", json=body).status_code == 200
    assert ("clip_cosine", {"revision": "client-revision"}) in called
    assert ("object_criteria", {"weights": "client-weights"}) in called
    assert client.post("/api/calculate-metrics", json=body).status_code == 200 and len(called) == 3
    assert (
        client.post("/api/calculate-metrics", json={**body, "rerun_failed": True}).status_code
        == 200
        and len(called) == 6
    )
    assert (
        client.post(
            "/api/calculate-metrics",
            json={k: v for k, v in body.items() if k != "evaluator_settings"},
        ).status_code
        == 200
    )
    assert ("clip_cosine", {"revision": "server-revision"}) in called and (
        "object_criteria",
        {"weights": "server-weights"},
    ) in called


def test_versioned_cost_estimates(tmp_path, monkeypatch):
    prices = {
        "version": "fixture-v1",
        "as_of": "2026-10-29",
        "source": "test fixture, not commercial prices",
        "currency": "USD",
        "input_per_million": 2,
        "output_per_million": 10,
    }
    assert estimate({"input_tokens": 100, "output_tokens": 20}, prices, "openai") == pytest.approx(
        0.0004
    )
    assert (
        estimate(
            {
                "input_tokens": 100,
                "output_tokens": 20,
                "input_tokens_details": {"cached_tokens": 20},
            },
            prices,
            "openai",
        )
        is None
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    store, eid, _ = setup(tmp_path)
    result = judges.judge(
        store,
        eid,
        store.list("asset", eid)[:1],
        "task",
        judge_config(pricing=prices),
        transport=Transport(Response()),
    )
    assert result["cost"] is None and result["estimated_cost"] == pytest.approx(0.0004)
    assert analysis.summarize(store, eid)["judge_tradeoffs"][0]["estimated_cost"] == pytest.approx(
        0.0004
    )


def test_dataset_cache_includes_version_and_weights(tmp_path, monkeypatch):
    store, eid, _ = setup(tmp_path)
    assets = store.list("asset", eid)
    weights = tmp_path / "weights"
    weights.write_bytes(b"one")
    first = metrics.cache_key("fid", assets, "", {"weights": str(weights)})
    weights.write_bytes(b"two")
    second = metrics.cache_key("fid", assets, "", {"weights": str(weights)})
    assert first != second
    monkeypatch.setitem(metrics.REGISTRY["fid"], "version", "next")
    assert metrics.cache_key("fid", assets, "", {"weights": str(weights)}) != second


def test_provisioned_weights_retry_supersedes_unavailable(tmp_path, monkeypatch):
    store, _, config = setup(tmp_path)
    weights = tmp_path / "provisioned.pt"
    config["metrics"] = [{"id": "object_criteria", "weights": str(weights)}]
    eid = experiments.create(store, config, tmp_path / "media")["id"]
    monkeypatch.setattr(metrics, "dependencies", lambda _: [])

    def detector(path, weight_path, threshold):
        if not Path(weight_path).exists():
            raise ImportError("Weights not yet provisioned")
        return [{"class_name": "car"}, {"class_name": "car"}], {
            "classes": {0: "car"},
            "weights_sha256": file_hash(weight_path),
        }

    monkeypatch.setattr(metrics, "detect", detector)
    experiments.execute(store, eid, tmp_path / "media")
    assert analysis.summarize(store, eid)["unavailable"] == 2
    weights.write_bytes(b"fixture weights")
    experiments.execute(store, eid, tmp_path / "media", rerun_failed=True)
    summary = analysis.summarize(store, eid)
    assert (
        summary["scored"] == 2
        and summary["unavailable"] == 0
        and summary["superseded_evaluations"] == 2
    )


def test_temporal_windows_reach_metric_and_judge(tmp_path, fixture_media):
    root, _ = fixture_media
    _, details = media.adjacent_stability(root / "moving.webm", offset=2, window_seconds=0.3)
    assert details["offset_seconds"] == 2 and details["window_seconds"] == 0.3
    asset = record("asset", **experiments.managed_asset(root / "moving.webm", tmp_path / "media"))
    images, observations = judges.evidence(
        [asset], frames=3, policy="window", offset=2, window_seconds=0.3
    )
    assert len(images) == 3 and [o["timestamp"] for o in observations] == pytest.approx(
        [2, 2.1, 2.2]
    )


def test_preflight_credentials_and_read_only_endpoint(monkeypatch):
    from research.preflight import inspect

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    class ReadOnly:
        def __init__(self):
            self.urls = []

        def get(self, url, timeout):
            self.urls.append(url)

            class R:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"system": {}}

            return R()

    transport = ReadOnly()
    result = inspect(
        {
            "judges": [judge_config()],
            "generation": {"workflow": {"1": {"inputs": {}}}, "bindings": {}},
            "prompts": [{"id": "p", "text": "task"}],
        },
        transport,
    )
    assert result["provider_calls_submitted"] == 0 and transport.urls == [
        "http://127.0.0.1:8188/system_stats"
    ]
    assert (
        next(c for c in result["checks"] if c["check"] == "judge_credentials")["status"]
        == "unavailable"
    )


def test_historical_rankings_portable_and_idempotent(tmp_path):
    from research.historical_import import import_rankings

    path = tmp_path / "history.csv"
    path.write_text("Quality Ranking,Model\n1 (Even),a\n1 (Even),b\n3,c\n")
    store = Store(tmp_path / "history.db")
    experiment = import_rankings(store, path)
    assert import_rankings(store, path) == experiment
    rows = store.list("historical_ranking", experiment["id"])
    assert len(rows) == 3 and sum(r["tie_group"] is not None for r in rows) == 2
    assert all(r["asset_id"] is None and r["numeric_score"] is None for r in rows)
    bundles.export_bundle(store, experiment["id"], tmp_path / "history.zip")
    replay = Store(tmp_path / "replay.db")
    bundles.import_bundle(replay, tmp_path / "history.zip", tmp_path / "media")
    assert replay.list("historical_ranking", experiment["id"]) == rows
