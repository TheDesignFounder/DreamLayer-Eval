"""Common evaluator descriptors and explicit result semantics."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import math
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

from . import __version__, media
from .composition import detect, evaluate_criteria, interpret
from .contracts import digest, file_hash, membership, record
from .types import JsonObject, PathLike


def descriptor(
    id: str,
    scope: str,
    direction: str,
    domain: Sequence[float | None],
    dependencies: Sequence[str],
    limitations: str,
    reference: bool = False,
    criteria: Sequence[str] = (),
) -> JsonObject:
    "Describe evaluator version, scope, domain, dependencies and limitations."
    return {
        "id": id,
        "version": "1.0.0",
        "scope": scope,
        "direction": direction,
        "valid_domain": domain,
        "dependencies": dependencies,
        "reference_required": reference,
        "supported_criteria": list(criteria),
        "limitations": limitations,
    }


REGISTRY = {
    x["id"]: x
    for x in [
        descriptor(
            "pixel_luminance",
            "image",
            "descriptive",
            [0, 1],
            ["PIL"],
            "Mean sRGB channel intensity heuristic; not quality",
        ),
        descriptor(
            "clip_cosine",
            "image",
            "higher",
            [-1, 1],
            ["torch", "transformers"],
            "CLIP cosine similarity; not the published scaled CLIPScore; 77-token limit",
            criteria=["global_text_alignment"],
        ),
        descriptor(
            "object_criteria",
            "criterion",
            "higher",
            [0, 1],
            ["ultralytics"],
            "Closed-vocabulary detector criteria; requires researcher review; not full task success",
            criteria=["count", "presence"],
        ),
        descriptor(
            "vqascore",
            "image",
            "higher",
            [0, 1],
            ["t2v_metrics"],
            "Published VQAScore via pinned upstream implementation; model-dependent probabilistic alignment",
            criteria=["compositional_text_alignment"],
        ),
        descriptor(
            "adjacent_pixel_stability",
            "video",
            "higher",
            [0, 1],
            ["av"],
            "Custom adjacent-frame MAE stability; frozen clips score well; not VBench or motion quality",
        ),
        descriptor(
            "aligned_psnr",
            "video",
            "higher",
            [0, None],
            ["av"],
            "Only pixel-aligned videos with matching PTS/resolution; infinity encoded explicitly",
            reference=True,
        ),
        descriptor(
            "fid",
            "dataset",
            "lower",
            [0, None],
            ["torch", "pytorch_fid"],
            "Two explicit image distributions; biased and unstable at small sample counts",
            reference=True,
        ),
        descriptor(
            "fvd",
            "dataset",
            "lower",
            [0, None],
            ["torch"],
            "Two video sets; requires explicit compatible I3D features and temporal preprocessing",
            reference=True,
        ),
    ]
}

REGISTRY["object_criteria"]["version"] = "1.2.0"
REGISTRY["adjacent_pixel_stability"]["version"] = "1.1.0"
REGISTRY["fid"]["version"] = "1.1.0"


def dependencies(metric_id: str) -> list[str]:
    "List required optional modules that cannot currently be imported."
    return [p for p in REGISTRY[metric_id]["dependencies"] if importlib.util.find_spec(p) is None]


def result(
    metric_id: str,
    assets: Sequence[JsonObject],
    experiment_id: str | None = None,
    config: JsonObject | None = None,
    **overrides: Any,
) -> JsonObject:
    "Construct a versioned evaluation record with explicit status and evidence identity."
    d = REGISTRY[metric_id]
    config = config or {}
    return record(
        "result",
        experiment_id,
        metric_id=metric_id,
        metric_version=d["version"],
        scope=d["scope"],
        membership_hash=membership(assets),
        asset_ids=[a["id"] for a in assets],
        reference_hash=None,
        implementation={"name": "dreamlayer-research", "version": __version__},
        weights=config.get("weights"),
        preprocessing_hash=digest(config),
        units="unitless",
        direction=d["direction"],
        elapsed_ms=0,
        **overrides,
    )


def evaluator_config(metric_id: str, config: JsonObject) -> JsonObject:
    "Expand settings with available weight and extractor fingerprints."
    config = dict(config)
    if config.get("weights") and Path(config["weights"]).is_file():
        config["weights_sha256"] = file_hash(config["weights"])
    if metric_id == "fid":
        from .fid import EXTRACTOR

        config["extractor"] = EXTRACTOR
        config["expected_weights_sha256"] = (
            "6726825d0af5f729cebd5821db510b11b1cfad8faad88a03f1befd49fb9129b2"
        )
    return config


def cache_key(
    metric_id: str,
    assets: Sequence[JsonObject],
    prompt: str,
    config: JsonObject,
    references: Sequence[JsonObject] = (),
) -> str:
    "Hash evaluator, media, prompt, preprocessing and reference identities."
    config = evaluator_config(metric_id, config)
    return digest(
        {
            "descriptor": REGISTRY[metric_id],
            "assets": membership(assets),
            "prompt": prompt,
            "config": config,
            "reference": membership(references) if references else None,
        }
    )


_models = {}


def clip_cosine(path: PathLike, prompt: str, config: JsonObject) -> tuple[float, JsonObject]:
    "Run pinned CLIP cosine inference and return tokenizer/model provenance."
    import torch
    from transformers import CLIPModel, CLIPProcessor

    model_id = config.get("model", "openai/clip-vit-large-patch14")
    revision = config.get("revision")
    if not revision:
        raise ValueError("CLIP requires a pinned model revision or local weights path")
    key = (model_id, revision, config.get("device", "cpu"))
    if key not in _models:
        model = (
            CLIPModel.from_pretrained(
                model_id,
                revision=revision,
                local_files_only=not config.get("allow_download", False),
            )
            .to(key[2])
            .eval()
        )
        processor = CLIPProcessor.from_pretrained(
            model_id, revision=revision, local_files_only=not config.get("allow_download", False)
        )
        _models[key] = (model, processor)
    model, processor = _models[key]
    tokens = processor.tokenizer(prompt, truncation=False)["input_ids"]
    inputs = processor(
        text=[prompt],
        images=[media.image_evidence(path, 2048)],
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=77,
    ).to(key[2])
    with torch.inference_mode():
        output = model(**inputs)
        score = torch.cosine_similarity(output.text_embeds, output.image_embeds, dim=1).item()
    return score, {
        "model": model_id,
        "revision": revision,
        "token_count": len(tokens),
        "token_limit": 77,
        "truncated": len(tokens) > 77,
        "transformers": importlib.metadata.version("transformers"),
    }


def vqascore(path: PathLike, prompt: str, config: JsonObject) -> tuple[float, JsonObject]:
    "Run explicitly provisioned upstream VQAScore and report its model identity."
    if not config.get("allow_download") and not config.get("weights_ready"):
        raise ImportError(
            "VQAScore weights not declared ready; install optional environment and explicitly provision weights"
        )
    import t2v_metrics

    model_id = config.get("model", "clip-flant5-xl")
    key = ("vqascore", model_id, config.get("device", "cpu"))
    if key not in _models:
        _models[key] = t2v_metrics.VQAScore(model=model_id, device=key[2])
    value = _models[key](images=[str(path)], texts=[prompt])
    return float(value[0, 0].item()), {
        "upstream": "https://github.com/linzhiqiu/t2v_metrics",
        "model": model_id,
        "package_version": importlib.metadata.version("t2v_metrics"),
        "adaptation": "none; upstream image/text scoring API",
    }


def aligned_psnr(
    path: PathLike, reference: PathLike, config: JsonObject
) -> tuple[float | None, JsonObject]:
    "Compute PSNR only after explicit timestamp and pixel-alignment checks."
    if config.get("alignment") != "exact_pts_pixels":
        raise ValueError("Explicit exact_pts_pixels alignment assertion required")
    a, ap = media.sample_video(path, count=config.get("frames", 32), max_side=2048)
    b, bp = media.sample_video(reference, count=config.get("frames", 32), max_side=2048)
    if (
        ap["timestamps"] != bp["timestamps"]
        or ap["decoded_frames"] != bp["decoded_frames"]
        or ap["dimensions"] != bp["dimensions"]
        or ap["source_duration"] != bp["source_duration"]
    ):
        raise ValueError("Reference timestamps, duration, frame count and dimensions must match")
    errors = [
        float(np.mean((np.asarray(x, dtype=np.float64) - np.asarray(y, dtype=np.float64)) ** 2))
        for x, y in zip(a, b)
    ]
    mse = float(np.mean(errors))
    return (10 * math.log10(255**2 / mse) if mse else None), {
        "generated_sampling": ap,
        "reference_sampling": bp,
        "mse": mse,
        "positive_infinity": mse == 0,
    }


def evaluate(
    metric_id: str,
    assets: Sequence[JsonObject],
    prompt: str = "",
    config: JsonObject | None = None,
    references: Sequence[JsonObject] = (),
    experiment_id: str | None = None,
) -> JsonObject:
    "Evaluate one declared metric and encode failures as explicit, nullable results."
    config = config or {}
    started = time.perf_counter()
    d = REGISTRY[metric_id]
    status, score, reason, details = "success", None, None, {}
    try:
        config = evaluator_config(metric_id, config)
        if not assets:
            status, reason = "insufficient_data", "No assets"
        elif d["reference_required"] and not references:
            status, reason = "not_applicable", "Explicit reference set required"
        elif d["scope"] == "dataset" and (len(assets) < 2 or len(references) < 2):
            status, reason = "insufficient_data", "At least two samples required in each set"
        elif metric_id not in {"fid", "fvd"} and len(assets) != 1:
            raise ValueError("Per-asset evaluators accept exactly one asset")
        elif any(
            a["media"]["modality"]
            != (
                "video"
                if metric_id in {"adjacent_pixel_stability", "aligned_psnr", "fvd"}
                else "image"
            )
            for a in assets
        ):
            status, reason = "not_applicable", "Asset modality outside evaluator scope"
        elif metric_id in {"clip_cosine", "vqascore"} and not prompt.strip():
            status, reason = "not_applicable", "Empty prompt"
        elif metric_id == "object_criteria" and not (
            config["criteria"] if "criteria" in config else interpret(prompt)["criteria"]
        ):
            status, reason = "not_applicable", "No supported object target"
        else:
            missing = dependencies(metric_id)
            if missing:
                raise ImportError("Missing optional dependencies: " + ", ".join(missing))
            for asset in [*assets, *references]:
                if file_hash(asset["locator"]) != asset["sha256"]:
                    raise ValueError("Asset content changed since import")
            path = assets[0]["locator"]
            modality = assets[0]["media"]["modality"]
            wanted = (
                "video"
                if metric_id in {"adjacent_pixel_stability", "aligned_psnr", "fvd"}
                else "image"
            )
            if modality != wanted:
                status, reason = "not_applicable", f"Requires {wanted} assets"
            elif metric_id == "pixel_luminance":
                score = float(
                    np.asarray(media.image_evidence(path, 2048), dtype=np.float64).mean() / 255
                )
            elif metric_id in {"clip_cosine", "vqascore"}:
                if not prompt.strip():
                    status, reason = "not_applicable", "Empty prompt"
                else:
                    score, details = (clip_cosine if metric_id == "clip_cosine" else vqascore)(
                        path, prompt, config
                    )
            elif metric_id == "object_criteria":
                parsed = (
                    config["criteria"] if "criteria" in config else interpret(prompt)["criteria"]
                )
                if not parsed:
                    status, reason = "not_applicable", "No supported object target"
                else:
                    detections, detector = detect(
                        path, config.get("weights"), config.get("threshold", 0.25)
                    )
                    classes = detector["classes"]
                    vocabulary = (
                        list(classes.values()) if isinstance(classes, dict) else list(classes)
                    )
                    details = evaluate_criteria(
                        parsed,
                        detections,
                        vocabulary=vocabulary,
                        exhaustive=config.get("exhaustive_objects", False),
                    )
                    status, score, reason = details["status"], details["score"], details["reason"]
                    details["detector"] = detector
            elif metric_id == "adjacent_pixel_stability":
                score, details = media.adjacent_stability(
                    path,
                    config.get("max_pairs", 4096),
                    config.get("max_side", 256),
                    config.get("offset_seconds", 0),
                    config.get("window_seconds"),
                )
                if score is None:
                    status, reason = (
                        "insufficient_data",
                        "At least two distinct decoded timestamps required",
                    )
            elif metric_id == "aligned_psnr":
                score, details = aligned_psnr(path, references[0]["locator"], config)
            elif metric_id == "fid":
                from .fid import calculate

                score, details = calculate(
                    [a["locator"] for a in assets],
                    [a["locator"] for a in references],
                    device=config.get("device", "cpu"),
                    allow_download=config.get("allow_download", False),
                )
            elif metric_id == "fvd":
                from .fvd import calculate

                score, details = calculate(assets, references, config)
        if score is not None and not math.isfinite(score):
            raise ValueError("Evaluator returned a nonfinite score")
    except (ImportError, ModuleNotFoundError) as exc:
        status, score, reason = "unavailable_dependency", None, str(exc)
    except Exception as exc:
        status, score, reason = "failed_evaluation", None, str(exc)
    output = result(
        metric_id,
        assets,
        experiment_id,
        config,
        status=status,
        score=score,
        reason=reason,
        details=details,
        special_value="positive_infinity" if details.get("positive_infinity") else None,
    )
    output["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
    output["reference_hash"] = membership(references) if references else None
    return output
