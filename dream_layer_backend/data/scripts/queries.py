"""
DreamLayer Database Query Interface
Provides high-level query functions for runs, assets, and metrics
Used by report_bundle.py and other components
"""

import os
import json
from typing import Dict, List, Any, Optional, Tuple
from database import DreamLayerDB
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DreamLayerQueries:
    """High-level query interface for DreamLayer database"""
    
    def __init__(self):
        self.db = DreamLayerDB()
    
    def get_runs_for_csv_export(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get runs formatted for CSV export (compatible with report_bundle.py)"""
        try:
            runs_with_metrics = self.db.get_runs_with_metrics(limit)
            csv_formatted_runs = []
            
            for run in runs_with_metrics:
                # Get assets for this run
                assets = self.db.get_run_assets(run['run_id'])
                
                # Format for CSV export
                csv_run = {
                    'run_id': run['run_id'],
                    'timestamp': run['timestamp'],
                    'model': run['model'],
                    'vae': run['vae'],
                    'prompt': run['prompt'],
                    'negative_prompt': run['negative_prompt'],
                    'seed': run['seed'],
                    'sampler': run['sampler'],
                    'steps': run['steps'],
                    'cfg_scale': run['cfg_scale'],
                    'width': run['width'],
                    'height': run['height'],
                    'batch_size': run['batch_size'],
                    'batch_count': run['batch_count'],
                    'generation_type': run['generation_type'],
                    'loras': run['loras'],
                    'controlnets': run['controlnets'],
                    'workflow_hash': '',  # Can be computed from workflow if needed
                    
                    # Image paths (comma-separated for CSV)
                    'image_paths': ','.join([asset['asset_value'] for asset in assets]),
                    
                    # Metrics (with defaults for missing values)
                    'clip_score_mean': run['metrics'].get('clip_score_mean'),
                    'fid_score': run['metrics'].get('fid_score'),
                    'legacy_fid_score': run['metrics'].get('legacy_fid_score'),
                    'fid_status': run['metrics'].get('fid_status'),
                }
                
                csv_formatted_runs.append(csv_run)
            
            return csv_formatted_runs
            
        except Exception as e:
            logger.error(f"Error getting runs for CSV export: {e}")
            return []
    
    def get_run_with_full_data(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get complete run data including assets and metrics"""
        try:
            run = self.db.get_run(run_id)
            if not run:
                return None
            
            # Add assets
            assets = self.db.get_run_assets(run_id)
            run['assets'] = assets
            
            # Add metrics
            metrics = self.db.get_run_metrics(run_id)
            run['metrics'] = {
                'clip_score_mean': metrics.get('clip_score_mean'),
                'fid_score': metrics.get('fid_score')
            }
            
            return run
            
        except Exception as e:
            logger.error(f"Error getting full run data for {run_id}: {e}")
            return None
    
    def get_image_path_for_clip_score(self, run_id: str, image_index: int = 0) -> Optional[str]:
        """Get full image path for ClipScore calculation using absolute paths"""
        try:
            assets = self.db.get_run_assets(run_id)
            
            if not assets or image_index >= len(assets):
                logger.warning(f"No asset found for run {run_id} at index {image_index}")
                return None
            
            asset = assets[image_index]
            stored_path = asset['full_path']
            filename = asset['asset_value']
            
            # Try the stored path first
            if os.path.exists(stored_path):
                return stored_path
            
            # Find DreamLayer project root (look for characteristic files)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = current_dir
            
            # Navigate up to find DreamLayer root (contains Dream_Layer_Resources)
            while project_root != os.path.dirname(project_root):  # Not at filesystem root
                if os.path.exists(os.path.join(project_root, 'Dream_Layer_Resources', 'output')):
                    break
                project_root = os.path.dirname(project_root)
            
            # Define search paths relative to project root
            search_paths = [
                os.path.join(project_root, 'Dream_Layer_Resources', 'output'),
                os.path.join(project_root, 'dream_layer_backend', 'served_images'),
                os.path.join(project_root, 'ComfyUI', 'output'),
                os.path.join(project_root, 'ComfyUI', 'input'),
                project_root
            ]
            
            for search_path in search_paths:
                full_path = os.path.join(search_path, filename)
                if os.path.exists(full_path):
                    logger.debug(f"Found image at: {full_path}")
                    return full_path
            
            logger.warning(f"Image file not found in any search path: {filename}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting image path for run {run_id}: {e}")
            return None
    
    def save_clip_score(self, run_id: str, timestamp: str, clip_score: float, 
                       metadata: Dict = None) -> bool:
        """Save ClipScore metric for a run"""
        return self.db.upsert_metric(run_id, timestamp, clip_score_mean=clip_score, metadata=metadata)
    
    def save_fid_score(self, run_id: str, timestamp: str, fid_score: float, 
                      metadata: Dict = None) -> bool:
        """Save FID metric for a run"""
        return self.db.upsert_metric(run_id, timestamp, fid_score=fid_score, metadata=metadata)
    
    def save_composition_metrics(self, run_id: str, timestamp: str, prompt_text: str, 
                               image_path: str, metrics: Dict[str, Any]) -> bool:
        """Save composition metrics for a run"""
        return self.db.upsert_composition_metrics(run_id, timestamp, prompt_text, image_path, metrics)
    
    def get_composition_metrics(self, run_id):
        return self.db.get_composition_metrics(run_id)

    def get_runs_without_clip_score(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get runs that don't have ClipScore calculated yet"""
        try:
            with self.db.get_connection() as conn:
                query = """
                    SELECT r.* FROM runs r
                    LEFT JOIN metrics m ON r.run_id = m.run_id
                    WHERE m.clip_score_mean IS NULL
                    ORDER BY r.timestamp DESC
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor = conn.execute(query)
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error getting runs without ClipScore: {e}")
            return []
    
    def get_runs_without_fid_score(self, limit=None):
        return []  # Dataset FID has no per-run pending state.
    
    def get_runs_without_composition_metrics(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get runs that don't have composition metrics calculated yet"""
        try:
            with self.db.get_connection() as conn:
                query = """
                    SELECT r.* FROM runs r
                    LEFT JOIN composition_metrics cm ON r.run_id = cm.run_id
                    WHERE cm.run_id IS NULL AND NOT EXISTS (SELECT 1 FROM research_records rr WHERE rr.kind='result' AND json_extract(rr.payload,'$.source_run_id')=r.run_id AND json_extract(rr.payload,'$.metric_id')='object_criteria')
                    ORDER BY r.timestamp DESC
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor = conn.execute(query)
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error getting runs without composition metrics: {e}")
            return []
    
    def can_compute_metrics_for_run(self, run_id: str) -> bool:
        """Check if run has accessible image files for metrics computation"""
        image_path = self.get_image_path_for_clip_score(run_id, 0)
        return image_path is not None and os.path.exists(image_path)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary statistics for all metrics"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(clip_score_mean) as clip_count,
                        AVG(clip_score_mean) as clip_avg,
                        MIN(clip_score_mean) as clip_min,
                        MAX(clip_score_mean) as clip_max,
                        COUNT(fid_score) as fid_count
                    FROM metrics
                """)
                
                row = cursor.fetchone()
                if row:
                    summary = {}
                    
                    if row['clip_count'] > 0:
                        summary['clip_score_mean'] = {
                            'count': row['clip_count'],
                            'average': row['clip_avg'],
                            'minimum': row['clip_min'],
                            'maximum': row['clip_max']
                        }
                    
                    if row['fid_count'] > 0:
                        summary['legacy_fid_score'] = {
                            'count': row['fid_count'],
                            'status': 'invalid_legacy_result',
                            'reason': 'Per-run FID values are not a distribution-level FID; aggregation disabled'
                        }
                    
                    return summary
                
                return {}
                
        except Exception as e:
            logger.error(f"Error getting metrics summary: {e}")
            return {}
    
    def search_runs(self, model: str = None, prompt_contains: str = None, 
                   generation_type: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Search runs with filters"""
        try:
            conditions = []
            params = []
            
            if model:
                conditions.append("model = ?")
                params.append(model)
            
            if prompt_contains:
                conditions.append("prompt LIKE ?")
                params.append(f"%{prompt_contains}%")
            
            if generation_type:
                conditions.append("generation_type = ?")
                params.append(generation_type)
            
            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)
            
            query = f"""
                SELECT * FROM runs 
                {where_clause}
                ORDER BY timestamp DESC 
                LIMIT {limit}
            """
            
            with self.db.get_connection() as conn:
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error searching runs: {e}")
            return []
    
    def export_to_legacy_json(self, output_path: str = None) -> bool:
        """Export database back to run_registry.json format for backup"""
        try:
            if output_path is None:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                output_path = os.path.join(script_dir, '..', '..', 'run_registry_backup.json')
            
            runs = self.db.get_all_runs()
            legacy_data = {}
            
            for run in runs:
                # Get assets for this run
                assets = self.db.get_run_assets(run['run_id'])
                generated_images = [asset['asset_value'] for asset in assets]
                
                # Convert back to legacy format
                legacy_run = dict(run)
                legacy_run['generated_images'] = generated_images
                
                # Parse JSON fields back to objects
                json_fields = ['loras', 'controlnets', 'workflow']
                for field in json_fields:
                    if legacy_run.get(field):
                        try:
                            legacy_run[field] = json.loads(legacy_run[field])
                        except (json.JSONDecodeError, TypeError):
                            pass  # Keep as string if not valid JSON
                
                legacy_data[run['run_id']] = legacy_run
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(legacy_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Exported {len(legacy_data)} runs to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting to legacy JSON: {e}")
            return False

# Convenience functions for common operations
def get_queries() -> DreamLayerQueries:
    """Get a queries instance"""
    return DreamLayerQueries()

def get_csv_data(limit: int = None) -> List[Dict[str, Any]]:
    """Quick function to get CSV-formatted data"""
    queries = DreamLayerQueries()
    return queries.get_runs_for_csv_export(limit)

def calculate_missing_clip_scores():
    """Calculate ClipScore for runs that don't have it yet"""
    from dream_layer_backend_utils.clip_score_metrics import get_clip_calculator
    
    queries = DreamLayerQueries()
    runs_without_clip = queries.get_runs_without_clip_score(limit=50)
    
    if not runs_without_clip:
        logger.info("All runs already have ClipScore calculated")
        return
    
    logger.info(f"Calculating ClipScore for {len(runs_without_clip)} runs...")
    
    # Get ClipScore calculator
    clip_calculator = get_clip_calculator()
    if not clip_calculator:
        logger.error("Could not initialize ClipScore calculator")
        return
    
    success_count = 0
    for run in runs_without_clip:
        try:
            # Get image path
            image_path = queries.get_image_path_for_clip_score(run['run_id'])
            if not image_path:
                logger.warning(f"No image found for run {run['run_id']}")
                continue
            
            # Calculate ClipScore
            prompt = run.get('prompt', '')
            if not prompt:
                logger.warning(f"No prompt found for run {run['run_id']}")
                continue
            
            clip_score = clip_calculator.calculate_clip_score(prompt, image_path)
            
            # Save to database
            if queries.save_clip_score(run['run_id'], run['timestamp'], clip_score):
                success_count += 1
                logger.info(f"Calculated ClipScore {clip_score:.4f} for run {run['run_id']}")
            
        except Exception as e:
            logger.error(f"Error calculating ClipScore for run {run['run_id']}: {e}")
    
    logger.info(f"Successfully calculated ClipScore for {success_count}/{len(runs_without_clip)} runs")

if __name__ == "__main__":
    # Test queries
    queries = DreamLayerQueries()
    
    # Get summary
    summary = queries.get_metrics_summary()
    print("Metrics Summary:", summary)
    
    # Get recent runs
    recent_runs = queries.get_csv_data(limit=5)
    print(f"Recent runs: {len(recent_runs)}")
    
    # Calculate missing ClipScores
    calculate_missing_clip_scores()
