"""Read-only checks: never submit generation or judge requests."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from .metrics import dependencies
from .pricing import estimate, validate_pricing
from .types import JsonObject


def inspect(config: JsonObject, transport: Any = requests) -> JsonObject:
    "Inspect local dependencies and endpoint readiness without submitting paid work."
    checks, estimates = [], []
    for metric in config.get("metrics", []):
        missing = dependencies(metric["id"])
        checks.append(
            {
                "component": metric["id"],
                "check": "imports",
                "status": "unavailable" if missing else "ready",
                "missing": missing,
            }
        )
        if metric["id"] == "object_criteria":
            ready = bool(metric.get("weights") and Path(metric["weights"]).is_file())
            checks.append(
                {
                    "component": metric["id"],
                    "check": "weights",
                    "status": "ready" if ready else "unavailable",
                    "reason": "Explicit local detector weights required",
                }
            )
        elif metric["id"] == "clip_cosine":
            checks.append(
                {
                    "component": metric["id"],
                    "check": "revision",
                    "status": "configured" if metric.get("revision") else "unavailable",
                    "reason": "Pinned revision required; local model cache and inference not verified by preflight",
                }
            )
        elif metric["id"] in {"fid", "vqascore", "dino_similarity", "lpips", "fvd"}:
            checks.append(
                {
                    "component": metric["id"],
                    "check": "weights_and_inference",
                    "status": "unverified",
                    "reason": "Run an evaluator smoke test in the intended model environment",
                }
            )
    for judge in config.get("judges", []):
        provider = judge.get("provider", "synthetic")
        env = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}.get(provider)
        checks.append(
            {
                "component": provider,
                "check": "judge_credentials",
                "status": "synthetic"
                if provider == "synthetic"
                else "configured"
                if env and os.getenv(env)
                else "unavailable",
                "reason": "Presence only; credentials, model access and provider compatibility are not live-validated",
            }
        )
        validate_pricing(judge.get("pricing"))
        budget = judge.get("budget", {})
        # Explicit token scenarios are estimates, never a claim about billed usage.
        scenario = judge.get("estimated_usage")
        estimates.append(
            {
                "provider": provider,
                "model": judge.get("model"),
                "per_call_estimate_usd": estimate(scenario, judge.get("pricing"), provider),
                "usage_scenario": scenario,
                "pricing": judge.get("pricing"),
                "budget": budget,
            }
        )
    generation = config.get("generation")
    if generation:
        from .generation import resolve_workflow

        for prompt in config["prompts"]:
            for model in config.get("models", ["imported"]):
                try:
                    _, bound, unbound = resolve_workflow(
                        generation, prompt, config.get("parameters", {}).get(model, {})
                    )
                    checks.append(
                        {
                            "component": "generation",
                            "check": "bindings",
                            "prompt_id": prompt["id"],
                            "model": model,
                            "status": "warning" if unbound else "configured",
                            "bound": list(bound),
                            "unbound": list(unbound),
                            "reason": "Workflow input binding is not proof of provider parameter enforcement",
                        }
                    )
                except (KeyError, ValueError, TypeError) as exc:
                    checks.append(
                        {
                            "component": "generation",
                            "check": "bindings",
                            "status": "unavailable",
                            "reason": str(exc),
                        }
                    )
        base = generation.get("base_url", "http://127.0.0.1:8188").rstrip("/")
        if urlparse(base).hostname not in {"127.0.0.1", "localhost", "::1"}:
            checks.append(
                {
                    "component": "generation",
                    "check": "endpoint",
                    "status": "unavailable",
                    "reason": "ComfyUI adapter requires a local endpoint",
                }
            )
        else:
            try:
                response = transport.get(base + "/system_stats", timeout=3)
                response.raise_for_status()
                body = response.json()
                checks.append(
                    {
                        "component": "generation",
                        "check": "endpoint",
                        "status": "reachable",
                        "system_stats_received": isinstance(body, dict),
                        "reason": "Read-only connectivity check; no workflow submitted",
                    }
                )
            except (requests.RequestException, ValueError) as exc:
                checks.append(
                    {
                        "component": "generation",
                        "check": "endpoint",
                        "status": "unavailable",
                        "reason": type(exc).__name__,
                    }
                )
    return {"checks": checks, "judge_cost_scenarios": estimates, "provider_calls_submitted": 0}
