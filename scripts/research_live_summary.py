"""Regenerate the live-smoke summary from saved evidence, with all HTTP blocked.

No credentials or provider calls are needed. --verified-at preserves the published
verification timestamp for byte-for-byte reproduction; omit it for a new audit.
Inputs: result.json, spending-reservations.json, experiment.zip, study.sqlite3 and
the four fixture PNGs from scripts/research_live_smoke.py. Source inputs are read-only.
"""

import argparse
import collections
import json
import math
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jsonschema import Draft202012Validator

from research import analysis, bundles, experiments
from research.contracts import file_hash, now
from research.pricing import estimate
from research.store import Store


def generate(root, verified_at):
    report = json.loads((root / "result.json").read_text())
    ledger = json.loads((root / "spending-reservations.json").read_text())
    assert report["status"] == "passed" and report["actual_http_calls"] == 12
    assert report["resume_added_calls"] == 0 and report["fresh_replay_exact"] is True
    assert len(ledger["calls"]) == report["actual_http_calls"]
    reserved = sum(Decimal(str(c["reserved_usd"])) for c in ledger["calls"])
    assert reserved == Decimal(str(report["reserved_usd"])) == Decimal(str(ledger["reserved_usd"]))
    assert reserved <= Decimal(str(ledger["cap_usd"])) == Decimal(str(report["cap_usd"]))
    eid = report["experiment_id"]
    validator = Draft202012Validator(
        json.loads(files("research.schemas").joinpath("record-v1.json").read_text())
    )
    with zipfile.ZipFile(root / "experiment.zip") as archive:
        exported = [json.loads(line) for line in archive.read("records.jsonl").splitlines()]
        for record in exported:
            validator.validate(record)
        assert b"/Users/" not in archive.read("records.jsonl")
    with tempfile.TemporaryDirectory(prefix="dreamlayer-live-summary-") as temp:
        work = Path(temp)
        with sqlite3.connect(
            (root / "study.sqlite3").resolve().as_uri() + "?mode=ro", uri=True
        ) as original:
            with sqlite3.connect(work / "source.sqlite3") as copied:
                original.backup(copied)
        source = Store(work / "source.sqlite3")
        original_records = source.list(experiment_id=eid)
        by_id = {r["id"]: r for r in original_records}
        assert {r["id"] for r in exported} == set(by_id)
        experiments.execute(source, eid, work / "source-media")
        assert source.list(experiment_id=eid) == original_records
        replay = Store(work / "replay.sqlite3")
        bundles.import_bundle(replay, root / "experiment.zip", work / "media")
        before = replay.list(experiment_id=eid)
        experiments.execute(replay, eid, work / "media")
        assert replay.list(experiment_id=eid) == before
        assert analysis.summarize(source, eid) == analysis.summarize(replay, eid)
    responses = [
        r for r in original_records if r["kind"] == "judge_call" and r.get("phase") == "response"
    ]
    assert len(responses) == 12 and all(
        r["status"] == "success" and r.get("parsed") for r in responses
    )
    asset_models = {
        r["id"]: by_id[r["trial_id"]]["model"] for r in original_records if r["kind"] == "asset"
    }
    providers, public_responses = {}, []
    for provider in ("openai", "anthropic"):
        rows = [r for r in responses if r["provider"] == provider]
        mode_counts, slot_a = collections.Counter(), collections.Counter()
        for row in rows:
            request = by_id[row["request_record_id"]]
            mode = "pairwise" if len(request["order_mapping"]) == 2 else "pointwise"
            mode_counts[mode] += 1
            assert row["model"] == report["models"][provider]
            assert math.isclose(
                estimate(row["usage"], row["pricing"], provider),
                row["estimated_cost"],
                rel_tol=0,
                abs_tol=1e-12,
            )
            if mode == "pairwise":
                assert asset_models[row["mapped_labels"]["task"]] == "matching"
                slot_a[asset_models[request["order_mapping"]["A"]]] += 1
            else:
                expected = (
                    "pass" if asset_models[request["order_mapping"]["A"]] == "matching" else "fail"
                )
                assert row["parsed"]["labels"]["task"] == expected
            public_responses.append(
                {
                    "record_id": row["id"],
                    "provider": provider,
                    "mode": mode,
                    "returned_model": row["model"],
                    "status": row["status"],
                    "usage": row["usage"],
                    "estimated_cost_usd": row["estimated_cost"],
                    "elapsed_ms": row["elapsed_ms"],
                    "labels": row["parsed"]["labels"],
                    "order_mapping": row["order_mapping"],
                    "mapped_labels": row.get("mapped_labels"),
                    "fixture_expectation_matched": True,
                }
            )
        assert mode_counts == {"pointwise": 4, "pairwise": 2}
        assert slot_a == {"matching": 1, "other": 1}
        providers[provider] = {
            "configured_model": report["models"][provider],
            "returned_models": sorted({r["model"] for r in rows}),
            "successful_calls": len(rows),
            "pointwise": mode_counts["pointwise"],
            "pairwise": mode_counts["pairwise"],
            "matching_candidate_in_slot_a": slot_a["matching"],
            "other_candidate_in_slot_a": slot_a["other"],
            "input_tokens": sum(r["usage"]["input_tokens"] for r in rows),
            "output_tokens": sum(r["usage"]["output_tokens"] for r in rows),
            "estimated_cost_usd": float(sum(Decimal(str(r["estimated_cost"])) for r in rows)),
        }
    return {
        "executed_at": report["started_at"],
        "verified_at": verified_at,
        "status": "passed",
        "experiment_id": eid,
        "authorized_total_usd": int(ledger["cap_usd"])
        if float(ledger["cap_usd"]).is_integer()
        else ledger["cap_usd"],
        "actual_http_calls": 12,
        "reserved_upper_usd": report["reserved_usd"],
        "estimated_total_usd": float(sum(Decimal(str(r["estimated_cost"])) for r in responses)),
        "billing_confirmed": False,
        "providers": providers,
        "pricing": report["pricing"],
        "structured_results_parsed": 12,
        "fixture_expectations_matched": 12,
        "resume_added_calls": 0,
        "fresh_replay_exact": True,
        "independent_replay_with_network_blocked": True,
        "fresh_resume_added_records": 0,
        "schema_validated_records": len(exported),
        "bundle_sha256": file_hash(root / "experiment.zip"),
        "raw_report_sha256": file_hash(root / "result.json"),
        "spending_ledger_sha256": file_hash(root / "spending-reservations.json"),
        "script_sha256": file_hash(Path(__file__).with_name("research_live_smoke.py")),
        "fixture_sha256": {p.name: file_hash(p) for p in sorted(root.glob("*.png"))},
        "responses": public_responses,
        "limitations": [
            "Four generated color/shape fixtures only; this does not validate research conclusions or broad model quality.",
            "Retry, rate-limit, timeout and reconciliation branches remain verified only offline; no paid fault induction was performed.",
            "Token-based cost is estimated from recorded official rates and response usage; actual provider billing was not checked.",
            "Only the named model snapshots, image inputs and sparse one-pass protocols were exercised.",
        ],
        # Historical execution metadata, not a new credential scan. This generator
        # never loads credentials and cannot independently audit the original process.
        "credential_handling": "Read from an existing authorized local environment file into the test process only; no key was copied into source or evidence.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verified-at", default=None)
    args = parser.parse_args()
    verified_at = args.verified_at or now()
    datetime.fromisoformat(verified_at)
    with patch(
        "requests.sessions.Session.request",
        side_effect=AssertionError("Evidence generation forbids HTTP"),
    ):
        summary = generate(args.run_directory, verified_at)
    with args.output.open("x") as output:
        output.write(json.dumps(summary, indent=2) + "\n")
    print(
        json.dumps(
            {"status": "passed", "network_calls": 0, "summary_sha256": file_hash(args.output)}
        )
    )


if __name__ == "__main__":
    main()
