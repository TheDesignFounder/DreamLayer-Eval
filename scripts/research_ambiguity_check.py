"""Run a separately hand-authored legacy fixture through the actual CLI."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image

from research import experiments
from research.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = Path(args.directory).resolve()
    output.mkdir(parents=True, exist_ok=False)
    fixture_path = root / "tests/fixtures/ambiguous-legacy-v1.json"
    fixture = json.loads(fixture_path.read_text())
    image = output / "fixture.png"
    Image.new("RGB", (16, 16), "white").save(image)
    store = Store(output / "study.sqlite3")
    config = {
        "schema_version": 1,
        "name": "Opaque legacy settings",
        "models": ["fixture"],
        "prompts": [{"id": "p", "text": "a dog"}],
        "assets": [{"prompt_id": "p", "model": "fixture", "path": str(image)}],
        "metrics": fixture["metrics"],
    }
    eid = experiments.create(store, config, output / "media")["id"]
    asset = store.list("asset", eid)[0]
    membership = hashlib.sha256(
        json.dumps([asset["sha256"]], separators=(",", ":")).encode()
    ).hexdigest()
    # Supply opaque records directly, without calling metric evaluation or the matcher.
    for index in range(2):
        store.put(
            {
                **fixture["result"],
                "id": f"opaque-result-{index}",
                "experiment_id": eid,
                "asset_ids": [asset["id"]],
                "trial_id": asset["trial_id"],
                "membership_hash": membership,
            }
        )
    before = store.list("result", eid)
    checks = []
    for flags in (
        [],
        ["--rerun-failed"],
        ["--upgrade-evaluators"],
        ["--rerun-failed", "--upgrade-evaluators"],
    ):
        response = subprocess.run(
            [sys.executable, "-m", "research", "--db", str(store.path), "run", eid, *flags],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        job = json.loads(response.stdout)
        warnings = [
            w for w in job["resume_warnings"] if w["kind"] == "unresolved_legacy_metric_settings"
        ]
        assert job["state"] == "complete" and len(warnings) == 2
        assert all(len(w["possible_configuration_hashes"]) == 2 for w in warnings)
        assert store.list("result", eid) == before and not store.list("judge_call", eid)
        checks.append(
            {
                "flags": flags,
                "result_count": 2,
                "added_results": 0,
                "ambiguous_warnings": len(warnings),
                "exit_code": 0,
            }
        )
    report = {
        "status": "passed",
        "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "checks": checks,
        "original_payloads_unchanged": True,
        "provider_calls": 0,
        "scope": "Separate hand-authored fixture and CLI execution, not external reviewer confirmation.",
    }
    (output / "result.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
