"""Blinded local assignments, independent labels and lossless CSV/JSONL exchange."""

from __future__ import annotations

import csv
import io
import json
import random
from collections.abc import Sequence

from .contracts import digest, record, validate
from .judges import rubric_validate
from .store import Store
from .types import JsonObject


def assign(
    store: Store,
    experiment_id: str,
    rater_id: str,
    rubric: JsonObject,
    mode: str = "pointwise",
    seed: int = 0,
    practice: Sequence[str] | None = None,
) -> list[JsonObject]:
    "Create blinded assignments or reuse matching rater/rubric/media units."
    if not rater_id.strip() or mode not in {"pointwise", "pairwise"}:
        raise ValueError("Pseudonymous rater and supported mode required")
    rubric_validate(rubric)
    all_assets = store.list("asset", experiment_id)
    assets = [a for a in all_assets if a.get("role") != "reference"]
    references = [a for a in all_assets if a.get("role") == "reference"]
    trials = {t["id"]: t for t in store.list("trial", experiment_id)}
    groups = {}
    for asset in assets:
        trial = trials[asset["trial_id"]]
        groups.setdefault((trial["prompt_id"], trial["repeat_index"]), []).append(asset)
    rng = random.Random(seed)
    batches = (
        [[a] for a in assets]
        if mode == "pointwise"
        else [v for v in groups.values() if len(v) == 2]
    )
    rng.shuffle(batches)
    rubric_hash = digest(rubric)
    existing = {}
    for assignment in store.list("assignment", experiment_id):
        if (
            assignment["rater_id"] == rater_id
            and assignment["mode"] == mode
            and assignment["rubric_hash"] == rubric_hash
        ):
            existing.setdefault(frozenset(assignment["asset_ids"]), assignment)
    result = []
    for index, batch in enumerate(batches):
        batch = sorted(batch, key=lambda a: a["id"])
        rng.shuffle(batch)
        prior = existing.get(frozenset(a["id"] for a in batch))
        if prior:
            result.append(prior)
            continue
        assignment_id = digest(
            [experiment_id, rater_id, rubric, mode, seed, [a["id"] for a in batch]]
        )
        try:
            item = store.get(assignment_id)
        except KeyError:
            trial = trials[batch[0]["trial_id"]]
            prompt = store.get(trial["prompt_id"])
            item = record(
                "assignment",
                experiment_id,
                id=assignment_id,
                rater_id=rater_id,
                rubric=rubric,
                mode=mode,
                seed=seed,
                asset_ids=[a["id"] for a in batch],
                prompt_text=prompt["text"],
                presentation_index=index,
                practice=bool(
                    set(practice or [])
                    & {assignment_id, prompt.get("source_id"), *[a["id"] for a in batch]}
                ),
                rubric_hash=rubric_hash,
                reference_ids=[
                    a["id"]
                    for a in references
                    if not a.get("prompt_source_ids")
                    or prompt["source_id"] in a["prompt_source_ids"]
                ],
            )
            store.put(item)
        existing[frozenset(item["asset_ids"])] = item
        result.append(item)
    return result


def blinded(store: Store, assignment: JsonObject) -> JsonObject:
    "Return review-visible fields without model names or source filenames."
    labels = store.list("annotation", assignment["experiment_id"], assignment_id=assignment["id"])
    return {
        k: assignment[k]
        for k in (
            "id",
            "rater_id",
            "rubric",
            "mode",
            "prompt_text",
            "practice",
            "presentation_index",
        )
    } | {
        "media": [
            {
                "slot": i,
                "modality": store.get(a)["media"]["modality"],
                "url": f"/api/research/review/{assignment['id']}/media/{i}",
            }
            for i, a in enumerate(assignment["asset_ids"])
        ],
        "references": [
            {
                "slot": i,
                "url": f"/api/research/review/{assignment['id']}/reference/{i}",
                "modality": store.get(a)["media"]["modality"],
            }
            for i, a in enumerate(assignment.get("reference_ids", []))
        ],
        "completed": bool(labels),
        "annotations": [
            {
                "id": a["id"],
                "labels": a["labels"],
                "comment": a.get("comment"),
                "adjudicates": a.get("adjudicates"),
            }
            for a in labels
        ],
    }


