"""Real, bounded-memory media inspection and timestamped video evidence."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps

from .contracts import file_hash
from .types import JsonObject, PathLike

VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
SAMPLER_VERSION = "pts-v1"


def probe(path: PathLike) -> JsonObject:
    "Inspect media dimensions, duration and orientation without inferring generation identity."
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"Media file missing: {p.name}")
    if p.suffix.lower() not in VIDEO_SUFFIXES:
        with Image.open(p) as im:
            im.load()
            original = im.size
            oriented = ImageOps.exif_transpose(im)
            return {
                "modality": "image",
                "width": original[0],
                "height": original[1],
                "display_width": oriented.width,
                "display_height": oriented.height,
                "mode": im.mode,
                "orientation": im.getexif().get(274),
                "audio": None,
                "duration": None,
                "frame_rate": None,
                "timebase": None,
            }
    import av

    with av.open(str(p)) as container:
        if not container.streams.video:
            raise ValueError("No video stream")
        stream = container.streams.video[0]
        info = {
            "modality": "video",
            "width": stream.width,
            "height": stream.height,
            "duration": float(stream.duration * stream.time_base)
            if stream.duration
            else (float(container.duration / av.time_base) if container.duration else None),
            "frame_rate": str(stream.average_rate) if stream.average_rate else None,
            "timebase": str(stream.time_base),
            "audio": bool(container.streams.audio),
            "rotation": 0,
            "codec": stream.codec_context.name,
        }
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(p)],
            capture_output=True,
            check=True,
            timeout=30,
        )
        video = next(s for s in json.loads(result.stdout)["streams"] if s["codec_type"] == "video")
        info["rotation"] = int(
            next(
                (s["rotation"] for s in video.get("side_data_list", []) if "rotation" in s),
                video.get("tags", {}).get("rotate", 0),
            )
        )
    except FileNotFoundError:
        info["rotation"] = None
    return info


def decoded(path: PathLike) -> Iterator[tuple[int, float, Any]]:
    """Decode in presentation order. Missing/nonmonotone PTS is an explicit error."""
    import av

    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        previous = None
        for index, frame in enumerate(container.decode(stream)):
            if frame.pts is None:
                raise ValueError("Decoded frame has no presentation timestamp")
            ts = float(frame.pts * frame.time_base)
            if previous is not None and ts < previous:
                raise ValueError("Nonmonotone presentation timestamps")
            # Equal timestamps are retained in inspection; sampling selects unique observations.
            previous = ts
            yield index, ts, frame


def frame_image(frame: Any, rotation: float = 0, max_side: int = 768) -> Image.Image:
    "Orient and resize a decoded frame into RGB evidence."
    im = frame.to_image().convert("RGB")
    if rotation is None:
        raise ValueError("Rotation metadata unavailable; install ffprobe")
    if rotation:
        im = im.rotate(rotation, expand=True)
    im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return im


def sample_video(
    path: PathLike,
    count: int = 8,
    policy: str = "uniform",
    offset: float = 0.0,
    window_seconds: float | None = None,
    max_side: int = 768,
) -> tuple[list[Image.Image], JsonObject]:
    "Sample real decoded timestamps using the declared full-clip or window policy."
    if not 1 <= count <= 256 or not 16 <= max_side <= 2048 or offset < 0:
        raise ValueError("Invalid frame count, offset or resolution budget")
    if policy not in {"uniform", "window"}:
        raise ValueError("Sampling policy must be uniform or window")
    if window_seconds is not None and not 0 < window_seconds < float("inf"):
        raise ValueError("Window duration must be positive and finite")
    metadata = probe(path)
    stamps, indices, duplicates = [], [], 0
    for index, ts, _ in decoded(path):
        if len(stamps) >= 1_000_000:
            raise ValueError("Video exceeds one million decoded frame metadata entries")
        if stamps and ts == stamps[-1]:
            duplicates += 1
            continue
        stamps.append(ts)
        indices.append(index)
    if not stamps:
        raise ValueError("No decoded frames")
    start = stamps[0] + offset
    end = stamps[-1] if window_seconds is None else min(stamps[-1], start + window_seconds)
    eligible = [i for i, ts in enumerate(stamps) if start <= ts <= end]
    if not eligible:
        raise ValueError("Sampling window contains no frames")
    if policy == "window":
        chosen = eligible[:count]  # Consecutive source observations, no cadence substitution.
    else:
        targets = np.linspace(stamps[eligible[0]], stamps[eligible[-1]], min(count, len(eligible)))
        times = np.array(stamps)
        chosen = sorted(set(min(eligible, key=lambda i: (abs(times[i] - t), i)) for t in targets))
    selected = {indices[i] for i in chosen}
    frames, timestamps = [], []
    for index, ts, frame in decoded(path):
        if index in selected:
            frames.append(frame_image(frame, metadata["rotation"], max_side))
            timestamps.append(ts)
        if len(frames) == len(selected):
            break
    provenance = {
        "version": SAMPLER_VERSION,
        "source_sha256": file_hash(path),
        "policy": policy,
        "offset_seconds": offset,
        "window_seconds": window_seconds,
        "requested_frames": count,
        "decoded_frames": len(stamps) + duplicates,
        "duplicate_timestamps": duplicates,
        "timestamps": timestamps,
        "source_first_pts": stamps[0],
        "source_last_pts": stamps[-1],
        "source_duration": metadata["duration"],
        "max_side": max_side,
        "rotation": metadata["rotation"],
        "transform": "RGB, orientation, aspect-preserving thumbnail; no crop",
        "dimensions": [list(f.size) for f in frames],
    }
    return frames, provenance


def adjacent_stability(
    path: PathLike,
    max_pairs: int = 4096,
    max_side: int = 256,
    offset: float = 0.0,
    window_seconds: float | None = None,
) -> tuple[float | None, JsonObject]:
    """Custom full-clip adjacent-frame MAE; a static clip scores one by definition."""
    if offset < 0 or (window_seconds is not None and window_seconds <= 0):
        raise ValueError("Temporal offset must be nonnegative and window positive")
    metadata = probe(path)
    source_start = None
    previous, first, last = None, None, None
    differences, deltas = [], []
    for _, ts, frame in decoded(path):
        source_start = ts if source_start is None else source_start
        if ts < source_start + offset:
            continue
        if window_seconds is not None and ts > source_start + offset + window_seconds:
            break
        current = np.asarray(frame_image(frame, metadata["rotation"], max_side), dtype=np.float32)
        if previous is not None:
            if ts == last:
                continue
            if current.shape != previous.shape:
                raise ValueError("Changing decoded frame dimensions")
            if len(differences) >= max_pairs:
                raise ValueError("Temporal budget exceeded; choose an explicit contiguous window")
            differences.append(float(np.abs(current - previous).mean() / 255))
            deltas.append(ts - last)
        first = ts if first is None else first
        previous, last = current, ts
    details = {
        "pairs": len(differences),
        "first_pts": first,
        "last_pts": last,
        "cadence_seconds": deltas,
        "per_pair_mae": differences,
        "max_side": max_side,
        "transform": "RGB, orientation, aspect-preserving thumbnail",
        "version": SAMPLER_VERSION,
        "offset_seconds": offset,
        "window_seconds": window_seconds,
    }
    return (1 - float(np.mean(differences)) if differences else None), details


def image_evidence(path: PathLike, max_side: int = 768) -> Image.Image:
    "Load an oriented RGB image and bound its longest side."
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        return im.copy()
