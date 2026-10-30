"""Transactional append-only research records alongside untouched legacy tables."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .contracts import canonical, digest, now, record, validate
from .types import JsonObject, PathLike

INDEXED_FIELDS = (
    "protocol_key",
    "trial_id",
    "request_record_id",
    "assignment_id",
    "evaluation_slot",
    "metric_id",
    "model",
)


class Store:
    def __init__(self, path: PathLike) -> None:
        "Open the local store and apply idempotent additive schema migrations."
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        "Yield a transactional SQLite connection and always close it."
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def migrate(self) -> None:
        "Create indexes and tables while preserving immutable and legacy payloads."
        with self.connection() as c:
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables and "research_migrations" not in tables:
                backup = self.path.with_name(self.path.name + ".pre-research.bak")
                if backup.exists():
                    raise ValueError(
                        f"Migration backup already exists: {backup}; inspect before continuing"
                    )
                with sqlite3.connect(backup) as dest:
                    c.backup(dest)
            c.executescript("""
                CREATE TABLE IF NOT EXISTS research_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS research_records(
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, experiment_id TEXT,
                    payload TEXT NOT NULL, payload_hash TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS research_kind ON research_records(experiment_id,kind);
                CREATE TABLE IF NOT EXISTS research_jobs(
                    experiment_id TEXT PRIMARY KEY, state TEXT NOT NULL, cancel INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL, error TEXT);
                CREATE TABLE IF NOT EXISTS research_cache(key TEXT PRIMARY KEY, result_id TEXT NOT NULL
                    REFERENCES research_records(id));
                CREATE TABLE IF NOT EXISTS research_claims(key TEXT PRIMARY KEY, state TEXT NOT NULL,
                    created_at TEXT NOT NULL, result_id TEXT REFERENCES research_records(id));
            """)
            if not c.execute("SELECT 1 FROM research_migrations WHERE version=1").fetchone():
                # Preserve exact legacy values and annotate validity, never rewrite a historical score.
                for table in sorted(
                    tables & {"metrics", "composition_metrics", "video_metrics", "embedding_cache"}
                ):
                    for index, row in enumerate(c.execute(f'SELECT * FROM "{table}"')):
                        raw = dict(row)
                        raw = {k: v.hex() if isinstance(v, bytes) else v for k, v in raw.items()}
                        legacy = record(
                            "legacy",
                            source_table=table,
                            source_row=index,
                            original=raw,
                            status="invalid_legacy_result",
                            reason="Legacy evaluator/cache provenance unverified; per-run FID is not standard FID",
                        )
                        self._put(c, legacy)
                c.execute("INSERT INTO research_migrations VALUES(1,?)", (now(),))
            # Expression indexes keep the append-only payload/schema unchanged.
            for field in INDEXED_FIELDS:
                c.execute(
                    f"CREATE INDEX IF NOT EXISTS research_by_{field} ON research_records "
                    f"(experiment_id,kind,json_extract(payload,'$.{field}'),created_at,id)"
                )
            c.execute(
                "CREATE INDEX IF NOT EXISTS research_result_unit ON research_records "
                "(experiment_id,kind,json_extract(payload,'$.metric_id'),"
                "json_extract(payload,'$.trial_id'),json_extract(payload,'$.model'),created_at,id)"
            )
            c.execute("INSERT OR IGNORE INTO research_migrations VALUES(2,?)", (now(),))

    @staticmethod
    def _put(c, item):
        validate(item)
        payload = canonical(item)
        old = c.execute("SELECT payload FROM research_records WHERE id=?", (item["id"],)).fetchone()
        if old and old[0] != payload:
            raise ValueError(f"Immutable record conflict: {item['id']}")
        c.execute(
            "INSERT OR IGNORE INTO research_records VALUES(?,?,?,?,?,?)",
            (
                item["id"],
                item["kind"],
                item.get("experiment_id"),
                payload,
                digest(item),
                item["created_at"],
            ),
        )

    def put(self, item: JsonObject) -> JsonObject:
        "Append one record, rejecting conflicting content under an existing ID."
        with self.connection() as c:
            self._put(c, item)
        return item

    def put_many(self, items: Sequence[JsonObject]) -> None:
        "Append records atomically, rolling back the batch on any conflict."
        with self.connection() as c:
            for item in items:
                self._put(c, item)

    def get(self, id: str) -> JsonObject:
        "Read one immutable record or raise KeyError for an unknown ID."
        with self.connection() as c:
            row = c.execute("SELECT payload FROM research_records WHERE id=?", (id,)).fetchone()
        if row is None:
            raise KeyError(id)
        return json.loads(row[0])

    def list(
        self, kind: str | None = None, experiment_id: str | None = None, **filters: Any
    ) -> list[JsonObject]:
        """Read ordered records, optionally matching whitelisted indexed payload fields."""
        conditions, args = [], []
        for key, value in (("kind", kind), ("experiment_id", experiment_id)):
            if value is not None:
                conditions.append(f"{key}=?")
                args.append(value)
        for key, value in filters.items():
            if key not in INDEXED_FIELDS:
                raise ValueError(f"Unknown record filter: {key}")
            conditions.append(f"json_extract(payload,'$.{key}') IS ?")
            args.append(value)
        with self.connection() as c:
            rows = c.execute(
                "SELECT payload FROM research_records"
                + (" WHERE " + " AND ".join(conditions) if conditions else "")
                + " ORDER BY created_at,id",
                args,
            ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def cached(self, key: str) -> JsonObject | None:
        "Resolve a cache pointer to its recorded result, if present."
        with self.connection() as c:
            row = c.execute("SELECT result_id FROM research_cache WHERE key=?", (key,)).fetchone()
        return self.get(row[0]) if row else None

    def cache(self, key: str, item: JsonObject, slot: str | None = None) -> None:
        "Append an evaluation attempt and update its current cache pointer."
        item["cache_key"] = key
        if slot:
            item["evaluation_slot"] = slot
        with self.connection() as c:
            previous = c.execute(
                "SELECT r.payload FROM research_cache k JOIN research_records r ON r.id=k.result_id WHERE k.key=?",
                (key,),
            ).fetchone()
            if not previous and slot:
                prior = c.execute(
                    "SELECT payload FROM research_records WHERE kind='result' AND json_extract(payload,'$.evaluation_slot')=? ORDER BY created_at DESC,id DESC LIMIT 1",
                    (slot,),
                ).fetchone()
                if prior and json.loads(prior[0])["status"] in {
                    "failed_evaluation",
                    "unavailable_dependency",
                }:
                    previous = prior
            if previous and json.loads(previous[0])["id"] != item["id"]:
                old = json.loads(previous[0])
                item.setdefault("supersedes", old["id"])
                item.setdefault("evaluation_attempt", old.get("evaluation_attempt", 1) + 1)
            elif not previous:
                item.setdefault("evaluation_attempt", 1)
            self._put(c, item)
            c.execute(
                "INSERT INTO research_cache VALUES(?,?) ON CONFLICT(key) DO UPDATE SET result_id=excluded.result_id",
                (key, item["id"]),
            )

    def restore_cache(self, key: str, item: JsonObject) -> None:
        """Restore an exported cache pointer without modifying immutable payloads."""
        with self.connection() as c:
            self._put(c, item)
            c.execute(
                "INSERT INTO research_cache VALUES(?,?) ON CONFLICT(key) DO UPDATE SET result_id=excluded.result_id",
                (key, item["id"]),
            )

    def claim(self, key: str) -> bool:
        "Atomically claim an external request key; return false when it already exists."
        with self.connection() as c:
            return (
                c.execute(
                    "INSERT OR IGNORE INTO research_claims VALUES(?,?,?,NULL)",
                    (key, "started", now()),
                ).rowcount
                == 1
            )

    def finish_claim(self, key: str, result: JsonObject) -> None:
        "Persist a response and mark the corresponding external request complete."
        with self.connection() as c:
            self._put(c, result)
            c.execute(
                "UPDATE research_claims SET state='complete',result_id=? WHERE key=?",
                (result["id"], key),
            )
            c.execute(
                "INSERT INTO research_cache VALUES(?,?) ON CONFLICT(key) DO UPDATE SET result_id=excluded.result_id",
                (key, result["id"]),
            )

    def job(self, experiment_id: str, **changes: Any) -> JsonObject:
        "Read or update the mutable scheduling state for an experiment."
        with self.connection() as c:
            c.execute(
                "INSERT OR IGNORE INTO research_jobs VALUES(?,?,0,?,NULL)",
                (experiment_id, "planned", now()),
            )
            for key, value in changes.items():
                if key not in {"state", "cancel", "error"}:
                    raise ValueError("Unknown job field")
                c.execute(
                    f"UPDATE research_jobs SET {key}=?,updated_at=? WHERE experiment_id=?",
                    (value, now(), experiment_id),
                )
            return dict(
                c.execute(
                    "SELECT * FROM research_jobs WHERE experiment_id=?", (experiment_id,)
                ).fetchone()
            )
