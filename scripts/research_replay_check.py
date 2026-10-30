"""Assert a portable bundle replays analysis and resumes without duplicate results."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research import analysis, bundles, experiments
from research.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    parser.add_argument("experiment_id")
    parser.add_argument("output")
    args = parser.parse_args()
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)
    if (root / "replayed.sqlite3").exists():
        raise ValueError("Choose a new output directory to verify a fresh database")
    original = Store(args.database)
    before = analysis.summarize(original, args.experiment_id)
    bundle = bundles.export_bundle(original, args.experiment_id, root / "experiment.zip")
    replay = Store(root / "replayed.sqlite3")
    eid = bundles.import_bundle(replay, bundle, root / "media")
    after = analysis.summarize(replay, eid)
    if before != after:
        raise AssertionError("Export/import changed analysis")
    counts = {
        kind: len(replay.list(kind, eid))
        for kind in ["trial", "result", "judge_call", "annotation"]
    }
    experiments.execute(replay, eid, root / "media")
    if counts != {kind: len(replay.list(kind, eid)) for kind in counts}:
        raise AssertionError("Resume duplicated records or performed new work")
    if after != analysis.summarize(replay, eid):
        raise AssertionError("Resume changed analysis")
    report = {
        "status": "success",
        "experiment_id": eid,
        "exact_analysis_match": True,
        "resume_added_records": 0,
        "counts": counts,
        "analysis": after,
    }
    (root / "replay-report.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
