"""The paid smoke guard must reject requests before touching the network."""

import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from scripts.research_live_smoke import MAX_OUTPUT, MODELS, BoundedHTTP, reservation


def payload(provider="openai"):
    return {"model": MODELS[provider]["model"], "max_output_tokens": MAX_OUTPUT}


def test_insufficient_cap_makes_zero_calls(tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("Cap check must happen before HTTP")

    guard = BoundedHTTP(
        ".001", ["openai"], tmp_path / "ledger.json", SimpleNamespace(post=forbidden)
    )
    with pytest.raises(ValueError, match="cap reached"):
        guard.post(MODELS["openai"]["url"], json=payload())
    assert not guard.calls


def test_unknown_delivery_keeps_reservation_and_blocks_future_calls(tmp_path):
    count = []

    def timeout(*args, **kwargs):
        count.append(1)
        raise TimeoutError("unknown delivery")

    guard = BoundedHTTP(5, ["openai"], tmp_path / "ledger.json", SimpleNamespace(post=timeout))
    with pytest.raises(TimeoutError):
        guard.post(MODELS["openai"]["url"], json=payload())
    with pytest.raises(ValueError, match="Transport failure"):
        guard.post(MODELS["openai"]["url"], json=payload())
    ledger = json.loads((tmp_path / "ledger.json").read_text())
    assert count == [1] and Decimal(str(ledger["reserved_usd"])) == reservation("openai")


def test_unapproved_endpoint_and_oversized_payload_rejected(tmp_path):
    guard = BoundedHTTP(5, ["openai"], tmp_path / "ledger.json")
    with pytest.raises(ValueError, match="unapproved endpoint"):
        guard.post("https://example.invalid", json=payload())
    with pytest.raises(ValueError, match="size/output/tool"):
        guard.post(MODELS["openai"]["url"], json={**payload(), "input": "x" * 33000})
    assert not guard.calls


def test_http_error_stops_smoke_and_never_records_credentials(tmp_path):
    calls = []

    def denied(*args, **kwargs):
        calls.append(1)
        return SimpleNamespace(status_code=401)

    guard = BoundedHTTP(5, ["openai"], tmp_path / "ledger.json", SimpleNamespace(post=denied))
    guard.post(
        MODELS["openai"]["url"], json=payload(), headers={"Authorization": "Bearer secret-fixture"}
    )
    with pytest.raises(ValueError, match="HTTP 401"):
        guard.post(MODELS["openai"]["url"], json=payload())
    assert calls == [1] and "secret-fixture" not in (tmp_path / "ledger.json").read_text()


def test_offline_runner_uses_real_adapters_and_replays_without_more_requests(tmp_path, monkeypatch):
    """Fake only HTTP responses; exercise the guard, adapters, records and replay together."""
    from scripts import research_live_smoke

    calls = []

    def http_response(url, **kwargs):
        payload = kwargs["json"]
        calls.append(payload)
        is_openai = url == MODELS["openai"]["url"]
        schema = (
            payload["text"]["format"]["schema"]
            if is_openai
            else payload["output_config"]["format"]["schema"]
        )
        options = schema["properties"]["labels"]["properties"]["task"]["enum"]
        label = "A" if "A" in options else "pass"
        verdict = json.dumps(
            {
                "labels": {"task": label},
                "explanation": "Offline integration fixture",
                "evidence": [],
            }
        )
        body = {
            "model": payload["model"],
            "id": f"fixture-{len(calls)}",
            "usage": {"input_tokens": 100, "output_tokens": 20},
        }
        if is_openai:
            body["output"] = [
                {"type": "message", "content": [{"type": "output_text", "text": verdict}]}
            ]
        else:
            body["content"] = [{"type": "text", "text": verdict}]
        return SimpleNamespace(status_code=200, ok=True, json=lambda: body)

    monkeypatch.setattr(research_live_smoke.requests, "post", http_response)
    report = research_live_smoke.run(tmp_path / "smoke", ["openai", "anthropic"], Decimal(5))
    assert report["status"] == "passed", report
    assert len(calls) == report["actual_http_calls"] == 12
    assert report["fresh_replay_exact"] and report["resume_added_calls"] == 0
    assert 0 < report["estimated_total_usd"] < report["reserved_usd"] < 5
    assert all(row["parsed"] and row["estimated_cost"] is not None for row in report["responses"])
