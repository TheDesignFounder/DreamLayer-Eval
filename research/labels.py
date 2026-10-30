"""Auditable annotation selection; raw records are never changed or discarded."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .store import Store
from .types import JsonObject


def unit_key(annotation: JsonObject, assignments: Mapping[str, Any]) -> tuple[Any, ...]:
    "Identify one rater/rubric/media unit independently of presentation order."
    assignment = assignments[annotation["assignment_id"]]
    return (
        tuple(sorted(assignment["asset_ids"])),
        annotation["rubric_hash"],
        annotation["rater_id"],
    )


def select_annotations(
    store: Store, eid: str, view: str = "raw"
) -> tuple[list[JsonObject], list[JsonObject]]:
    "Select current raw or adjudicated labels and report duplicate-rater warnings."
    if view not in {"raw", "adjudicated"}:
        raise ValueError("label_view must be raw or adjudicated")
    assignments = {a["id"]: a for a in store.list("assignment", eid)}
    records = store.list("annotation", eid)
    by_id = {a["id"]: a for a in records}
    selected, warnings = {}, []
    for a in records:
        if a.get("adjudicates"):
            continue
        key = unit_key(a, assignments)
        if key in selected:
            warnings.append(
                {
                    "kind": "duplicate_rater_unit",
                    "policy": "latest_created_at_then_id",
                    "selected": a["id"],
                    "excluded": selected[key]["id"],
                    "rater_id": a["rater_id"],
                }
            )
        selected[key] = deepcopy(a)
    if view == "adjudicated":

        def originals(a, seen=()):
            if a["id"] in seen:
                raise ValueError("Cyclic adjudication references")
            if not a.get("adjudicates"):
                return [a]
            return [
                raw
                for source in a["adjudicates"]
                for raw in originals(by_id[source], (*seen, a["id"]))
            ]

        for adj in records:
            if not adj.get("adjudicates"):
                continue
            own = assignments[adj["assignment_id"]]
            for raw in originals(adj):
                key = unit_key(raw, assignments)
                if key not in selected:
                    continue
                effective = selected[key]
                target = assignments[effective["assignment_id"]]
                labels = {}
                for criterion, value in adj["labels"].items():
                    if value in {"A", "B"}:
                        winner = own["asset_ids"][0 if value == "A" else 1]
                        value = "A" if target["asset_ids"][0] == winner else "B"
                    labels[criterion] = value
                effective.update(
                    labels=labels,
                    adjudication_id=adj["id"],
                    independent=False,
                    source_annotation_ids=[raw["id"], adj["id"]],
                    label_origin="adjudicated",
                )
    return list(selected.values()), warnings
