"""
FVD (Frechet Video Distance) computation using I3D features.
Adapted from https://github.com/universome/fvd-comparison
and common_metrics_on_video_quality.
"""

import os
import math
from typing import Tuple

import numpy as np
import torch
import torch.nn.functional as F
from scipy.linalg import sqrtm


def load_i3d_pretrained(device=torch.device('cpu'), filepath=None, weights_sha256=None):
    """Only explicitly provisioned, hash-verified I3D weights; no automatic download."""
    from research.contracts import file_hash
    if not filepath or not os.path.isfile(filepath):
        raise ImportError("Explicit local I3D weights required")
    if not weights_sha256 or file_hash(filepath) != weights_sha256:
        raise ValueError("Expected I3D weights checksum required")
    return torch.jit.load(filepath).eval().to(device)


def preprocess_single(video, resolution=224):
    """Preprocess a single video for I3D input.

    Args:
        video: tensor of shape (C, T, H, W) in [0, 1]
        resolution: target spatial resolution

    Returns:
        Preprocessed video tensor (C, T, resolution, resolution) in [-1, 1]
    """
    c, t, h, w = video.shape

    # Scale shorter side to resolution
    scale = resolution / min(h, w)
    if h < w:
        target_size = (resolution, math.ceil(w * scale))
    else:
        target_size = (math.ceil(h * scale), resolution)
    video = F.interpolate(video, size=target_size, mode='bilinear', align_corners=False)

    # Center crop
    c, t, h, w = video.shape
    w_start = (w - resolution) // 2
    h_start = (h - resolution) // 2
    video = video[:, :, h_start:h_start + resolution, w_start:w_start + resolution]

    # [0, 1] -> [-1, 1]
    video = (video - 0.5) * 2

    return video.contiguous()


def get_fvd_feats(videos, i3d, device, bs=10):
    """Extract I3D features from videos.

    Args:
        videos: tensor of shape (B, C, T, H, W) in [0, 1]
        i3d: pretrained I3D model
        device: torch device
        bs: batch size for feature extraction

    Returns:
        numpy array of shape (B, 400) with I3D features
    """
    detector_kwargs = dict(rescale=False, resize=False, return_features=True)
    feats = np.empty((0, 400))

    with torch.no_grad():
        for i in range((len(videos) - 1) // bs + 1):
            batch = torch.stack([
                preprocess_single(video)
                for video in videos[i * bs:(i + 1) * bs]
            ]).to(device)
            batch_feats = i3d(batch, **detector_kwargs).detach().cpu().numpy()
            feats = np.vstack([feats, batch_feats])

    return feats


def compute_stats(feats: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Compute mean and covariance of features."""
    mu = feats.mean(axis=0)
    sigma = np.cov(feats, rowvar=False)
    return mu, sigma


def frechet_distance(feats_fake, feats_real):
    from research.fid import frechet_from_features
    return frechet_from_features(feats_fake, feats_real)
