"""Versioned compatibility projections for the old multi-service application."""

from __future__ import annotations

import json
import sqlite3

from .contracts import digest, file_hash
from .metrics import result
from .store import Store
from .types import JsonObject, PathLike


def save_composition(
    db_path: PathLike, run_id: str, prompt: str, image_path: PathLike, values: JsonObject
) -> bool:
    "Persist a corrected composition result for the legacy application adapter."
    details = values["object_criteria_result"]
    sha = file_hash(image_path)
    store = Store(db_path)
    key = digest(["legacy-adapter", run_id, sha, prompt, values])
    if not store.cached(key):
        output = result(
            "object_criteria",
            [],
            config={"prompt": prompt, "criteria": values.get("target_objects")},
            score=details["score"],
            status=details["status"],
            reason=details.get("reason"),
            details=details,
        )
        output.update(
            source_run_id=run_id,
            source_sha256=sha,
            membership_hash=digest([sha]),
            compatibility_payload=values,
        )
        store.cache(key, output)
    return True


def composition(conn: sqlite3.Connection, run_id: str) -> JsonObject | None:
    "Return the latest corrected composition projection for a legacy run."
    row = conn.execute(
        "SELECT payload FROM research_records WHERE kind='result' AND json_extract(payload,'$.source_run_id')=? AND json_extract(payload,'$.metric_id')='object_criteria' ORDER BY created_at DESC,id DESC LIMIT 1",
        (run_id,),
    ).fetchone()
    return json.loads(row[0])["compatibility_payload"] if row else None


def project(conn: sqlite3.Connection, row: JsonObject) -> JsonObject:
    "Add explicit validity fields and corrected values to a legacy report row."
    row["fid_status"] = (
        "invalid_legacy_result" if row.get("legacy_fid_score") is not None else "not_applicable"
    )
    if row.get("macro_f1") is not None:
        row["composition_status"] = "invalid_legacy_result"
        row["composition_limitation"] = "Legacy detector F1; not full prompt correctness"
    corrected = composition(conn, row.get("run_id"))
    if corrected:
        row.update(corrected)
        row["composition_status"] = corrected["object_criteria_result"]["status"]
    return row
