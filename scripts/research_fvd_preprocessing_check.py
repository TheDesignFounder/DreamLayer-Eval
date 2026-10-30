"""Regenerate I3D preprocessing parity evidence without loading any model weights."""

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.fvd import _preprocess_single


def generate(extended=False):
    import torch

    source = (
        Path(__file__).resolve().parents[1]
        / "dream_layer_backend/dream_layer_backend_utils/fvd/fvd.py"
    )
    spec = importlib.util.spec_from_file_location("legacy_fvd_preprocessing_reference", source)
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)
    shapes = [(3, 4, 32, 48), (3, 4, 48, 32), (3, 4, 32, 32)]
    if extended:
        shapes += [(3, 1, 17, 29), (3, 7, 257, 129)]
    checks = []
    for shape in shapes:
        video = torch.linspace(0, 1, math.prod(shape), dtype=torch.float32).reshape(shape)
        actual, expected = _preprocess_single(video), legacy.preprocess_single(video)
        assert torch.equal(actual, expected), f"Preprocessing differs on shape {shape}"
        checks.append(
            {
                "input_shape": list(shape),
                "output_shape": list(actual.shape),
                "max_difference": float((actual - expected).abs().max()),
            }
        )
    return {
        "status": "passed",
        "checks": checks,
        "scope": "Tensor preprocessing parity only; no I3D model inference",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--extended", action="store_true", help="Also check odd sizes and one-frame input"
    )
    args = parser.parse_args()
    report = generate(args.extended)
    # Existing evidence must not be overwritten by a reproduction.
    with args.output.open("x") as output:
        output.write(json.dumps(report, indent=2))
    print(json.dumps({"status": "passed", "shapes": len(report["checks"])}))


if __name__ == "__main__":
    main()
