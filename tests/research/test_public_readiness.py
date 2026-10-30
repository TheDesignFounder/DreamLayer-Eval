"""Reference estimators and persistence invariants for public distributions."""

import itertools
import json
import sqlite3
import zipfile
from pathlib import Path

import numpy as np
import pytest
from jsonschema import Draft202012Validator
from sklearn.metrics import cohen_kappa_score

from research import analysis, platforms
from research.contracts import record
from research.store import Store


def test_kappa_matches_sklearn_with_uncertainty_and_missing_labels():
    rng = np.random.default_rng(891)
    for count in (2, 7, 100):
        left = rng.choice(["pass", "fail", "uncertain"], count).tolist()
        right = rng.choice(["pass", "fail", "uncertain"], count).tolist()
        result = analysis.agreement([*zip(left, right), (None, "pass"), ("fail", None)])
        assert result["n"] == count
        assert result["cohen_kappa"] == pytest.approx(cohen_kappa_score(left, right), abs=1e-12)


def test_cluster_interval_matches_exact_two_cluster_distribution():
    rows = [{"group_id": "zero", "value": 0.0}] * 4 + [{"group_id": "ten", "value": 10.0}] * 4
    exact_means = [np.mean(pair) for pair in itertools.product([0.0, 10.0], repeat=2)]
    result = analysis.cluster_interval(rows, seed=721, iterations=2000)
    assert result["mean"] == 5.0 and result["groups"] == 2 and result["n"] == 8
    assert [result["low"], result["high"]] == pytest.approx(
        np.quantile(exact_means, [0.025, 0.975], method="inverted_cdf")
    )


def test_index_migration_preserves_payloads_and_rejects_unknown_fields(tmp_path):
    path = tmp_path / "schema1.sqlite3"
    store = Store(path)
    expected = [
        record("judge_call", "exp", protocol_key=f"protocol-{i % 3}", phase="request")
        for i in range(30)
    ]
    store.put_many(expected)
    with sqlite3.connect(path) as conn:
        for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'research_by_%'"
        ).fetchall():
            conn.execute(f'DROP INDEX "{name}"')
        conn.execute("DELETE FROM research_migrations WHERE version=2")
        before = conn.execute(
            "SELECT id,payload,payload_hash FROM research_records ORDER BY id"
        ).fetchall()
    upgraded = Store(path)
    assert len(upgraded.list("judge_call", "exp", protocol_key="protocol-1")) == 10
    with upgraded.connection() as conn:
        assert [
            tuple(row)
            for row in conn.execute(
                "SELECT id,payload,payload_hash FROM research_records ORDER BY id"
            )
        ] == before
        plan = conn.execute(
            "EXPLAIN QUERY PLAN SELECT payload FROM research_records WHERE experiment_id=? AND kind=? AND json_extract(payload,'$.protocol_key') IS ? ORDER BY created_at,id",
            ("exp", "judge_call", "protocol-1"),
        ).fetchall()
        assert any("research_by_protocol_key" in row["detail"] for row in plan)
    assert Store(path).list("judge_call", "exp") == upgraded.list("judge_call", "exp")
    with pytest.raises(ValueError, match="Unknown record filter"):
        store.list("judge_call", "exp", **{"unsafe'field": "value"})


def test_windows_fails_with_explicit_platform_message(monkeypatch):
    monkeypatch.setattr(platforms.os, "name", "nt")
    with pytest.raises(RuntimeError, match="Windows is unsupported"):
        platforms.require_supported_platform()


def test_frozen_schema_accepts_original_bundle_and_rejects_bad_scores():
    root = Path(__file__).resolve().parents[2]
    schema = json.loads((root / "research/schemas/record-v1.json").read_text())
    validator = Draft202012Validator(schema)
    Draft202012Validator.check_schema(schema)
    with zipfile.ZipFile(root / "tests/fixtures/legacy-browser-v1.zip") as archive:
        records = [json.loads(line) for line in archive.read("records.jsonl").splitlines()]
        for row in records:
            validator.validate(row)
        manifest = json.loads(archive.read("manifest.json"))
        Draft202012Validator(
            json.loads((root / "research/schemas/bundle-v1.json").read_text())
        ).validate(manifest)
    result = next(row for row in records if row["kind"] == "result")
    assert list(
        validator.iter_errors(
            {**result, "status": "failed_evaluation", "score": 0, "reason": "failure"}
        )
    )
    assert list(validator.iter_errors({**result, "schema_version": 999}))
