"""Bounded real-provider smoke on generated images, with auditable cost reservations.

Preview is the default. Execution requires explicit --execute, --cap-usd, and
environment credentials. No response is synthesized; the transport wraps requests
only to restrict endpoints, request size, call count and reserved estimated spend.
"""

import argparse
import json
import os
import sys
from decimal import Decimal
from functools import partial
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from PIL import Image, ImageDraw

from research import analysis, bundles, experiments, judges
from research.contracts import now
from research.store import Store

MAX_INPUT_RESERVATION = 32768
MAX_OUTPUT = 1024
MODELS = {
    "openai": {
        "model": "gpt-5.4-mini-2026-03-17",
        "url": "https://api.openai.com/v1/responses",
        "key": "OPENAI_API_KEY",
        "pricing": {
            "input_per_million": 0.75,
            "output_per_million": 4.5,
            "cached_input_per_million": 0.075,
            "source": "https://developers.openai.com/api/docs/models/gpt-5.4-mini",
        },
    },
    "anthropic": {
        "model": "claude-haiku-4-5-20251001",
        "url": "https://api.anthropic.com/v1/messages",
        "key": "ANTHROPIC_API_KEY",
        "pricing": {
            "input_per_million": 1,
            "output_per_million": 5,
            "cached_input_per_million": 0.1,
            "cache_write_per_million": 1.25,
            "source": "https://platform.claude.com/docs/en/models/haiku-4-5/overview",
        },
    },
}


def reservation(provider):
    rates = MODELS[provider]["pricing"]
    return (
        Decimal(MAX_INPUT_RESERVATION) * Decimal(str(rates["input_per_million"]))
        + Decimal(MAX_OUTPUT) * Decimal(str(rates["output_per_million"]))
    ) / Decimal(1_000_000)


class BoundedHTTP:
    """Reserve the worst configured token scenario before any real HTTP submission."""

    def __init__(self, cap, providers, ledger, client=requests):
        self.cap = Decimal(str(cap))
        if not self.cap.is_finite() or self.cap <= 0:
            raise ValueError("A finite positive USD cap is required")
        self.providers = providers
        self.client = client
        self.ledger = Path(ledger)
        self.calls = []
        self.reserved = Decimal(0)
        self.stop_reason = None

    def post(self, url, **kwargs):
        if self.stop_reason:
            raise ValueError(self.stop_reason)
        provider = next((p for p in self.providers if MODELS[p]["url"] == url), None)
        if provider is None:
            raise ValueError("Smoke transport refuses an unapproved endpoint")
        payload = kwargs["json"]
        if payload.get("model") != MODELS[provider]["model"]:
            raise ValueError("Smoke model must match the priced snapshot")
        output_limit = payload.get("max_output_tokens", payload.get("max_tokens"))
        if (
            output_limit != MAX_OUTPUT
            or len(json.dumps(payload).encode()) > 32000
            or payload.get("tools")
        ):
            raise ValueError("Smoke payload exceeds the approved size/output/tool limits")
        reserved = reservation(provider)
        if len(self.calls) >= 6 * len(self.providers) or self.reserved + reserved > self.cap:
            raise ValueError("Smoke spending/call cap reached before submission")
        self.reserved += reserved
        self.calls.append(
            {
                "provider": provider,
                "model": payload["model"],
                "reserved_usd": float(reserved),
                "submitted_at": now(),
            }
        )
        self.ledger.write_text(
            json.dumps(
                {
                    "cap_usd": float(self.cap),
                    "reserved_usd": float(self.reserved),
                    "calls": self.calls,
                },
                indent=2,
            )
        )
        try:
            response = self.client.post(url, **kwargs, allow_redirects=False)
        except Exception:
            self.stop_reason = (
                "Transport failure; smoke stops without automatic retries or refunding reservations"
            )
            raise
        if not 200 <= response.status_code < 300:
            self.stop_reason = (
                f"Provider HTTP {response.status_code}; smoke stops before further requests"
            )
        else:
            usage = response.json().get("usage", {})
            if usage.get("input_tokens", MAX_INPUT_RESERVATION + 1) > MAX_INPUT_RESERVATION:
                self.stop_reason = "Provider usage exceeded the conservative input reservation; reconcile billing before further calls"
        return response


