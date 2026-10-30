"""Run actual CLIP and YOLO inference; downloads require an explicit flag."""

import argparse
import importlib.metadata
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw

from research import experiments, metrics
from research.contracts import file_hash, now, record

CLIP_MODEL = "openai/clip-vit-base-patch32"
CLIP_REVISION = "3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268"
YOLO_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", default=".research/model-smoke")
    parser.add_argument("--allow-download", action="store_true")
    args = parser.parse_args()
    root = Path(args.directory).resolve()
    root.mkdir(parents=True, exist_ok=False)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(root / "yolo-settings"))
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    report = {
        "started_at": now(),
        "provider_calls": 0,
        "device": "cpu",
        "results": {},
        "limitation": "Generated shapes exercise inference and provenance, not semantic accuracy or model quality.",
    }
    image = Image.new("RGB", (256, 256), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 40, 110, 190), fill="red")
    draw.ellipse((135, 90, 235, 190), fill="blue")
    path = root / "shapes.png"
    image.save(path)
    asset = record("asset", **experiments.managed_asset(path, root / "media"))
    report["fixture_sha256"] = asset["sha256"]
    weights = root / "yolov8n.pt"
    for metric_id in ("clip_cosine", "object_criteria"):
        started = time.perf_counter()
        try:
            if metric_id == "clip_cosine":
                settings = {
                    "model": CLIP_MODEL,
                    "revision": CLIP_REVISION,
                    "device": "cpu",
                    "allow_download": args.allow_download,
                }
            else:
                if not weights.exists() and args.allow_download:
                    import requests

                    response = requests.get(YOLO_URL, timeout=120)
                    response.raise_for_status()
                    weights.write_bytes(response.content)
                settings = {"weights": str(weights), "threshold": 0.25}
            prompt = "a red rectangle and a blue circle" if metric_id == "clip_cosine" else "a dog"
            first = metrics.evaluate(metric_id, [asset], prompt, settings)
            second = metrics.evaluate(
                metric_id, [asset], prompt, {**settings, "allow_download": False}
            )
            assert first["status"] == second["status"] == "success", (
                first.get("reason"),
                second.get("reason"),
            )
            assert abs(first["score"] - second["score"]) < 1e-7
            details = first.get("details", {})
            if metric_id == "object_criteria":
                assert len(details["detector"]["classes"]) == 80
                assert details["detector"]["weights_sha256"] == file_hash(weights)
                provenance = {
                    "weights_source": YOLO_URL,
                    "weights_sha256": file_hash(weights),
                    "vocabulary_size": 80,
                    "criteria": details.get("criteria"),
                    "detected_objects": details.get("detected_objects"),
                }
            else:
                from huggingface_hub import snapshot_download

                snapshot = Path(
                    snapshot_download(CLIP_MODEL, revision=CLIP_REVISION, local_files_only=True)
                )
                hashes = {p.name: file_hash(p) for p in snapshot.iterdir() if p.is_file()}
                provenance = {
                    "model": CLIP_MODEL,
                    "revision": CLIP_REVISION,
                    "snapshot_sha256": hashes,
                    "details": details,
                }
            report["results"][metric_id] = {
                "status": "success",
                "score": first["score"],
                "repeat_score": second["score"],
                "offline_repeat": True,
                "elapsed_seconds": time.perf_counter() - started,
                "provenance": provenance,
            }
        except Exception as exc:
            report["results"][metric_id] = {
                "status": "failed_or_unavailable",
                "reason": f"{type(exc).__name__}: {exc}",
            }
        (root / "result.json").write_text(json.dumps(report, indent=2))
        print(metric_id, report["results"][metric_id]["status"], flush=True)
    report["dependencies"] = {
        p: importlib.metadata.version(p)
        for p in ("torch", "torchvision", "transformers", "ultralytics", "Pillow", "numpy")
    }
    (root / "result.json").write_text(json.dumps(report, indent=2))
    raise SystemExit(0 if all(r["status"] == "success" for r in report["results"].values()) else 1)


if __name__ == "__main__":
    main()
