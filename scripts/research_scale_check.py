"""Measure real SQLite/judge/assignment work at 2,000 imported synthetic trials."""

import argparse
import json
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image

from research import experiments, human
from research.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    parser.add_argument("--trials", type=int, default=2000)
    args = parser.parse_args()
    if args.trials < 1:
        parser.error("trials must be positive")
    root = Path(args.directory).resolve()
    root.mkdir(parents=True, exist_ok=False)
    path = root / "fixture.png"
    Image.new("RGB", (16, 16), (10, 20, 30)).save(path)
    store = Store(root / "study.sqlite3")
    rubric = {
        "version": "1",
        "criteria": [{"id": "task", "description": "Synthetic scale fixture"}],
    }
    config = {
        "schema_version": 1,
        "name": "Scale fixture",
        "models": ["fixture"],
        "prompts": [{"id": str(i), "text": f"fixture {i}"} for i in range(args.trials)],
        "assets": [
            {"path": str(path), "prompt_id": str(i), "model": "fixture"} for i in range(args.trials)
        ],
        "metrics": [{"id": "pixel_luminance"}],
        "judges": [
            {"provider": "synthetic", "model": f"synthetic-{i}", "rubric": rubric} for i in range(2)
        ],
    }
    durations = {}
    start = time.perf_counter()
    eid = experiments.create(store, config, root / "media")["id"]
    durations["create_seconds"] = time.perf_counter() - start
    for phase in ("first_run", "resume"):
        count = len(store.list(experiment_id=eid))
        start = time.perf_counter()
        job = experiments.execute(store, eid, root / "media")
        durations[f"{phase}_seconds"] = time.perf_counter() - start
        assert job["state"] == "complete"
        if phase == "resume":
            assert len(store.list(experiment_id=eid)) == count
    start = time.perf_counter()
    assigned = human.assign(store, eid, "scale-rater", rubric)
    durations["assign_seconds"] = time.perf_counter() - start
    start = time.perf_counter()
    repeated = human.assign(store, eid, "scale-rater", rubric)
    durations["assignment_resume_seconds"] = time.perf_counter() - start
    assert assigned == repeated and len(assigned) == args.trials
    calls = store.list("judge_call", eid)
    assert len(calls) == args.trials * 4
    with store.connection() as connection:
        plan = [
            dict(row)
            for row in connection.execute(
                "EXPLAIN QUERY PLAN SELECT payload FROM research_records WHERE experiment_id=? "
                "AND kind=? AND json_extract(payload,'$.protocol_key') IS ? ORDER BY created_at,id",
                (eid, "judge_call", calls[0]["protocol_key"]),
            )
        ]
    assert any("research_by_protocol_key" in row["detail"] for row in plan)
    report = {
        "status": "passed",
        "trials": args.trials,
        "judges_per_trial": 2,
        "judge_mode": "pointwise",
        "judge_requests": len(calls) // 2,
        "resume_added_records": 0,
        "assignment_count": len(assigned),
        "durations": durations,
        "database_bytes": store.path.stat().st_size,
        "query_plan": plan,
        "python": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "provider_calls": 0,
        "limitations": "Synthetic judges, one shared tiny image, local SQLite, serial execution. Not inference throughput, human annotation throughput, or pairwise planning scale.",
    }
    (root / "result.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
