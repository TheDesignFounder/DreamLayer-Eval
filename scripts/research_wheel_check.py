"""Run with the isolated wheel environment's python -I to prove installed CLI replay."""

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from importlib.resources import files
from pathlib import Path

import research
from research.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    args = parser.parse_args()
    root = Path(args.directory).resolve()
    root.mkdir(parents=True, exist_ok=False)
    assert Path(research.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()), (
        "Run from an installed wheel environment with python -I, not the source tree"
    )
    for name in ("record-v1.json", "bundle-v1.json"):
        json.loads(files("research.schemas").joinpath(name).read_text())

    def cli(database, *arguments):
        result = subprocess.run(
            [sys.executable, "-I", "-m", "research", "--db", str(database), *arguments],
            cwd=root,
            check=True,
            text=True,
            capture_output=True,
        )
        return json.loads(result.stdout)

    original = root / "original.sqlite3"
    replay = root / "replay.sqlite3"
    demo = cli(original, "demo", "--directory", str(root / "fixtures"))
    eid = demo["experiment_id"]
    expected = cli(original, "analyze", eid)
    bundle = root / "experiment.zip"
    cli(original, "export", eid, str(bundle))
    cli(replay, "import", str(bundle))
    before = Store(replay).list(experiment_id=eid)
    cli(replay, "run", eid)
    assert Store(replay).list(experiment_id=eid) == before
    assert cli(replay, "analyze", eid) == expected
    with zipfile.ZipFile(bundle) as archive:
        for name in ("records.jsonl", "provenance.json"):
            assert str(root) not in archive.read(name).decode()
    report = {
        "status": "passed",
        "package_version": research.__version__,
        "python": sys.version.split()[0],
        "installed_package_outside_source": True,
        "schemas_present": True,
        "cli_demo_export_import_run_analyze": "passed",
        "fresh_resume_added_records": 0,
        "fresh_replay_exact": True,
        "bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
        "analysis": expected,
    }
    (root / "result.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
