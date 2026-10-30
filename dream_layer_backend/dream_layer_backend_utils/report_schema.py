"""
Clean schema architecture for DreamLayer report bundles.
Separates configuration data from metrics data for better scalability.
"""

import json
import math
import hashlib
import csv
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime


@dataclass
class RunMetrics:
    """Flat metrics data for CSV storage."""
    run_id: str
    # ClipScore metrics
    clip_score_mean: Optional[float] = None
    clip_score_median: Optional[float] = None
    clip_score_std: Optional[float] = None
    clip_score_max: Optional[float] = None
    clip_score_min: Optional[float] = None
    schema_version: str = "2"
    metric_id: str = "clip_cosine"
    metric_version: str = "legacy-unverified"
    status: str = "not_evaluated"
    reason: str = "No successful evaluation recorded"
    # Future metrics can be added here
    # aesthetic_score: Optional[float] = None
    # fid_score: Optional[float] = None
    # lpips_score: Optional[float] = None


@dataclass
class RunConfig:
    """Rich configuration data for JSON storage."""
    run_id: str
    metadata: Dict[str, Any]
    parameters: Dict[str, Any]
    assets: Dict[str, List[str]]
    workflow: Dict[str, Any]


class ReportDataManager:
    """Manages the dual-schema report data architecture."""
    
    def __init__(self, output_dir: str = "Dream_Layer_Resources/output"):
        self.output_dir = output_dir
        
    def save_run_config(self, config: RunConfig, config_file: str = "configs.json") -> None:
        """Save run configuration to JSON file."""
        config_path = os.path.join(self.output_dir, config_file)
        
        # Load existing configs or create new
        configs = {}
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                configs = json.load(f)
        
        # Add new config
        configs[config.run_id] = asdict(config)
        
        # Save back to file
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(configs, f, indent=2, ensure_ascii=False)
    
    def load_run_configs(self, config_file: str = "configs.json") -> Dict[str, RunConfig]:
        """Load all run configurations from JSON file."""
        config_path = os.path.join(self.output_dir, config_file)
        
        if not os.path.exists(config_path):
            return {}
        
        with open(config_path, 'r', encoding='utf-8') as f:
            configs_data = json.load(f)
        
        # Convert back to RunConfig objects
        configs = {}
        for run_id, config_data in configs_data.items():
            configs[run_id] = RunConfig(**config_data)
        
        return configs
    
    def save_run_metrics(self, metrics: List[RunMetrics], csv_file: str = "results.csv") -> str:
        """Save run metrics to CSV file."""
        csv_path = os.path.join(self.output_dir, csv_file)
        
        if not metrics:
            return csv_path
        
        # Get all field names from the dataclass
        fieldnames = list(asdict(metrics[0]).keys())
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for metric in metrics:
                writer.writerow(asdict(metric))
        
        return csv_path
    
    def load_run_metrics(self, csv_file: str = "results.csv") -> List[RunMetrics]:
        """Load run metrics from CSV file."""
        csv_path = os.path.join(self.output_dir, csv_file)
        
        if not os.path.exists(csv_path):
            return []
        
        metrics = []
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Convert string values to appropriate types
                for key, value in row.items():
                    if key.startswith('clip_score_'):
                        try:
                            row[key] = float(value) if value and math.isfinite(float(value)) else None
                        except (ValueError, TypeError):
                            row[key] = None
                
                metrics.append(RunMetrics(**row))
        
        return metrics
    
    def convert_legacy_registry(self, registry_file: str = "run_registry.json") -> None:
        """Convert legacy run_registry.json to new schema."""
        registry_path = os.path.join("dream_layer_backend", registry_file)
        
        if not os.path.exists(registry_path):
            print(f"Legacy registry not found: {registry_path}")
            return
        
        print("🔄 Converting legacy registry to new schema...")
        
        with open(registry_path, 'r', encoding='utf-8') as f:
            legacy_data = json.load(f)
        
        configs = []
        for run_id, run_data in legacy_data.items():
            # Convert to new schema
            config = RunConfig(
                run_id=run_id,
                metadata={
                    "timestamp": run_data.get("timestamp", ""),
                    "generation_type": run_data.get("generation_type", "txt2img"),
                    "model": run_data.get("model", ""),
                    "version": run_data.get("version", "1.0.0")
                },
                parameters={
                    "prompt": run_data.get("prompt", ""),
                    "negative_prompt": run_data.get("negative_prompt", ""),
                    "seed": run_data.get("seed", -1),
                    "steps": run_data.get("steps", 20),
                    "cfg_scale": run_data.get("cfg_scale", 7.0),
                    "width": run_data.get("width", 512),
                    "height": run_data.get("height", 512),
                    "batch_size": run_data.get("batch_size", 1),
                    "batch_count": run_data.get("batch_count", 1),
                    "sampler": run_data.get("sampler", "euler"),
                    "vae": run_data.get("vae")
                },
                assets={
                    "generated_images": run_data.get("generated_images", []),
                    "input_images": []  # Legacy doesn't have this
                },
                workflow={
                    "loras": run_data.get("loras", []),
                    "controlnets": run_data.get("controlnets", []),
                    "workflow_hash": hashlib.sha256(json.dumps(run_data.get('workflow', {}), sort_keys=True).encode()).hexdigest()
                }
            )
            configs.append(config)
        
        # Save converted configs
        for config in configs:
            self.save_run_config(config)
        
        print(f"✅ Converted {len(configs)} runs to new schema")
    
    def compute_and_save_metrics(self, run_ids: Optional[List[str]] = None) -> str:
        """Compute metrics for runs and save to CSV."""
        from .clip_score_metrics import get_clip_calculator
        
        # Load configurations
        configs = self.load_run_configs()
        
        if not configs:
            print("❌ No configurations found. Run convert_legacy_registry() first.")
            return ""
        
        # Filter by run_ids if specified
        if run_ids:
            configs = {rid: config for rid, config in configs.items() if rid in run_ids}
        
        print(f"🔄 Computing metrics for {len(configs)} runs...")
        
        # Get ClipScore calculator
        clip_calculator = get_clip_calculator()
        
        metrics_list = []
        for run_id, config in configs.items():
            print(f"   Processing {run_id[:8]}...")
            
            # Initialize metrics
            metrics = RunMetrics(run_id=run_id)
            
            # Compute ClipScore if we have prompt and images
            prompt = config.parameters.get("prompt", "")
            images = config.assets.get("generated_images", [])
            
            if prompt and images:
                try:
                    clip_metrics = clip_calculator.compute_metrics_for_batch(prompt, images)
                    metrics.clip_score_mean = clip_metrics["clip_score_mean"]
                    metrics.status = "success" if metrics.clip_score_mean is not None else "unavailable_dependency"
                    metrics.reason = "" if metrics.status == "success" else "CLIP model or image unavailable"
                    metrics.clip_score_median = clip_metrics["clip_score_median"]
                    metrics.clip_score_std = clip_metrics["clip_score_std"]
                    metrics.clip_score_max = clip_metrics["clip_score_max"]
                    metrics.clip_score_min = clip_metrics["clip_score_min"]
                    
                    print(f"      ClipScore: {metrics.clip_score_mean:.4f}")
                except Exception as e:
                    print(f"      ⚠️ ClipScore failed: {e}")
            
            metrics_list.append(metrics)
        
        # Save metrics to CSV
        csv_path = self.save_run_metrics(metrics_list)
        print(f"✅ Metrics saved to: {csv_path}")
        
        return csv_path


def create_report_bundle(run_ids: Optional[List[str]] = None) -> str:
    """Create a complete report bundle with the new schema."""
    manager = ReportDataManager()
    
    # Convert legacy data if needed
    if not os.path.exists(os.path.join(manager.output_dir, "configs.json")):
        manager.convert_legacy_registry()
    
    # Compute and save metrics
    csv_path = manager.compute_and_save_metrics(run_ids)
    
    return csv_path
