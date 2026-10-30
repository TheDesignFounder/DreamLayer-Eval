from __future__ import annotations
"""
Video Quality Metrics (No-Reference).

Single-video evaluation metrics that don't require a reference video.
Custom stability heuristics; these are not standard VBench metrics.

Metrics:
    - Temporal Flickering: frame-to-frame stability (pure math, no model)
    - Subject Consistency: DINO feature similarity across frames
    - Background Consistency: DINO feature similarity across frames
    - Motion Smoothness: optical flow smoothness (OpenCV, no model)
    - Aesthetic Quality: per-frame LAION aesthetic score (reuses existing model)
"""

import os
import logging
from typing import Dict, List, Optional, Any

import cv2
import numpy as np
try:
    import torch
    import torch.nn.functional as F
except ImportError:
    torch = F = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Video frame extraction
# ---------------------------------------------------------------------------

def extract_frames(video_path, max_frames=None):
    from research.media import sample_video
    frames, _ = sample_video(video_path, count=max_frames or 32, max_side=768)
    return [np.asarray(frame) for frame in frames]


# ---------------------------------------------------------------------------
# 1. Temporal Flickering (pure math)
# ---------------------------------------------------------------------------

def compute_temporal_flickering(video_path, max_frames=None):
    from research.media import adjacent_stability
    score, provenance = adjacent_stability(video_path, max_pairs=max_frames or 4096)
    return {'adjacent_pixel_stability': score, 'per_frame_flicker': provenance['per_pair_mae'],
            'temporal_provenance': provenance, 'temporal_status': 'success' if score is not None else 'insufficient_data'}


# ---------------------------------------------------------------------------
# 2 & 3. Subject & Background Consistency (DINO ViT)
# ---------------------------------------------------------------------------

_dino_model = None


def _get_dino_model(device: torch.device):
    """Lazy-load DINO ViT-B/16 model."""
    global _dino_model
    if _dino_model is None:
        logger.info("Loading DINO ViT-B/16 model...")
        _dino_model = torch.jit.load(os.environ['DREAMLAYER_DINO_WEIGHTS'], map_location=device)
        _dino_model = _dino_model.to(device)
        _dino_model.eval()
        logger.info("DINO model loaded successfully")
    return _dino_model


def _dino_preprocess(frame: np.ndarray, size: int = 224) -> torch.Tensor:
    """Preprocess a frame for DINO: resize, normalize, to tensor."""
    from torchvision import transforms
    transform = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((size, size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225]),
    ])
    return transform(frame)


def _compute_dino_features(frames: List[np.ndarray], model, device: torch.device,
                           batch_size: int = 8) -> torch.Tensor:
    """Extract DINO features for a list of frames.

    Returns:
        Tensor of shape (N, feature_dim) with L2-normalized features
    """
    all_features = []

    for i in range(0, len(frames), batch_size):
        batch_frames = frames[i:i + batch_size]
        batch_tensors = torch.stack([_dino_preprocess(f) for f in batch_frames]).to(device)

        with torch.no_grad():
            features = model(batch_tensors)

        features = F.normalize(features, dim=-1, p=2)
        all_features.append(features.cpu())

    return torch.cat(all_features, dim=0)


def compute_subject_consistency(video_path: str, device: torch.device,
                                max_frames: Optional[int] = None) -> Dict[str, Any]:
    """Compute subject consistency using DINO features.

    Measures how consistent the main subject is across frames by computing
    cosine similarity of DINO features between consecutive frames and the first frame.

    Returns:
        dict with subject_consistency_score (0-1, higher is better)
        and per_frame_subject_sim (list)
    """
    frames = extract_frames(video_path, max_frames)

    if len(frames) < 2:
        return {"whole_frame_anchored_dino_cosine": None, "per_frame_subject_sim": []}

    model = _get_dino_model(device)
    features = _compute_dino_features(frames, model, device)

    per_frame_sim = []
    for i in range(1, len(features)):
        sim_to_prev = F.cosine_similarity(features[i:i+1], features[i-1:i]).item()
        sim_to_first = F.cosine_similarity(features[i:i+1], features[0:1]).item()
        avg_sim = (sim_to_prev + sim_to_first) / 2.0
        per_frame_sim.append(avg_sim)

    score = float(np.mean(per_frame_sim))

    return {
        "whole_frame_anchored_dino_cosine": score,
        "per_frame_subject_sim": per_frame_sim,
    }


