from __future__ import annotations
"""
Video Evaluation Metrics Calculator.

Provides FVD, Video SSIM, Video PSNR, and Video LPIPS metrics
for evaluating generated videos. Adapted from common_metrics_on_video_quality.

Input videos are loaded as tensors in [B, T, C, H, W] format with pixel values in [0, 1].
"""

import os
import math
import logging
from typing import Dict, List, Optional, Any

import cv2
import numpy as np
try:
    import torch
except ImportError:
    torch = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Video loading
# ---------------------------------------------------------------------------

def load_video_as_tensor(video_path, max_frames=None):
    from research.media import sample_video
    if torch is None:
        raise ImportError('PyTorch required for tensor metrics')
    frames, _ = sample_video(video_path, count=max_frames or 32, max_side=768)
    return torch.from_numpy(np.stack([np.asarray(f) for f in frames]).copy()).permute(0,3,1,2).float().unsqueeze(0)/255


# ---------------------------------------------------------------------------
# SSIM (per-frame, no ML model needed)
# ---------------------------------------------------------------------------

def _ssim_single(img1: np.ndarray, img2: np.ndarray) -> float:
    """Compute SSIM between two single-channel images (numpy, float64, [0,1])."""
    C1 = 0.01 ** 2
    C2 = 0.03 ** 2
    img1 = img1.astype(np.float64)
    img2 = img2.astype(np.float64)
    kernel = cv2.getGaussianKernel(11, 1.5)
    window = np.outer(kernel, kernel.transpose())
    mu1 = cv2.filter2D(img1, -1, window)[5:-5, 5:-5]
    mu2 = cv2.filter2D(img2, -1, window)[5:-5, 5:-5]
    mu1_sq = mu1 ** 2
    mu2_sq = mu2 ** 2
    mu1_mu2 = mu1 * mu2
    sigma1_sq = cv2.filter2D(img1 ** 2, -1, window)[5:-5, 5:-5] - mu1_sq
    sigma2_sq = cv2.filter2D(img2 ** 2, -1, window)[5:-5, 5:-5] - mu2_sq
    sigma12 = cv2.filter2D(img1 * img2, -1, window)[5:-5, 5:-5] - mu1_mu2
    ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / \
               ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))
    return float(ssim_map.mean())


def _ssim_frame(img1: np.ndarray, img2: np.ndarray) -> float:
    """Compute SSIM for a frame pair. Input shape: (C, H, W), values in [0, 1]."""
    if img1.ndim == 2:
        return _ssim_single(img1, img2)
    elif img1.ndim == 3:
        if img1.shape[0] == 3:
            return float(np.mean([_ssim_single(img1[i], img2[i]) for i in range(3)]))
        elif img1.shape[0] == 1:
            return _ssim_single(np.squeeze(img1), np.squeeze(img2))
    raise ValueError(f"Unexpected image dimensions: {img1.shape}")


def compute_video_ssim(videos1: torch.Tensor, videos2: torch.Tensor,
                       per_frame: bool = False) -> Dict[str, Any]:
    """Compute SSIM between two video tensors.

    Args:
        videos1, videos2: tensors of shape [B, T, C, H, W] in [0, 1]
        per_frame: if True, return per-frame scores

    Returns:
        dict with video_ssim_mean, video_ssim_std, and optionally video_ssim_per_frame
    """
    assert videos1.shape == videos2.shape, "Video shapes must match"

    all_frame_scores = []
    for b in range(videos1.shape[0]):
        for t in range(videos1.shape[1]):
            img1 = videos1[b, t].numpy()
            img2 = videos2[b, t].numpy()
            all_frame_scores.append(_ssim_frame(img1, img2))

    num_frames = videos1.shape[1]
    per_frame_means = []
    if per_frame:
        for t in range(num_frames):
            frame_scores = [all_frame_scores[b * num_frames + t]
                            for b in range(videos1.shape[0])]
            per_frame_means.append(float(np.mean(frame_scores)))

    result = {
        "video_ssim_mean": float(np.mean(all_frame_scores)),
        "video_ssim_std": float(np.std(all_frame_scores)),
    }
    if per_frame:
        result["video_ssim_per_frame"] = per_frame_means
    return result


# ---------------------------------------------------------------------------
# PSNR (per-frame, no ML model needed)
# ---------------------------------------------------------------------------

def _psnr_frame(img1: np.ndarray, img2: np.ndarray) -> float:
    """Compute PSNR for a frame pair. Input: (C, H, W), values in [0, 1]."""
    mse = np.mean((img1.astype(np.float64) - img2.astype(np.float64)) ** 2)
    if mse == 0:
        return float("inf")
    return float(20 * math.log10(1.0 / math.sqrt(mse)))


def compute_video_psnr(videos1, videos2, per_frame=False):
    if videos1.shape != videos2.shape or videos1.shape[1] < 1:
        raise ValueError('Aligned nonempty video tensors with identical shapes required')
    a=videos1.detach().cpu().numpy().astype(np.float64)
    b=videos2.detach().cpu().numpy().astype(np.float64)
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Nonfinite video tensor')
    errors=np.mean((a-b)**2,axis=(0,2,3,4))
    mse=float(np.mean(errors))
    result={'video_psnr_mean':10*math.log10(1/mse) if mse else None,
            'video_psnr_std':None,'psnr_special_value':'positive_infinity' if mse==0 else None,
            'definition':'PSNR from pooled pixel MSE; infinity encoded explicitly'}
    if per_frame:
        result['video_psnr_per_frame']=[10*math.log10(1/e) if e else None for e in errors]
        result['video_psnr_per_frame_special']=['positive_infinity' if e==0 else None for e in errors]
    return result


