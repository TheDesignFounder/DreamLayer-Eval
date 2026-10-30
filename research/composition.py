"""Inspectable, conservative object criteria. This is not a full prompt parser."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from .contracts import digest, file_hash
from .types import JsonObject, PathLike

COCO = (
    "person,bicycle,car,motorcycle,airplane,bus,train,truck,boat,traffic light,fire hydrant,stop sign,parking meter,bench,bird,cat,dog,horse,sheep,cow,elephant,bear,zebra,giraffe,backpack,umbrella,handbag,tie,suitcase,frisbee,skis,snowboard,sports ball,kite,baseball bat,baseball glove,skateboard,surfboard,tennis racket,bottle,wine glass,cup,fork,knife,spoon,bowl,banana,apple,sandwich,orange,broccoli,carrot,hot dog,pizza,donut,cake,chair,couch,potted plant,bed,dining table,toilet,tv,laptop,mouse,remote,keyboard,cell phone,microwave,oven,toaster,sink,refrigerator,book,clock,vase,scissors,teddy bear,hair drier,toothbrush"
).split(",")
ALIASES = {
    "man": "person",
    "woman": "person",
    "people": "person",
    "men": "person",
    "women": "person",
    "doughnut": "donut",
    "doughnuts": "donut",
}
NUMBERS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def interpret(prompt: str) -> JsonObject:
    "Extract conservative object criteria for researcher review before execution."
    variants = {word: word for word in COCO}
    variants.update({word + "s": word for word in COCO if not word.endswith("s")})
    variants.update(ALIASES)
    pattern = (
        r"\b(" + "|".join(re.escape(v) for v in sorted(variants, key=len, reverse=True)) + r")\b"
    )
    criteria = []
    previous_end = 0
    adjectives = set(
        "red blue green yellow black white orange pink purple brown gray grey large small big tiny little tall short round square old young bright dark striped spotted wooden metal metallic shiny matte parked moving fluffy furry happy sleeping ripe fresh".split()
    )
    matches = list(re.finditer(pattern, prompt.lower()))
    for match_index, match in enumerate(matches):
        entity = variants[match[0]]
        if match[0] == "orange" and match_index + 1 < len(matches):
            between = re.findall(
                r"\w+", prompt[match.end() : matches[match_index + 1].start()].lower()
            )
            if all(word in adjectives for word in between):
                continue  # Color modifying the following recognized noun, not a fruit target.
        prefix = prompt[max(previous_end, match.start() - 100) : match.start()].lower()
        previous_end = match.end()
        # Restrict interpretation to this noun phrase; never borrow another object's count.
        prefix = re.split(r"[,;.!?]|\b(?:and|with|beside|behind|near|under|on|in)\b", prefix)[-1]
        words = re.findall(r"\w+", prefix)
        while words and words[-1] in adjectives:
            words.pop()
        reduced_prefix = " ".join(words) + " "
        tokens = words
        last = tokens[-1] if tokens else ""
        criterion = {
            "id": f"object-{len(criteria) + 1}",
            "kind": "presence",
            "entity": entity,
            "count_mode": "unspecified",
            "minimum": 1,
            "maximum": None,
            "source_span": [match.start(), match.end()],
            "source_text": match[0],
        }
        range_match = re.search(
            r"between (\w+) and (\w+)\s*(?:" + "|".join(adjectives) + r"|\s)*$",
            prompt[max(0, match.start() - 100) : match.start()].lower(),
        )

        def number(text):
            return int(text) if text.isdigit() else NUMBERS.get(text)

        if range_match and all(number(x) is not None for x in range_match.groups()):
            low, high = [number(x) for x in range_match.groups()]
            if low > high:
                criterion.update(kind="unsupported", reason="Reversed count range")
            else:
                criterion.update(kind="count", count_mode="range", minimum=low, maximum=high)
        elif last in {"no", "without", "zero"}:
            criterion.update(kind="count", count_mode="exact", minimum=0, maximum=0)
        elif last.isdigit() or last in NUMBERS:
            n = int(last) if last.isdigit() else NUMBERS[last]
            minimum = bool(re.search(r"(?:at least|minimum of)\s+\w+\s*$", reduced_prefix))
            if sum(t.isdigit() or t in NUMBERS for t in tokens) > 1 or re.search(
                r"\b(?:or|about|approximately|roughly|around|almost|nearly|more than|less than|at most|up to|over)\b",
                reduced_prefix,
            ):
                criterion.update(
                    kind="unsupported",
                    count_mode="unresolved",
                    minimum=None,
                    maximum=None,
                    reason="Unsupported count quantifier; review this criterion",
                )
            else:
                criterion.update(
                    kind="count",
                    count_mode="minimum" if minimum else "exact",
                    minimum=n,
                    maximum=None if minimum else n,
                )
        elif any(t.isdigit() or t in NUMBERS or t in {"no", "without"} for t in tokens):
            criterion.update(
                kind="unsupported",
                reason="Explicit count/negation has unresolved modifiers; review this criterion",
                count_mode="unresolved",
                minimum=None,
                maximum=None,
            )
        elif last in {"a", "an", "the"}:
            # Articles establish presence only after excluding unresolved counts.
            criterion["count_mode"] = "minimum"
        criteria.append(criterion)
    return {
        "version": "object-criteria-v4",
        "criteria": criteria,
        "prompt_hash": digest(prompt),
        "requires_review": True,
        "exhaustive_objects": False,
        "unsupported": ["attributes", "relations", "actions", "text", "reference_identity"],
        "reason": None
        if criteria
        else "No supported object target; researcher-defined criteria needed",
    }


def evaluate_criteria(
    criteria: Sequence[JsonObject],
    detections: Sequence[JsonObject] | None,
    vocabulary: Sequence[str] | Mapping[int, str] | None = None,
    exhaustive: bool = False,
) -> JsonObject:
    "Score supported counts against detections and the actual detector vocabulary."
    if detections is None:
        return {
            "status": "failed_evaluation",
            "score": None,
            "reason": "Detector failed; absence is unknown",
            "criteria": [],
        }
    if vocabulary is None:
        return {
            "status": "not_applicable",
            "score": None,
            "reason": "Detector vocabulary not supplied; coverage and absence are unknown",
            "coverage": None,
            "criteria": [
                {
                    **c,
                    "status": "not_applicable",
                    "label": "uncertain",
                    "reason": "Detector vocabulary not supplied",
                }
                for c in criteria
            ],
        }
    counts = Counter(d["class_name"] for d in detections)
    rows = []
    for criterion in criteria:
        row = dict(criterion)
        if (
            criterion.get("kind") not in {"presence", "count"}
            or criterion.get("entity") not in vocabulary
        ):
            row.update(
                status="not_applicable",
                label="uncertain",
                reason="Unsupported criterion or detector class",
            )
        else:
            count = counts[criterion["entity"]]
            low, high = criterion.get("minimum", 1), criterion.get("maximum")
            passed = count >= low and (high is None or count <= high)
            row.update(status="success", label="pass" if passed else "fail", detected=count)
        rows.append(row)
    if exhaustive:
        allowed = {c.get("entity") for c in criteria}
        for extra in sorted(set(counts) - allowed):
            rows.append(
                {
                    "id": f"forbidden-{extra}",
                    "kind": "count",
                    "entity": extra,
                    "status": "success",
                    "label": "fail",
                    "detected": counts[extra],
                    "maximum": 0,
                }
            )
    supported = [r for r in rows if r["status"] == "success"]
    return {
        "status": "success" if supported else "not_applicable",
        "score": sum(r["label"] == "pass" for r in supported) / len(supported)
        if supported
        else None,
        "reason": None if supported else "No supported criteria",
        "criteria": rows,
        "coverage": len(supported) / len(rows) if rows else None,
        "detected_objects": dict(counts),
    }


def detect(
    path: PathLike, weights: PathLike, threshold: float = 0.25, iou: float = 0.5
) -> tuple[list[JsonObject], JsonObject]:
    "Run an explicitly provisioned YOLO model and return detections with provenance."
    if not weights or not Path(weights).is_file():
        raise ImportError("Explicit local YOLO weights required; no implicit download")
    from ultralytics import YOLO

    model = YOLO(weights)
    results = model(str(path), conf=threshold, iou=iou, verbose=False)
    detections = [
        {
            "class_name": model.names[int(b.cls[0])],
            "confidence": float(b.conf[0]),
            "bbox": b.xyxy[0].tolist(),
        }
        for b in results[0].boxes
    ]
    return detections, {
        "weights_sha256": file_hash(weights),
        "classes": model.names,
        "confidence_threshold": threshold,
        "iou_threshold": iou,
        "parser": "object-criteria-v4",
    }