def annotate(store: Store, assignment_id: str, data: JsonObject) -> JsonObject:
    "Validate and append an independent annotation or explicit adjudication."
    assignment = store.get(assignment_id)
    if assignment["kind"] != "assignment" or data.get("rater_id") != assignment["rater_id"]:
        raise ValueError("Annotation rater does not match assignment")
    labels = data.get("labels", {})
    if set(labels) != {c["id"] for c in assignment["rubric"]["criteria"]}:
        raise ValueError("Labels must cover exactly the rubric criteria")
    allowed = (
        {"A", "B", "tie", "uncertain"}
        if assignment["mode"] == "pairwise"
        else {"pass", "fail", "uncertain", "not_applicable"}
    )
    if any(v not in allowed for v in labels.values()):
        raise ValueError("Label incompatible with assignment mode")
    existing = store.list("annotation", assignment["experiment_id"], assignment_id=assignment_id)
    if existing and not data.get("adjudicates"):
        matching = next(
            (
                a
                for a in existing
                if not a.get("adjudicates")
                and a["labels"] == labels
                and a.get("comment", "") == data.get("comment", "")
            ),
            None,
        )
        if matching:
            return matching
        raise ValueError("Independent annotation already exists; create an explicit adjudication")
    for aid in data.get("adjudicates", []):
        original = store.get(aid)
        if (
            original["kind"] != "annotation"
            or original["experiment_id"] != assignment["experiment_id"]
        ):
            raise ValueError("Invalid adjudication source")
        if original["rubric_hash"] != assignment["rubric_hash"]:
            raise ValueError("Adjudication must use the same rubric")
        if set(store.get(original["assignment_id"])["asset_ids"]) != set(assignment["asset_ids"]):
            raise ValueError("Adjudication must address the same media unit")
    durations = [store.get(a)["media"].get("duration") for a in assignment["asset_ids"]]
    for start, end in data.get("intervals", []):
        if not 0 <= start <= end or any(d is not None and end > d for d in durations):
            raise ValueError("Failure interval exceeds media duration")
    annotation = record(
        "annotation",
        assignment["experiment_id"],
        assignment_id=assignment_id,
        rater_id=assignment["rater_id"],
        labels=labels,
        rubric_hash=digest(assignment["rubric"]),
        intervals=data.get("intervals", []),
        comment=data.get("comment", ""),
        aesthetic_rating=data.get("aesthetic_rating"),
        adjudicates=data.get("adjudicates", []),
        source_references=data.get("source_references", []),
    )
    return store.put(annotation)


def export_annotations(
    store: Store, experiment_id: str, format: str = "jsonl", blinded_export: bool = False
) -> str:
    "Serialize labels as CSV or JSONL, optionally removing identifying provenance."
    rows = store.list("annotation", experiment_id)
    if blinded_export:
        rows = [{**r, "rater_id": digest(r["rater_id"])[:16]} for r in rows]
    if format == "jsonl":
        return "\n".join(json.dumps(r, ensure_ascii=False, allow_nan=False) for r in rows)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=["schema_version", "id", "record_json"])
    writer.writeheader()
    for r in rows:
        writer.writerow(
            {
                "schema_version": 1,
                "id": r["id"],
                "record_json": json.dumps(r, ensure_ascii=False, allow_nan=False),
            }
        )
    return out.getvalue()


def import_annotations(
    store: Store, content: str, format: str = "jsonl", experiment_id: str | None = None
) -> int:
    "Validate annotation references and append records without duplicating independent votes."
    rows = (
        [json.loads(r["record_json"]) for r in csv.DictReader(io.StringIO(content))]
        if format == "csv"
        else [json.loads(line) for line in content.splitlines() if line.strip()]
    )
    seen = set()
    for row in rows:
        validate(row)
        if row["kind"] != "annotation":
            raise ValueError("Only annotation records allowed")
        if experiment_id and row["experiment_id"] != experiment_id:
            raise ValueError("Cross-experiment annotation import")
        assignment = store.get(row["assignment_id"])
        if row["experiment_id"] != assignment["experiment_id"]:
            raise ValueError("Annotation and assignment belong to different experiments")
        if (
            assignment["rater_id"] != row["rater_id"]
            or digest(assignment["rubric"]) != row["rubric_hash"]
        ):
            raise ValueError("Rater/rubric provenance mismatch")
        allowed = (
            {"A", "B", "tie", "uncertain"}
            if assignment["mode"] == "pairwise"
            else {"pass", "fail", "uncertain", "not_applicable"}
        )
        if set(row["labels"]) != {c["id"] for c in assignment["rubric"]["criteria"]} or any(
            v not in allowed for v in row["labels"].values()
        ):
            raise ValueError("Imported labels do not match assignment rubric/mode")
        existing = [
            a
            for a in store.list(
                "annotation", row["experiment_id"], assignment_id=row["assignment_id"]
            )
            if not a.get("adjudicates")
        ]
        if existing and not row.get("adjudicates") and any(a["id"] != row["id"] for a in existing):
            raise ValueError("Duplicate independent assignment annotation")
        if row["assignment_id"] in seen and not row.get("adjudicates"):
            raise ValueError("Duplicate independent assignment annotation")
        seen.add(row["assignment_id"])
        for aid in assignment["asset_ids"]:
            if store.get(aid)["kind"] != "asset":
                raise ValueError("Orphan annotation asset")
            duration = store.get(aid)["media"].get("duration")
            if duration is not None and any(end > duration for _, end in row.get("intervals", [])):
                raise ValueError("Failure interval exceeds media duration")
        for aid in row.get("adjudicates", []):
            original = store.get(aid)
            if (
                original["kind"] != "annotation"
                or original["experiment_id"] != row["experiment_id"]
            ):
                raise ValueError("Invalid adjudication source")
            if original["rubric_hash"] != row["rubric_hash"]:
                raise ValueError("Adjudication must use the same rubric")
            if set(store.get(original["assignment_id"])["asset_ids"]) != set(
                assignment["asset_ids"]
            ):
                raise ValueError("Adjudication must address the same media unit")
    store.put_many(rows)
    return len(rows)