# ---------------------------------------------------------------------------
# LPIPS (per-frame, requires pretrained network)
# ---------------------------------------------------------------------------

def compute_video_lpips(videos1: torch.Tensor, videos2: torch.Tensor,
                        device: torch.device, per_frame: bool = False) -> Dict[str, Any]:
    """Compute LPIPS between two video tensors.

    Args:
        videos1, videos2: tensors of shape [B, T, C, H, W] in [0, 1]
        device: torch device
        per_frame: if True, return per-frame scores

    Returns:
        dict with video_lpips_mean, video_lpips_std, and optionally video_lpips_per_frame
    """
    import lpips as lpips_lib
    import warnings
    warnings.filterwarnings("ignore")

    assert videos1.shape == videos2.shape, "Video shapes must match"

    loss_fn = lpips_lib.LPIPS(net='alex', spatial=True).to(device)

    # Handle grayscale
    if videos1.shape[2] == 1:
        videos1 = videos1.repeat(1, 1, 3, 1, 1)
        videos2 = videos2.repeat(1, 1, 3, 1, 1)

    # [0, 1] -> [-1, 1] for LPIPS
    videos1 = videos1 * 2 - 1
    videos2 = videos2 * 2 - 1

    all_frame_scores = []
    with torch.no_grad():
        for b in range(videos1.shape[0]):
            for t in range(videos1.shape[1]):
                img1 = videos1[b, t].unsqueeze(0).to(device)
                img2 = videos2[b, t].unsqueeze(0).to(device)
                score = loss_fn.forward(img1, img2).mean().detach().cpu().item()
                all_frame_scores.append(score)

    num_frames = videos1.shape[1]
    per_frame_means = []
    if per_frame:
        for t in range(num_frames):
            frame_scores = [all_frame_scores[b * num_frames + t]
                            for b in range(videos1.shape[0])]
            per_frame_means.append(float(np.mean(frame_scores)))

    result = {
        "video_lpips_mean": float(np.mean(all_frame_scores)),
        "video_lpips_std": float(np.std(all_frame_scores)),
    }
    if per_frame:
        result["video_lpips_per_frame"] = per_frame_means
    return result


# ---------------------------------------------------------------------------
# FVD (distribution metric, requires I3D model)
# ---------------------------------------------------------------------------

def compute_fvd(videos1: torch.Tensor, videos2: torch.Tensor,
                device: torch.device) -> Dict[str, float]:
    """Compute Frechet Video Distance between two sets of videos.

    Args:
        videos1, videos2: tensors of shape [B, T, C, H, W] in [0, 1]
                         B >= 2 for meaningful covariance, T >= 10 for I3D
        device: torch device

    Returns:
        dict with fvd_score
    """
    from .fvd.fvd import load_i3d_pretrained, get_fvd_feats, frechet_distance

    assert videos1.shape == videos2.shape, "Video shapes must match"
    assert videos1.shape[1] >= 10, "FVD requires at least 10 frames per video"

    # Handle grayscale
    if videos1.shape[2] == 1:
        videos1 = videos1.repeat(1, 1, 3, 1, 1)
        videos2 = videos2.repeat(1, 1, 3, 1, 1)

    # BTCHW -> BCTHW for I3D
    v1 = videos1.permute(0, 2, 1, 3, 4)
    v2 = videos2.permute(0, 2, 1, 3, 4)

    i3d = load_i3d_pretrained(device=device)
    feats1 = get_fvd_feats(v1, i3d=i3d, device=device)
    feats2 = get_fvd_feats(v2, i3d=i3d, device=device)
    fvd_score = frechet_distance(feats1, feats2)

    return {"fvd_score": fvd_score}


# ---------------------------------------------------------------------------
# VideoMetricsCalculator (singleton pattern)
# ---------------------------------------------------------------------------

class VideoMetricsCalculator:
    """Calculator for video evaluation metrics."""

    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu') if torch else None

    def compute_all(self, video_path, reference_path=None, per_frame=True, alignment=None):
        from research.media import sample_video
        from research.metrics import aligned_psnr
        from .video_quality_metrics import compute_all_quality_metrics
        metrics = compute_all_quality_metrics(video_path, self.device)
        metrics['_errors'] = metrics.pop('_quality_errors', [])
        metrics['fvd_score'] = None
        metrics['fvd_status'] = 'not_applicable'
        metrics['fvd_reason'] = 'FVD requires two explicit video sets; use Research workbench'
        if reference_path:
            if alignment != 'exact_pts_pixels':
                metrics['reference_status'] = 'not_applicable'
                metrics['_errors'].append('Pixel-based references require explicit exact_pts_pixels alignment')
            else:
                try:
                    score, details = aligned_psnr(video_path, reference_path, {'alignment': alignment, 'frames': 32})
                    metrics.update(video_psnr_mean=score, psnr_special_value='positive_infinity' if details['positive_infinity'] else None,
                                   reference_provenance=details, reference_status='success')
                    a = load_video_as_tensor(video_path, 32)
                    b = load_video_as_tensor(reference_path, 32)
                    metrics.update(compute_video_ssim(a,b,per_frame=per_frame))
                    try:
                        metrics.update(compute_video_lpips(a,b,self.device,per_frame=per_frame))
                    except Exception as exc:
                        metrics['lpips_status'] = 'unavailable_dependency'
                        metrics['_errors'].append(str(exc))
                except Exception as exc:
                    metrics['reference_status'] = 'failed_evaluation'
                    metrics['_errors'].append(str(exc))
        return metrics


# Singleton
_calculator = None


def get_video_calculator() -> VideoMetricsCalculator:
    """Get or create the singleton VideoMetricsCalculator."""
    global _calculator
    if _calculator is None:
        _calculator = VideoMetricsCalculator()
    return _calculator
