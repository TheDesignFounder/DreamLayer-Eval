"""Composition database adapter over the shared, versioned criteria scorer."""
import os
import logging
from pathlib import Path
import sys
from typing import Optional, Dict, Any
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from queries import DreamLayerQueries
from dream_layer_backend.dream_layer_backend_utils.composition_metrics import CompositionMetricsCalculator as SharedCalculator
logger = logging.getLogger(__name__)

class CompositionMetricsCalculator(SharedCalculator):
    def calculate_metrics(self, prompt, image_path):
        return self.calculate_object_metrics(prompt, image_path)

class DatabaseCompositionCalculator:
    """Composition metrics calculator that uses database for path resolution (follows ClipScore pattern)"""
    
    def __init__(self):
        self.queries = DreamLayerQueries()
        self.composition_calculator = CompositionMetricsCalculator()
    
    def calculate_for_run(self, run_id: str, image_index: int = 0) -> Optional[Dict[str, Any]]:
        """Calculate composition metrics for a specific run and image"""
        try:
            # Get run data
            run = self.queries.db.get_run(run_id)
            if not run:
                logger.error(f"Run {run_id} not found in database")
                return None
            
            # Reuse the working ClipScore image path method
            image_path = self.queries.get_image_path_for_clip_score(run_id, image_index)
            if not image_path:
                logger.error(f"No image path found for run {run_id}")
                return None
            
            # Get prompt
            prompt = run.get('prompt', '')
            if not prompt:
                logger.error(f"No prompt found for run {run_id}")
                return None
            
            # Calculate composition metrics using the working image path
            metrics = self.composition_calculator.calculate_metrics(prompt, image_path)
            
            # Save to database
            if self.queries.save_composition_metrics(run_id, run['timestamp'], prompt, image_path, metrics):
                logger.info(f"Calculated and saved composition metrics for run {run_id}")
                return metrics
            else:
                logger.error(f"Failed to save composition metrics for run {run_id}")
                return metrics  # Return value even if save failed
            
        except Exception as e:
            logger.error(f"Error calculating composition metrics for run {run_id}: {e}")
            return None
    
    def calculate_batch(self, limit: int = 2000) -> Dict[str, Any]:
        """Calculate composition metrics for multiple runs that don't have it"""
        # Get runs without composition metrics
        runs_without_composition = self.queries.get_runs_without_composition_metrics(limit)
        
        stats = {
            "total": len(runs_without_composition),
            "success": 0,
            "failed": 0,
            "results": []
        }
        
        logger.info(f"Calculating composition metrics for {stats['total']} runs...")
        
        for run in runs_without_composition:
            run_id = run['run_id']
            if not self.queries.can_compute_metrics_for_run(run_id): continue
            metrics = self.calculate_for_run(run_id)
            
            if metrics is not None:
                stats["success"] += 1
                stats["results"].append({
                    "run_id": run_id,
                    "macro_f1": metrics["macro_f1"],
                    "macro_precision": metrics["macro_precision"],
                    "macro_recall": metrics["macro_recall"],
                    "prompt": run.get('prompt', '')[:50] + "..."
                })
            else:
                stats["failed"] += 1
        
        logger.info(f"Batch calculation complete: {stats['success']} success, {stats['failed']} failed")
        return stats


def calculate_missing_composition_metrics(limit: int = 2000) -> Dict[str, Any]:
    """Convenience function to calculate missing composition metrics"""
    calculator = DatabaseCompositionCalculator()
    return calculator.calculate_batch(limit)

def compute_composition_metrics_for_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Convenience function to calculate composition metrics for a single run"""
    calculator = DatabaseCompositionCalculator()
    return calculator.calculate_for_run(run_id)


if __name__ == "__main__":
    # Test composition metrics calculation
    calculator = DatabaseCompositionCalculator()
    
    # Calculate for runs without composition metrics
    stats = calculator.calculate_batch(limit=5)
    print(f"Calculated composition metrics for {stats['success']}/{stats['total']} runs")
    
    # Show results
    for result in stats['results'][:3]:
        print(f"Run {result['run_id']}: F1 {result['macro_f1']:.4f}, P {result['macro_precision']:.4f}, R {result['macro_recall']:.4f}")
