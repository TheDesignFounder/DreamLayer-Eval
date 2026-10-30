"""Run the offline suite and assert no runtime artifacts changed in source paths."""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


def snapshot(root):
    files = {}
    ignored = {
        ".research",
        ".git",
        ".pytest_cache",
        "__pycache__",
        "node_modules",
        ".venv-research",
        ".venv-research-clean",
        "docs",
        "dist",
    }
    for parent, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".venv")]
        for name in names:
            p = Path(parent) / name
            runtime = any(
                part in {"served_images", "input", "output", "logs", "temp_images", "videos"}
                for part in p.relative_to(root).parts[:-1]
            )
            if (
                runtime
                or name.endswith((".db", ".sqlite3", ".sqlite", ".bak"))
                or name.startswith("dreamlayer_report_")
                and name.endswith(".zip")
            ):
                files[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("python")
    parser.add_argument("output")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    before = snapshot(root)
    with (output / "pytest.txt").open("w") as log:
        result = subprocess.run(
            [args.python, "-m", "pytest", "-q"],
            cwd=root,
            stdout=log,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    after = snapshot(root)
    changes = [p for p in sorted(before.keys() | after.keys()) if before.get(p) != after.get(p)]
    report = {
        "pytest_exit_code": result.returncode,
        "runtime_files_checked": len(before),
        "changed_runtime_artifacts": changes,
        "scope": "Runtime output, served media, input, logs, databases and report ZIPs outside .research, dependency environments and docs",
    }
    (output / "hygiene.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    raise SystemExit(result.returncode or bool(changes))


if __name__ == "__main__":
    main()
