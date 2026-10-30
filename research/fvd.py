"""Explicit I3D feature Fréchet distance; no synthetic or singleton fallback."""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from .contracts import file_hash, membership
from .fid import frechet_from_features
from .media import sample_video
from .types import JsonObject


def _preprocess_single(video, resolution=224):
    """Preserve the legacy I3D resize/crop contract without importing the application.

    Adapted from the bundled fvd-comparison preprocessing. Input is C,T,H,W in
    [0,1]; bilinear resize of the shorter side, center crop, then scale to [-1,1].
    """
    from torch.nn import functional as functional

    _, _, height, width = video.shape
    scale = resolution / min(height, width)
    target = (
        (resolution, math.ceil(width * scale))
        if height < width
        else (math.ceil(height * scale), resolution)
    )
    video = functional.interpolate(video, size=target, mode="bilinear", align_corners=False)
    _, _, height, width = video.shape
    top, left = (height - resolution) // 2, (width - resolution) // 2
    return ((video[:, :, top : top + resolution, left : left + resolution] - 0.5) * 2).contiguous()


def calculate(
    generated: Sequence[JsonObject], reference: Sequence[JsonObject], config: JsonObject
) -> tuple[float, JsonObject]:
    "Compare video sets using explicitly supplied compatible I3D TorchScript weights."
    if len(generated) < 2 or len(reference) < 2:
        raise ValueError("FVD requires at least two distinct videos per set")
    weights = config.get("weights")
    if not weights or not Path(weights).is_file():
        raise ImportError("Explicit local I3D TorchScript weights required")
    if not config.get("weights_sha256") or file_hash(weights) != config["weights_sha256"]:
        raise ValueError("I3D weights hash must match the frozen configuration")
    import torch

    device = config.get("device", "cpu")
    model = torch.jit.load(weights, map_location=device).eval()
    all_features, provenance = [], []
    for assets in (generated, reference):
        membership(assets)
        feats, samples = [], []
        for asset in assets:
            frames, sampling = sample_video(
                asset["locator"], count=config.get("frames", 16), max_side=512
            )
            if len(frames) != config.get("frames", 16):
                raise ValueError("Video too short for the configured temporal sampling")
            array = np.stack([np.asarray(f) for f in frames])
            tensor = torch.from_numpy(array.copy()).permute(3, 0, 1, 2).float() / 255
            tensor = _preprocess_single(tensor).unsqueeze(0).to(device)
            with torch.inference_mode():
                feature = (
                    model(tensor, rescale=False, resize=False, return_features=True)
                    .detach()
                    .cpu()
                    .numpy()
                    .reshape(-1)
                )
            feats.append(feature)
            samples.append(sampling)
        all_features.append(np.stack(feats))
        provenance.append(
            {"membership_hash": membership(assets), "count": len(assets), "sampling": samples}
        )
    return frechet_from_features(*all_features), {
        "implementation": "dreamlayer-i3d-frechet-v1",
        "weights_sha256": file_hash(weights),
        "feature_dimension": all_features[0].shape[1],
        "sets": provenance,
        "limitation": "Explicit I3D variant; upstream benchmark parity not asserted; content bias and small-sample instability remain",
    }