def run(root, providers, cap):
    root.mkdir(parents=True, exist_ok=False)
    rubric = {
        "version": "1",
        "criteria": [
            {
                "id": "task",
                "description": "Does the visible image fulfill the specified color and shape? In pairwise mode choose the more faithful image; tie or abstain when appropriate.",
            }
        ],
    }
    config = {
        "schema_version": 1,
        "name": "Bounded real provider smoke",
        "models": ["matching", "other"],
        "prompts": [
            {"id": "red", "text": "a red square on a white background"},
            {"id": "blue", "text": "a blue circle on a white background"},
        ],
        "metrics": [{"id": "pixel_luminance"}],
        "assets": [],
        "judges": [],
    }
    for prompt in config["prompts"]:
        for model in config["models"]:
            image = Image.new("RGB", (128, 128), "white")
            draw = ImageDraw.Draw(image)
            color = prompt["id"] if model == "matching" else "green"
            if prompt["id"] == "red":
                draw.rectangle((24, 24, 104, 104), fill=color)
            else:
                draw.ellipse((24, 24, 104, 104), fill=color)
            path = root / f"{prompt['id']}-{model}.png"
            image.save(path)
            config["assets"].append({"path": str(path), "prompt_id": prompt["id"], "model": model})
    for provider in providers:
        for mode in ("pointwise", "pairwise"):
            config["judges"].append(
                {
                    "provider": provider,
                    "model": MODELS[provider]["model"],
                    "mode": mode,
                    "protocol": "sparse",
                    "max_side": 128,
                    "max_output_tokens": MAX_OUTPUT,
                    "timeout": 60,
                    "retry": {"max_retries": 0},
                    "budget": {"calls": 1, "frames": 2, "tokens": 65536},
                    "rubric": rubric,
                    "pricing": {
                        **MODELS[provider]["pricing"],
                        "currency": "USD",
                        "as_of": "2026-10-30",
                        "version": "official-model-page-20261030",
                    },
                }
            )
    transport = BoundedHTTP(cap, providers, root / "spending-reservations.json")
    store = Store(root / "study.sqlite3")
    eid = experiments.create(store, config, root / "media")["id"]
    report = {
        "started_at": now(),
        "cap_usd": float(cap),
        "experiment_id": eid,
        "planned_calls": 6 * len(providers),
        "models": {p: MODELS[p]["model"] for p in providers},
        "pricing": {p: MODELS[p]["pricing"] for p in providers},
        "status": "running",
    }
    # Instrument the real network boundary; no provider response is mocked.
    live_judge = partial(judges.judge, transport=transport.post)
    try:
        with patch.object(experiments, "judge", live_judge):
            experiments.execute(store, eid, root / "media")
            before = store.list(experiment_id=eid)
            call_count = len(transport.calls)
            experiments.execute(store, eid, root / "media")
            assert store.list(experiment_id=eid) == before and len(transport.calls) == call_count
            bundles.export_bundle(store, eid, root / "experiment.zip")
            replay = Store(root / "fresh.sqlite3")
            bundles.import_bundle(replay, root / "experiment.zip", root / "fresh-media")
            experiments.execute(replay, eid, root / "fresh-media")
            assert len(transport.calls) == call_count
            assert analysis.summarize(store, eid) == analysis.summarize(replay, eid)
        responses = [r for r in store.list("judge_call", eid) if r.get("phase") == "response"]
        assert len(responses) == 6 * len(providers)
        assert all(
            r["status"] == "success" and r.get("parsed") and r.get("usage") for r in responses
        )
        report.update(status="passed", resume_added_calls=0, fresh_replay_exact=True)
    except Exception as exc:
        report.update(status="failed", reason=str(exc))
    finally:
        responses = [r for r in store.list("judge_call", eid) if r.get("phase") == "response"]
        report.update(
            actual_http_calls=len(transport.calls),
            reserved_usd=float(transport.reserved),
            estimated_total_usd=sum(
                r["estimated_cost"] for r in responses if r.get("estimated_cost") is not None
            ),
            responses=[
                {
                    k: r.get(k)
                    for k in [
                        "provider",
                        "configured_model",
                        "model",
                        "status",
                        "reason",
                        "usage",
                        "estimated_cost",
                        "elapsed_ms",
                        "parsed",
                        "order_mapping",
                        "mapped_labels",
                    ]
                }
                for r in responses
            ],
            billing_confirmed=False,
            limitation="One tiny fixture study with bounded requests. Reservations use 32,768 input tokens per request, over the small fixed image/text inputs; rates and provider billing are not independently audited. Retry/reconciliation failure branches are not deliberately induced against paid APIs.",
        )
        (root / "result.json").write_text(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", default=".research/live-smoke")
    parser.add_argument("--provider", choices=["both", "openai", "anthropic"], default="both")
    parser.add_argument("--cap-usd", type=Decimal)
    parser.add_argument("--env-file", default=".research/live-smoke.env")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    providers = list(MODELS) if args.provider == "both" else [args.provider]
    upper = sum((6 * reservation(p) for p in providers), Decimal(0))
    if not args.execute:
        print(
            json.dumps(
                {
                    "mode": "preview",
                    "planned_calls": 6 * len(providers),
                    "reserved_upper_usd": float(upper),
                    "models": {p: MODELS[p]["model"] for p in providers},
                    "configured_cap_usd": float(args.cap_usd) if args.cap_usd else None,
                },
                indent=2,
            )
        )
        return
    if (
        args.cap_usd is None
        or not args.cap_usd.is_finite()
        or args.cap_usd <= 0
        or args.cap_usd < upper
    ):
        parser.error(
            f"Explicit positive --cap-usd must cover the conservative reservation ({upper} USD)"
        )
    if Path(args.env_file).exists():
        from dotenv import load_dotenv

        load_dotenv(args.env_file, override=False)
    missing = [MODELS[p]["key"] for p in providers if not os.environ.get(MODELS[p]["key"])]
    if missing:
        parser.error("Credentials are not configured: " + ", ".join(missing))
    report = run(Path(args.directory).resolve(), providers, args.cap_usd)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
