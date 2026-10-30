"""Rebuild a representative legacy DB from recovered rows, then verify migration.

This validates real recovered values in the full legacy schema. It is explicitly
not a migration of a surviving original historical runtime database.
"""

import argparse
import ast
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.contracts import digest, file_hash
from research.store import Store


def snapshot(path, tables):
    with sqlite3.connect(path) as c:
        result = {}
        for table in tables:
            rows = c.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
            normalized = [[v.hex() if isinstance(v, bytes) else v for v in row] for row in rows]
            result[table] = {"rows": len(rows), "content_sha256": digest(normalized)}
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recovered_rows")
    parser.add_argument("output")
    args = parser.parse_args()
    source = Path(args.recovered_rows)
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)
    database = root / "reconstructed-legacy.sqlite3"
    if database.exists():
        raise ValueError("Choose a fresh validation directory")
    repo = Path(__file__).resolve().parents[1]
    before_source = file_hash(source)
    rows = [json.loads(line) for line in source.read_text().splitlines() if line]
    unique = {}
    for row in rows:
        raw = row["original"]
        if raw.get("run_id") and raw.get("timestamp"):
            unique.setdefault(str(raw["run_id"]), raw)
    with sqlite3.connect(database) as c:
        c.execute("PRAGMA foreign_keys=ON")
        c.executescript((repo / "dream_layer_backend/sql_scripts/schema.sql").read_text())
        c.executescript(
            (repo / "dream_layer_backend/sql_scripts/add_composition_metrics.sql").read_text()
        )
        # Reuse literal SQL from the original runtime schema for both optional tables.
        tree = ast.parse((repo / "dream_layer_backend/data/scripts/database.py").read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and any(
                    "CREATE TABLE IF NOT EXISTS " + name + " (" in node.value
                    for name in ("embedding_cache", "video_metrics")
                )
            ):
                c.execute(node.value)
        columns = [x[1] for x in c.execute("PRAGMA table_info(runs)")]
        for rid, row in unique.items():
            fields = [k for k in columns if row.get(k) is not None]
            c.execute(
                "INSERT INTO runs ("
                + ",".join(fields)
                + ") VALUES ("
                + ",".join("?" for _ in fields)
                + ")",
                [row[k] for k in fields],
            )
            c.execute(
                "INSERT INTO assets(run_id,timestamp,asset_key,asset_value,full_path) VALUES(?,?,?,?,?)",
                (rid, row["timestamp"], "image", row.get("asset_value"), row.get("full_path")),
            )
            c.execute(
                "INSERT INTO metrics(run_id,timestamp,clip_score_mean,fid_score) VALUES(?,?,?,?)",
                (rid, row["timestamp"], row.get("clip_score_mean"), row.get("fid_score")),
            )
            if row.get("macro_f1") is not None:
                fields = [
                    "run_id",
                    "prompt_text",
                    "macro_precision",
                    "macro_recall",
                    "macro_f1",
                    "per_class_metrics",
                    "detected_objects",
                    "missing_objects",
                ]
                c.execute(
                    "INSERT INTO composition_metrics ("
                    + ",".join(fields)
                    + ") VALUES ("
                    + ",".join("?" for _ in fields)
                    + ")",
                    [row.get(k) for k in fields],
                )
        # Explicit synthetic sentinels cover binary storage, null and successful zero.
        c.execute(
            "INSERT INTO embedding_cache(source_type,source_id,embedding_type,model_name,embedding_data,embedding_dim) VALUES(?,?,?,?,?,?)",
            ("synthetic", "sentinel", "fixture", "fixture", b"\x00\xff\x80", 3),
        )
        c.execute(
            "INSERT INTO video_metrics(run_id,timestamp,fvd_score,video_ssim_mean) VALUES(?,?,NULL,0)",
            (next(iter(unique)), "2026-10-30T00:00:00"),
        )
    tables = [
        "runs",
        "assets",
        "metrics",
        "composition_metrics",
        "embedding_cache",
        "video_metrics",
    ]
    before = snapshot(database, tables)
    store = Store(database)
    backup = database.with_name(database.name + ".pre-research.bak")
    assert snapshot(backup, tables) == snapshot(database, tables) == before
    first = store.list("legacy")
    assert Store(database).list("legacy") == first
    assert len(first) == sum(before[t]["rows"] for t in tables if t not in {"runs", "assets"})
    assert file_hash(source) == before_source
    with sqlite3.connect(database) as c:
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
    report = {
        "status": "success",
        "source_sha256": before_source,
        "recovered_rows": len(rows),
        "reconstructed_runs": len(unique),
        "duplicate_run_policy": "First recovered workbook row per run ID for this validation fixture only",
        "source_unchanged": True,
        "backup_and_migrated_legacy_rows_identical": True,
        "idempotent": True,
        "foreign_keys_valid": True,
        "legacy_snapshots": len(first),
        "tables": before,
        "backup_sha256": file_hash(backup),
        "limitation": "Reconstructed full-schema DB with real historical workbook values and two synthetic optional-table sentinels; original historical runtime DB unavailable",
    }
    (root / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
