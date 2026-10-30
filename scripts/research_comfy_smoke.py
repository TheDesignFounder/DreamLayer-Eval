"""Exercise a real local ComfyUI procedural graph; this is not diffusion inference."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from PIL import Image

from research import analysis, bundles, experiments
from research.contracts import digest
from research.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8188")
    args = parser.parse_args()
    root = Path(args.directory).resolve()
    root.mkdir(parents=True, exist_ok=False)
    workflow = {
        "1": {
            "class_type": "EmptyImage",
            "inputs": {"width": 64, "height": 48, "batch_size": 1, "color": 0},
        },
        "2": {
            "class_type": "SaveImage",
            "inputs": {"images": ["1", 0], "filename_prefix": "research_procedural_smoke"},
        },
    }
    config = {
        "schema_version": 1,
        "name": "Actual ComfyUI procedural smoke",
        "models": ["procedural-color"],
        "prompts": [{"id": "p", "text": "Procedural solid color; prompt is not a model input"}],
        "metrics": [{"id": "pixel_luminance"}],
        "parameters": {"procedural-color": {"color": 0x336699}},
        "generation": {
            "base_url": args.base_url,
            "allow_provider_calls": True,
            "workflow": workflow,
            "bindings": {"color": [["1", "color"]]},
            "timeout_seconds": 30,
            "poll_seconds": 0.1,
            "identity": {
                "provider": "local-ComfyUI",
                "model": "EmptyImage/SaveImage",
                "version": "0.3.40",
            },
        },
    }
    store = Store(root / "study.sqlite3")
    eid = experiments.create(store, config, root / "media")["id"]
    job = experiments.execute(store, eid, root / "media")
    assert job["state"] == "complete"
    assets = store.list("asset", eid)
    assert len(assets) == 1
    with Image.open(assets[0]["locator"]) as image:
        assert image.size == (64, 48) and image.getpixel((0, 0)) == (51, 102, 153)
    results = store.list("result", eid)
    assert len(results) == 1 and results[0]["status"] == "success"
    attempts = store.list("attempt", eid)
    assert attempts[-1]["status"] == "success"
    jobs = {r["provider_request_id"] for r in attempts if r.get("provider_request_id")}
    assert len(jobs) == 1
    before = store.list(experiment_id=eid)
    experiments.execute(store, eid, root / "media")
    assert store.list(experiment_id=eid) == before
    bundles.export_bundle(store, eid, root / "experiment.zip")
    replay = Store(root / "fresh.sqlite3")
    bundles.import_bundle(replay, root / "experiment.zip", root / "fresh-media")
    experiments.execute(replay, eid, root / "fresh-media")
    assert analysis.summarize(replay, eid) == analysis.summarize(store, eid)
    stats = requests.get(args.base_url + "/system_stats", timeout=5).json()
    report = {
        "status": "passed",
        "execution": "Real local ComfyUI CPU queue, history, image retrieval and parameter binding",
        "generation_kind": "Procedural EmptyImage → SaveImage; no diffusion or text-to-image model",
        "workflow_sha256": digest(workflow),
        "comfyui_version": stats.get("system", {}).get("comfyui_version", "0.3.40"),
        "job_count": len(jobs),
        "asset_sha256": assets[0]["sha256"],
        "dimensions": [64, 48],
        "rgb": [51, 102, 153],
        "luminance": results[0]["score"],
        "resume_added_records": 0,
        "fresh_replay_exact": True,
        "paid_provider_calls": 0,
        "limitations": "Does not verify checkpoint loading, diffusion inference, provider nodes, text fidelity or production throughput. Optional audio/upscale nodes were unavailable.",
    }
    (root / "result.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
