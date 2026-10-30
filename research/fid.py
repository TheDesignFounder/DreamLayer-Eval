"""Distribution-level FID with explicit membership and upstream feature extraction."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .contracts import canonical, digest, file_hash, membership
from .types import JsonObject, PathLike

EXTRACTOR = {
    "implementation": "pytorch-fid",
    "version": "0.3.0",
    "dimension": 2048,
    "weights": "pt_inception-2015-12-05-6726825d.pth",
    "preprocessing": "upstream ImagePathDataset RGB/ToTensor [0,1]; InceptionV3 resize 299 bilinear and normalize to [-1,1]",
}


def validate_features(features: np.ndarray) -> np.ndarray:
    "Require a finite two-dimensional feature matrix with at least two observations."
    a = np.asarray(features, dtype=np.float64)
    if a.ndim != 2 or a.shape[0] < 2 or a.shape[1] < 1:
        raise ValueError("At least two samples with compatible feature vectors are required")
    if not np.isfinite(a).all():
        raise ValueError("Nonfinite features")
    return a


def frechet_from_features(real: np.ndarray, generated: np.ndarray) -> float:
    "Compute Fréchet distance from compatible features without singleton fallback."
    real, generated = validate_features(real), validate_features(generated)
    if real.shape[1] != generated.shape[1]:
        raise ValueError("Incompatible feature dimensions")
    # Bures covariance trace via symmetric PSD eigendecomposition, float64.
    a, b = np.atleast_2d(np.cov(real, rowvar=False)), np.atleast_2d(np.cov(generated, rowvar=False))
    vals, vecs = np.linalg.eigh(a)
    root = (vecs * np.sqrt(np.maximum(vals, 0))) @ vecs.T
    middle = root @ b @ root
    trace_root = np.sqrt(np.maximum(np.linalg.eigvalsh((middle + middle.T) / 2), 0)).sum()
    value = float(
        np.sum((real.mean(0) - generated.mean(0)) ** 2) + np.trace(a) + np.trace(b) - 2 * trace_root
    )
    if value < -1e-6:
        raise ValueError("Invalid negative Frechet distance")
    return max(value, 0.0)


def features(
    paths: Sequence[PathLike],
    device: str = "cpu",
    batch_size: int = 8,
    allow_download: bool = False,
) -> tuple[np.ndarray, JsonObject]:
    "Extract real Inception features with verified checkpoint and preprocessing provenance."
    if len(paths) < 2:
        raise ValueError("FID requires at least two distinct files in each set")
    member = membership(paths)
    import importlib.metadata

    import torch
    from PIL import Image
    from pytorch_fid.fid_score import get_activations
    from pytorch_fid.inception import InceptionV3

    if importlib.metadata.version("pytorch-fid") != EXTRACTOR["version"]:
        raise ImportError("This evaluator version requires pytorch-fid==0.3.0")
    weights = Path(torch.hub.get_dir()) / "checkpoints" / EXTRACTOR["weights"]
    if not weights.exists() and not allow_download:
        raise ImportError(
            "FID weights unavailable; use explicit --allow-download in the ML smoke command"
        )
    model = InceptionV3([InceptionV3.BLOCK_INDEX_BY_DIM[2048]]).to(device).eval()
    if file_hash(weights) != "6726825d0af5f729cebd5821db510b11b1cfad8faad88a03f1befd49fb9129b2":
        raise ValueError("Unexpected Inception checkpoint bytes")
    sizes = set()
    for path in paths:
        with Image.open(path) as im:
            sizes.add(im.size)
    # Upstream DataLoader stacks before Inception's resize; heterogeneous sizes need batches of one.
    effective_batch = 1 if len(sizes) > 1 else min(batch_size, len(paths))
    provenance = {
        **EXTRACTOR,
        "membership_hash": member,
        "count": len(paths),
        "weights_sha256": file_hash(weights),
        "device": device,
    }
    with torch.inference_mode():
        activations = get_activations(
            [str(p) for p in paths], model, effective_batch, 2048, device, num_workers=0
        )
    return validate_features(activations), provenance


def write_cache(path: PathLike, values: np.ndarray, provenance: JsonObject) -> None:
    "Persist validated features and their explicit dataset/extractor identity."
    values = validate_features(values)
    if provenance.get("count") != len(values) or not provenance.get("weights_sha256"):
        raise ValueError("Invalid cache provenance")
    np.savez_compressed(
        path,
        features=values,
        provenance=canonical(provenance),
        payload_hash=digest(values.tolist()),
    )


def read_cache(path: PathLike, expected: JsonObject) -> np.ndarray:
    "Load cached features only when the complete expected provenance matches."
    with np.load(path, allow_pickle=False) as data:
        if not {"features", "provenance", "payload_hash"}.issubset(data.files):
            raise ValueError("Legacy/unknown cache cannot be used as validated FID features")
        provenance = json.loads(str(data["provenance"]))
        if provenance != expected:
            raise ValueError("Incompatible FID cache provenance")
        values = validate_features(data["features"])
        if digest(values.tolist()) != str(data["payload_hash"]):
            raise ValueError("Corrupt FID cache")
        return values


def calculate(
    generated: Sequence[PathLike], reference: Sequence[PathLike], **kwargs: Any
) -> tuple[float, JsonObject]:
    "Compare two image distributions using the same Inception extractor."
    if len(generated) < 2 or len(reference) < 2:
        raise ValueError(
            "FID requires two explicit image sets with at least two distinct samples each"
        )
    gen, gp = features(generated, **kwargs)
    ref, rp = features(reference, **kwargs)
    if {k: v for k, v in gp.items() if k not in {"membership_hash", "count"}} != {
        k: v for k, v in rp.items() if k not in {"membership_hash", "count"}
    }:
        raise ValueError("Incompatible feature provenance")
    from pytorch_fid.fid_score import calculate_frechet_distance

    # Use upstream definition for the standard score; independent PSD implementation is regression-tested.
    score = float(
        calculate_frechet_distance(
            gen.mean(0), np.cov(gen, rowvar=False), ref.mean(0), np.cov(ref, rowvar=False)
        )
    )
    if not math.isfinite(score) or score < -1e-3:
        raise ValueError("Nonfinite or materially negative upstream FID")
    return max(0.0, score), {
        "generated": gp,
        "reference": rp,
        "limitation": "Finite sample FID is biased; small samples do not establish stable quality estimates",
    }
