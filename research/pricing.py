"""Explicit, versioned user-supplied prices. Estimates are not confirmed billing."""

from __future__ import annotations

import math

from .types import JsonObject


def validate_pricing(pricing: JsonObject | None) -> None:
    "Require a dated USD price table with finite nonnegative rates."
    if not pricing:
        return
    for field in ("version", "as_of", "source", "currency"):
        if not pricing.get(field):
            raise ValueError("Pricing requires version, as_of, source and currency")
    if pricing["currency"] != "USD":
        raise ValueError("Only explicitly USD-denominated price tables are supported")
    for field in (
        "input_per_million",
        "output_per_million",
        *[k for k in ("cached_input_per_million", "cache_write_per_million") if k in pricing],
    ):
        if (
            not isinstance(pricing.get(field), (int, float))
            or not math.isfinite(pricing[field])
            or pricing[field] < 0
        ):
            raise ValueError("Prices must be finite nonnegative USD amounts per million tokens")


def estimate(usage: JsonObject | None, pricing: JsonObject | None, provider: str) -> float | None:
    "Estimate usage cost from explicit rates, returning null when required data is missing."
    if not pricing or usage is None:
        return None
    validate_pricing(pricing)
    incoming = usage.get("input_tokens")
    outgoing = usage.get("output_tokens")
    if incoming is None or outgoing is None:
        return None
    cached = (
        usage.get("input_tokens_details", {}).get("cached_tokens", 0)
        if provider == "openai"
        else usage.get("cache_read_input_tokens", 0)
    )
    writes = usage.get("cache_creation_input_tokens", 0)
    if (
        cached
        and "cached_input_per_million" not in pricing
        or writes
        and "cache_write_per_million" not in pricing
    ):
        return None
    ordinary = incoming - cached if provider == "openai" else incoming
    counts = [ordinary, outgoing, cached, writes]
    if any(not isinstance(n, (int, float)) or not math.isfinite(n) or n < 0 for n in counts):
        return None
    return (
        ordinary * pricing["input_per_million"]
        + outgoing * pricing["output_per_million"]
        + cached * pricing.get("cached_input_per_million", 0)
        + writes * pricing.get("cache_write_per_million", 0)
    ) / 1_000_000
