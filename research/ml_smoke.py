"""Opt-in actual neural feature extraction; never a substitute for scientific validation."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

from .contracts import now
from .fid import features, frechet_from_features
from .types import JsonObject, PathLike


def run(directory: PathLike, allow_download: bool = False) -> JsonObject:
    "Exercise real Inception extraction on synthetic images and record numerical checks."
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    paths = []
    rng = np.random.default_rng(314)
    for i in range(3):
        path = root / f"fixture-{i}.png"
        Image.fromarray(rng.integers(0, 256, (96 + i * 8, 128, 3), dtype=np.uint8)).save(path)
        paths.append(path)
    started = time.perf_counter()
    report = {
        "started_at": now(),
        "media": "Synthetic images, real pretrained Inception feature extraction",
        "provider_calls": 0,
    }
    try:
        real, provenance = features(paths, allow_download=allow_download)
        repeated, _ = features(paths, allow_download=False)
        # Upstream reference extraction, determinism, and low-dimensional arithmetic parity are independent checks.
        from pytorch_fid.fid_score import calculate_frechet_distance

        a, b = real[:, :8], repeated[:, :8]
        upstream = float(
            calculate_frechet_distance(
                a.mean(0), np.cov(a, rowvar=False), b.mean(0), np.cov(b, rowvar=False)
            )
        )
        independent = frechet_from_features(a, b)
        full_distance = float(
            calculate_frechet_distance(
                real.mean(0),
                np.cov(real, rowvar=False),
                repeated.mean(0),
                np.cov(repeated, rowvar=False),
            )
        )
        if abs(full_distance) > 1e-3:
            raise ValueError("Full 2048D identical-set FID exceeded numerical tolerance")
        if not np.allclose(real, repeated, rtol=1e-6, atol=1e-6):
            raise ValueError("Nondeterministic serial feature extraction")
        if abs(upstream) > 1e-5 or abs(independent) > 1e-5:
            raise ValueError("Identical-feature distance is not approximately zero")
        report.update(
            status="success",
            features_shape=list(real.shape),
            finite=bool(np.isfinite(real).all()),
            full_feature_max_difference=float(np.abs(real - repeated).max()),
            upstream_distance_8d=upstream,
            independent_distance_8d=independent,
            upstream_distance_2048d=full_distance,
            provenance=provenance,
            limitation="Three synthetic samples test numerical behavior, not FID statistical reliability or model quality",
        )
    except Exception as exc:
        report.update(status="unavailable_or_failed", reason=f"{type(exc).__name__}: {exc}")
    report["elapsed_seconds"] = time.perf_counter() - started
    (root / "result.json").write_text(json.dumps(report, indent=2))
    return report