def compute_background_consistency(video_path: str, device: torch.device,
                                   max_frames: Optional[int] = None) -> Dict[str, Any]:
    """Compute background consistency using DINO features.

    Same approach as subject consistency but evaluates overall scene stability.
    Uses consecutive-frame similarity without first-frame anchoring
    to better capture background drift over time.

    Returns:
        dict with background_consistency_score (0-1, higher is better)
        and per_frame_bg_sim (list)
    """
    frames = extract_frames(video_path, max_frames)

    if len(frames) < 2:
        return {"whole_frame_adjacent_dino_cosine": None, "per_frame_bg_sim": []}

    model = _get_dino_model(device)
    features = _compute_dino_features(frames, model, device)

    per_frame_sim = []
    for i in range(1, len(features)):
        sim = F.cosine_similarity(features[i:i+1], features[i-1:i]).item()
        per_frame_sim.append(sim)

    score = float(np.mean(per_frame_sim))

    return {
        "whole_frame_adjacent_dino_cosine": score,
        "per_frame_bg_sim": per_frame_sim,
    }


# ---------------------------------------------------------------------------
# 4. Motion Smoothness (OpenCV optical flow)
# ---------------------------------------------------------------------------

def compute_motion_smoothness(video_path, max_frames=None):
    from research.media import decoded, frame_image, probe
    metadata = probe(video_path)
    previous = None
    magnitudes, times = [], []
    for _, ts, frame in decoded(video_path):
        current = cv2.cvtColor(np.asarray(frame_image(frame, metadata['rotation'], 256)), cv2.COLOR_RGB2GRAY)
        if times and ts == times[-1]:
            continue
        if len(times) >= (max_frames or 4096):
            raise ValueError('Temporal decoding budget exceeded; choose an explicit contiguous window')
        if previous is not None:
            flow = cv2.calcOpticalFlowFarneback(previous,current,None,.5,3,15,3,5,1.2,0)
            magnitudes.append(float(np.linalg.norm(flow,axis=2).mean()))
        previous = current
        times.append(ts)
    score = max(0., 1-float(np.abs(np.diff(magnitudes)).mean())/50) if len(magnitudes)>1 else None
    return {'flow_magnitude_stability': score, 'per_frame_motion': magnitudes,
            'flow_timestamps': times, 'flow_status': 'success' if score is not None else 'insufficient_data',
            'flow_definition': 'Custom changes of mean Farneback magnitude / 50px at max side 256; not motion quality'}


# ---------------------------------------------------------------------------
# 5. Per-Frame Aesthetic Quality (reuses existing LAION scorer)
# ---------------------------------------------------------------------------

def compute_video_aesthetic_quality(video_path: str,
                                   max_frames: Optional[int] = None) -> Dict[str, Any]:
    """Compute per-frame aesthetic quality using the existing LAION aesthetic predictor.

    Returns:
        dict with video_aesthetic_mean, video_aesthetic_min, video_aesthetic_std (1-10 scale)
        and per_frame_aesthetic (list)
    """
    import tempfile
    from PIL import Image

    frames = extract_frames(video_path, max_frames)

    try:
        from dream_layer_backend_utils.aesthetic_metrics import get_aesthetic_calculator
        calculator = get_aesthetic_calculator()
    except Exception as e:
        logger.error(f"Failed to load aesthetic calculator: {e}")
        return {
            "video_aesthetic_mean": None,
            "video_aesthetic_min": None,
            "video_aesthetic_std": None,
            "per_frame_aesthetic": [],
        }

    per_frame_scores = []
    # Sample frames to avoid excessive computation (every Nth frame)
    sample_step = max(1, len(frames) // 16)  # Cap at ~16 frames
    sampled_frames = frames[::sample_step]

    for frame in sampled_frames:
        try:
            # Save frame to temp file for the aesthetic calculator
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                Image.fromarray(frame).save(tmp.name)
                score = calculator.calculate_aesthetic_score(tmp.name)
                if score is not None:
                    per_frame_scores.append(score)
                os.unlink(tmp.name)
        except Exception as e:
            logger.warning(f"Aesthetic score failed for frame: {e}")
            continue

    if not per_frame_scores:
        return {
            "video_aesthetic_mean": None,
            "video_aesthetic_min": None,
            "video_aesthetic_std": None,
            "per_frame_aesthetic": [],
        }

    return {
        "video_aesthetic_mean": float(np.mean(per_frame_scores)),
        "video_aesthetic_min": float(np.min(per_frame_scores)),
        "video_aesthetic_std": float(np.std(per_frame_scores)),
        "per_frame_aesthetic": per_frame_scores,
    }


# ---------------------------------------------------------------------------
# Combined computation
# ---------------------------------------------------------------------------

def compute_all_quality_metrics(video_path, device=None, max_frames=None):
    metrics, errors = {}, []
    for function in (compute_temporal_flickering, compute_motion_smoothness):
        try:
            metrics.update(function(video_path, max_frames))
        except Exception as exc:
            errors.append(str(exc))
    metrics['_quality_errors'] = errors
    metrics['metric_version'] = 'custom-video-v2'
    metrics['limitations'] = 'Pixel/flow stability only; static video can score well. No subject/background isolation or audio-quality claim.'
    return metrics
