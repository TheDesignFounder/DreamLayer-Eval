"""Import recovered rankings without inventing asset links or numeric scores."""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import digest, record
from .history import human_rankings
from .store import Store
from .types import JsonObject, PathLike


def import_rankings(store: Store, path: PathLike) -> JsonObject:
    "Import historical rankings without inventing asset identity or reviewer metadata."
    path = Path(path)
    data = human_rankings(path) if path.suffix.lower() == ".csv" else json.loads(path.read_text())
    data = data.get("human", data)
    if not data or not data.get("source_sha256") or not isinstance(data.get("rankings"), list):
        raise ValueError(
            "Expected historical human CSV or recovery JSON with source hash and rankings"
        )
    eid = digest(["historical-rankings-v1", data["source_sha256"]])
    try:
        return store.get(eid)
    except KeyError:
        pass
    config = {
        "schema_version": 1,
        "name": "Historical human rankings: " + data["source_filename"],
        "mode": "historical_rankings",
        "source_sha256": data["source_sha256"],
        "prompts": [],
        "models": [],
        "metrics": [],
        "judges": [],
        "exploratory": True,
        "blinded": False,
        "independent_rater_count": 1,
    }
    experiment = record("experiment", eid, id=eid, config=config, config_hash=digest(config))
    rows = [experiment]
    for rank in data["rankings"]:
        rows.append(
            record(
                "historical_ranking",
                eid,
                id=digest([eid, rank["source_row"]]),
                source_sha256=data["source_sha256"],
                source_filename=data["source_filename"],
                author=data.get("author", "historical-author-1"),
                test=data.get("test"),
                exploratory=True,
                blinded=False,
                vlm_used=False,
                independent_rater_count=1,
                **rank,
            )
        )
    store.put_many(rows)
    store.job(eid, state="imported")
    return experiment
