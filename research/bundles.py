"""Portable, validated ZIP bundles with explicit media inclusion and content hashes."""

from __future__ import annotations

import copy
import csv
import importlib.metadata
import io
import json
import platform
import zipfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from . import __version__
from .contracts import canonical, digest, file_hash, redact, validate
from .store import Store
from .types import PathLike


def export_bundle(store: Store, eid: str, output: PathLike, include_media: bool = True) -> str:
    "Export immutable records and optional media with a content-hash manifest."
    records = copy.deepcopy(store.list(experiment_id=eid))
    if not any(r["kind"] == "experiment" for r in records):
        raise ValueError("Experiment not found")
    media = {}
    for r in records:
        if r["kind"] == "asset":
            p = Path(r["locator"])
            if not p.is_file() or file_hash(p) != r["sha256"]:
                raise ValueError("Missing or changed asset: " + r["original_filename"])
            member = "media/" + r["sha256"] + p.suffix.lower()
            if include_media:
                media[member] = p
            r["locator"] = member if include_media else "sha256:" + r["sha256"]
    files = {"records.jsonl": ("\n".join(canonical(redact(r)) for r in records) + "\n").encode()}
    results = [r for r in records if r["kind"] == "result"]
    out = io.StringIO()
    writer = csv.DictWriter(
        out,
        fieldnames=[
            "id",
            "metric_id",
            "metric_version",
            "scope",
            "status",
            "score",
            "reason",
            "record_json",
        ],
    )
    writer.writeheader()
    for r in results:
        writer.writerow(
            {
                **{k: r.get(k) for k in writer.fieldnames if k != "record_json"},
                "record_json": canonical(r),
            }
        )
    files["results.csv"] = out.getvalue().encode()
    code_root = Path(__file__).parent
    code_hash = digest({p.name: file_hash(p) for p in sorted(code_root.glob("*.py"))})
    provenance = {
        "schema_version": 1,
        "package_version": __version__,
        "code_hash": code_hash,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dependencies": {
            p: importlib.metadata.version(p) for p in ("Flask", "numpy", "scipy", "Pillow", "av")
        },
        "include_media": include_media,
        "experiment_id": eid,
    }
    files["provenance.json"] = canonical(provenance).encode()
    import hashlib

    manifest = {
        "schema_version": 1,
        "files": {
            **{name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
            **{name: file_hash(p) for name, p in media.items()},
        },
        "experiment_id": eid,
    }
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)
        for name, path in media.items():
            z.write(path, name)
        z.writestr("manifest.json", canonical(manifest))
    return str(output)


def import_bundle(
    store: Store,
    bundle: PathLike,
    media_root: PathLike,
    media_lookup: Mapping[str, Any] | None = None,
) -> str:
    "Validate a portable archive, restore records/caches, and return its experiment ID."
    import hashlib

    root = Path(media_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle) as z:
        names = z.namelist()
        if len(set(names)) != len(names):
            raise ValueError("Duplicate archive members")
        for info in z.infolist():
            path = PurePosixPath(info.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in info.filename
                or (info.external_attr >> 16) & 0o170000 == 0o120000
            ):
                raise ValueError("Unsafe archive member")
        if sum(i.file_size for i in z.infolist()) > 2_000_000_000:
            raise ValueError("Bundle exceeds 2 GB uncompressed budget")
        manifest = json.loads(z.read("manifest.json"))
        if manifest.get("schema_version") != 1 or set(names) != set(manifest["files"]) | {
            "manifest.json"
        }:
            raise ValueError("Archive membership differs from manifest")
        for name, sha in manifest["files"].items():
            h = hashlib.sha256()
            with z.open(name) as f:
                for block in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(block)
            if h.hexdigest() != sha:
                raise ValueError("Archive content hash mismatch")
        records = [json.loads(line) for line in z.read("records.jsonl").splitlines() if line]
        ids = {r["id"] for r in records}
        if len(ids) != len(records):
            raise ValueError("Duplicate record IDs")
        for r in records:
            validate(r)
            if r.get("experiment_id") != manifest["experiment_id"]:
                raise ValueError("Cross-experiment record")
            for field in (
                "trial_id",
                "prompt_id",
                "parent_asset_id",
                "assignment_id",
                "supersedes",
                "request_record_id",
                "reconciliation_id",
                "retry_of",
            ):
                if r.get(field) and r[field] not in ids:
                    raise ValueError("Orphan record reference: " + field)
            if any(
                a not in ids
                for field in (
                    "asset_ids",
                    "reference_ids",
                    "reference_asset_ids",
                    "adjudicates",
                    "supersedes_ids",
                )
                for a in r.get(field, [])
            ):
                raise ValueError("Orphan asset membership")
            if r["kind"] == "asset":
                locator = r["locator"]
                if locator.startswith("sha256:"):
                    p = Path((media_lookup or {}).get(r["sha256"], ""))
                    if not p.is_file() or file_hash(p) != r["sha256"]:
                        raise ValueError(
                            "Referenced media unavailable; supply a hash-to-file lookup"
                        )
                    r["locator"] = str(p.resolve())
                else:
                    if (
                        locator not in manifest["files"]
                        or not locator.startswith("media/")
                        or manifest["files"][locator] != r["sha256"]
                    ):
                        raise ValueError("Asset membership/hash mismatch")
                    dest = root / PurePosixPath(locator).name
                    with z.open(locator) as src, open(dest, "wb") as target:
                        import shutil

                        shutil.copyfileobj(src, target)
                    r["locator"] = str(dest)
    # Existing identical exports can be imported idempotently despite locator changes.
    for r in records:
        try:
            existing = store.get(r["id"])
        except KeyError:
            continue
        if r["kind"] == "asset" and {k: v for k, v in existing.items() if k != "locator"} == {
            k: v for k, v in r.items() if k != "locator"
        }:
            r["locator"] = existing["locator"]
    store.put_many(records)
    for item in records:
        if item.get("cache_key"):
            store.restore_cache(item["cache_key"], item)
        if item["kind"] == "judge_call" and item.get("phase") == "request":
            store.claim(item["request_key"])
    for item in records:
        if item["kind"] == "judge_call" and item.get("phase") == "response":
            store.finish_claim(item["request_key"], item)
    store.job(manifest["experiment_id"], state="imported")
    return manifest["experiment_id"]
