"""
Unified Database Queries for DreamLayer
Provides consistent database access across all components
"""

import os
import sys
from typing import List, Dict, Any, Optional

def get_database_connection():
    """Get database connection using consistent path"""
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'data', 'scripts'))
    from database import DreamLayerDB
    return DreamLayerDB()

def get_all_runs_with_clipscore() -> List[Dict[str, Any]]:
    """
    Unified query to get all runs with ClipScore
    Used by: run_registry.py, report_bundle.py, frontend APIs
    """
    try:
        db = get_database_connection()
        
        with db.get_connection() as conn:
            # Single unified query that joins runs with metrics (NEW SCHEMA)
            cursor = conn.execute("""
                SELECT 
                    r.*,
                    m.clip_score_mean,
                    m.fid_score AS legacy_fid_score, NULL AS fid_score
                FROM runs r
                LEFT JOIN metrics m ON r.run_id = m.run_id
                ORDER BY r.timestamp DESC
            """)
            
            runs = []
            for row in cursor.fetchall():
                from research.legacy import project
                run_dict = project(conn, dict(row))
                # Convert JSON strings back to objects and ensure arrays exist
                for field in ['loras', 'controlnets', 'workflow']:
                    if run_dict.get(field):
                        try:
                            import json
                            run_dict[field] = json.loads(run_dict[field])
                        except (json.JSONDecodeError, TypeError):
                            run_dict[field] = [] if field != 'workflow' else {}
                    else:
                        run_dict[field] = [] if field != 'workflow' else {}
                
                # Ensure generated_images is an array
                if not run_dict.get('generated_images'):
                    run_dict['generated_images'] = []
                elif isinstance(run_dict['generated_images'], str):
                    try:
                        import json
                        run_dict['generated_images'] = json.loads(run_dict['generated_images'])
                    except (json.JSONDecodeError, TypeError):
                        # If it's a single filename string, convert to array
                        run_dict['generated_images'] = [run_dict['generated_images']] if run_dict['generated_images'] else []
                
                # Ensure it's always a list
                if not isinstance(run_dict['generated_images'], list):
                    run_dict['generated_images'] = []
                
                runs.append(run_dict)
            
            return runs
            
    except Exception as e:
        print(f"Error getting runs with ClipScore: {e}")
        return []

def get_single_run_with_clipscore(run_id: str) -> Optional[Dict[str, Any]]:
    """
    Unified query to get single run with ClipScore
    Used by: run_registry.py, report_bundle.py
    """
    try:
        db = get_database_connection()
        
        with db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    r.*,
                    m.clip_score_mean,
                    m.fid_score AS legacy_fid_score, NULL AS fid_score
                FROM runs r
                LEFT JOIN metrics m ON r.run_id = m.run_id
                WHERE r.run_id = ?
            """, (run_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            from research.legacy import project
            
            run_dict = project(conn, dict(row))
            # Convert JSON strings back to objects and ensure arrays exist
            for field in ['loras', 'controlnets', 'workflow']:
                if run_dict.get(field):
                    try:
                        import json
                        run_dict[field] = json.loads(run_dict[field])
                    except (json.JSONDecodeError, TypeError):
                        run_dict[field] = [] if field != 'workflow' else {}
                else:
                    run_dict[field] = [] if field != 'workflow' else {}
            
            # Ensure generated_images is an array
            if not run_dict.get('generated_images'):
                run_dict['generated_images'] = []
            elif isinstance(run_dict['generated_images'], str):
                try:
                    import json
                    run_dict['generated_images'] = json.loads(run_dict['generated_images'])
                except (json.JSONDecodeError, TypeError):
                    run_dict['generated_images'] = [run_dict['generated_images']] if run_dict['generated_images'] else []
            
            return run_dict
            
    except Exception as e:
        print(f"Error getting run {run_id} with ClipScore: {e}")
        return None

def get_all_runs_with_metrics() -> List[Dict[str, Any]]:
    """
    Unified query to get all runs with all metrics (ClipScore, FiD, and Composition)
    Used by: run_registry.py, report_bundle.py, frontend APIs
    """
    try:
        db = get_database_connection()
        
        with db.get_connection() as conn:
            # Single unified query that joins runs with all metrics tables
            cursor = conn.execute("""
                SELECT
                    r.*,
                    m.clip_score_mean,
                    m.fid_score AS legacy_fid_score, NULL AS fid_score,
                    m.metadata as metrics_metadata,
                    cm.macro_precision,
                    cm.macro_recall,
                    cm.macro_f1,
                    cm.per_class_metrics,
                    cm.detected_objects,
                    cm.missing_objects,
                    vm.fvd_score AS legacy_fvd_score, NULL AS fvd_score,
                    vm.video_ssim_mean,
                    vm.video_psnr_mean,
                    vm.video_lpips_mean,
                    vm.metadata as video_metadata
                FROM runs r
                LEFT JOIN metrics m ON r.run_id = m.run_id
                LEFT JOIN composition_metrics cm ON r.run_id = cm.run_id
                LEFT JOIN video_metrics vm ON r.run_id = vm.run_id
                ORDER BY r.timestamp DESC
            """)

            runs = []
            for row in cursor.fetchall():
                from research.legacy import project
                run_dict = project(conn, dict(row))
                # Convert JSON strings back to objects and ensure arrays exist
                for field in ['loras', 'controlnets', 'workflow']:
                    if run_dict.get(field):
                        try:
                            import json
                            run_dict[field] = json.loads(run_dict[field])
                        except (json.JSONDecodeError, TypeError):
                            run_dict[field] = [] if field != 'workflow' else {}
                    else:
                        run_dict[field] = [] if field != 'workflow' else {}

                # Ensure generated_images is an array
                if not run_dict.get('generated_images'):
                    run_dict['generated_images'] = []
                elif isinstance(run_dict['generated_images'], str):
                    try:
                        import json
                        run_dict['generated_images'] = json.loads(run_dict['generated_images'])
                    except (json.JSONDecodeError, TypeError):
                        # If it's a single filename string, convert to array
                        run_dict['generated_images'] = [run_dict['generated_images']] if run_dict['generated_images'] else []

                # Ensure it's always a list
                if not isinstance(run_dict['generated_images'], list):
                    run_dict['generated_images'] = []

                # Parse composition metrics JSON fields
                for field in ['per_class_metrics', 'detected_objects', 'missing_objects']:
                    if run_dict.get(field):
                        try:
                            import json
                            run_dict[field] = json.loads(run_dict[field])
                        except (json.JSONDecodeError, TypeError):
                            run_dict[field] = {}
                    else:
                        run_dict[field] = {}

                # Parse image metrics metadata JSON (composition + aesthetic scores)
                if run_dict.get('metrics_metadata'):
                    try:
                        import json
                        mm = json.loads(run_dict['metrics_metadata'])
                        for key in ['composition_score', 'rule_of_thirds_score', 'symmetry_score', 'balance_score',
                                    'aesthetics_score', 'color_harmony_score', 'saturation_balance', 'value_contrast',
                                    'technical_quality_score', 'sharpness_score', 'noise_level', 'artifact_score',
                                    'overall_aesthetic_quality', 'criterion_pass_rate', 'object_criteria_result']:
                            if key in mm:
                                run_dict[key] = mm[key]
                    except (json.JSONDecodeError, TypeError):
                        pass
                run_dict.pop('metrics_metadata', None)

                # Parse video quality metrics from metadata JSON
                if run_dict.get('video_metadata'):
                    try:
                        import json
                        vm = json.loads(run_dict['video_metadata'])
                        for key in ['adjacent_pixel_stability', 'whole_frame_anchored_dino_cosine',
                                    'whole_frame_adjacent_dino_cosine', 'flow_magnitude_stability',
                                    'video_aesthetic_mean', 'video_aesthetic_min', 'video_aesthetic_std']:
                            if key in vm:
                                run_dict[key] = vm[key]
                    except (json.JSONDecodeError, TypeError):
                        pass
                run_dict.pop('video_metadata', None)

                runs.append(run_dict)
            
            return runs
            
    except Exception as e:
        print(f"Error getting runs with metrics: {e}")
        return []

def get_single_run_with_metrics(run_id: str) -> Optional[Dict[str, Any]]:
    """
    Unified query to get single run with all metrics (ClipScore, FiD, and Composition)
    Used by: run_registry.py, report_bundle.py
    """
    try:
        db = get_database_connection()
        
        with db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT
                    r.*,
                    m.clip_score_mean,
                    m.fid_score AS legacy_fid_score, NULL AS fid_score,
                    m.metadata as metrics_metadata,
                    cm.macro_precision,
                    cm.macro_recall,
                    cm.macro_f1,
                    cm.per_class_metrics,
                    cm.detected_objects,
                    cm.missing_objects,
                    vm.fvd_score AS legacy_fvd_score, NULL AS fvd_score,
                    vm.video_ssim_mean,
                    vm.video_psnr_mean,
                    vm.video_lpips_mean,
                    vm.metadata as video_metadata
                FROM runs r
                LEFT JOIN metrics m ON r.run_id = m.run_id
                LEFT JOIN composition_metrics cm ON r.run_id = cm.run_id
                LEFT JOIN video_metrics vm ON r.run_id = vm.run_id
                WHERE r.run_id = ?
            """, (run_id,))

            row = cursor.fetchone()
            if not row:
                return None

            from research.legacy import project

            run_dict = project(conn, dict(row))
            # Convert JSON strings back to objects and ensure arrays exist
            for field in ['loras', 'controlnets', 'workflow']:
                if run_dict.get(field):
                    try:
                        import json
                        run_dict[field] = json.loads(run_dict[field])
                    except (json.JSONDecodeError, TypeError):
                        run_dict[field] = [] if field != 'workflow' else {}
                else:
                    run_dict[field] = [] if field != 'workflow' else {}

            # Ensure generated_images is an array
            if not run_dict.get('generated_images'):
                run_dict['generated_images'] = []
            elif isinstance(run_dict['generated_images'], str):
                try:
                    import json
                    run_dict['generated_images'] = json.loads(run_dict['generated_images'])
                except (json.JSONDecodeError, TypeError):
                    run_dict['generated_images'] = [run_dict['generated_images']] if run_dict['generated_images'] else []

            # Parse composition metrics JSON fields
            for field in ['per_class_metrics', 'detected_objects', 'missing_objects']:
                if run_dict.get(field):
                    try:
                        import json
                        run_dict[field] = json.loads(run_dict[field])
                    except (json.JSONDecodeError, TypeError):
                        run_dict[field] = {}
                else:
                    run_dict[field] = {}

            # Parse image metrics metadata JSON (composition + aesthetic scores)
            if run_dict.get('metrics_metadata'):
                try:
                    import json
                    mm = json.loads(run_dict['metrics_metadata'])
                    for key in ['composition_score', 'rule_of_thirds_score', 'symmetry_score', 'balance_score',
                                'aesthetics_score', 'color_harmony_score', 'saturation_balance', 'value_contrast',
                                'technical_quality_score', 'sharpness_score', 'noise_level', 'artifact_score',
                                'overall_aesthetic_quality', 'criterion_pass_rate', 'object_criteria_result']:
                        if key in mm:
                            run_dict[key] = mm[key]
                except (json.JSONDecodeError, TypeError):
                    pass
            run_dict.pop('metrics_metadata', None)

            # Parse video quality metrics from metadata JSON
            if run_dict.get('video_metadata'):
                try:
                    import json
                    vm = json.loads(run_dict['video_metadata'])
                    for key in ['adjacent_pixel_stability', 'whole_frame_anchored_dino_cosine',
                                'whole_frame_adjacent_dino_cosine', 'flow_magnitude_stability',
                                'video_aesthetic_mean', 'video_aesthetic_min', 'video_aesthetic_std']:
                        if key in vm:
                            run_dict[key] = vm[key]
                except (json.JSONDecodeError, TypeError):
                    pass
            run_dict.pop('video_metadata', None)

            return run_dict
            
    except Exception as e:
        print(f"Error getting run {run_id} with metrics: {e}")
        return None

def save_run_to_database(run_data: Dict[str, Any]) -> bool:
    """
    Unified function to save run to database
    Used by: txt2img_server.py, img2img_server.py, run_registry.py
    """
    try:
        db = get_database_connection()
        
        # Convert arrays to JSON strings for database storage
        run_data_copy = run_data.copy()
        for field in ['loras', 'controlnets', 'workflow', 'generated_images']:
            if field in run_data_copy and run_data_copy[field]:
                import json
                run_data_copy[field] = json.dumps(run_data_copy[field])
        
        return db.insert_run(run_data_copy)
    except Exception as e:
        print(f"Error saving run to database: {e}")
        return False

def save_assets_to_database(run_id: str, timestamp: str, generated_images: List[str]) -> bool:
    """
    Unified function to save assets to database
    Used by: txt2img_server.py, img2img_server.py, run_registry.py
    """
    try:
        db = get_database_connection()
        output_dir = os.path.join('..', '..', 'Dream_Layer_Resources', 'output')
        return db.insert_assets(run_id, timestamp, generated_images, output_dir)
    except Exception as e:
        print(f"Error saving assets to database: {e}")
        return False

def save_clipscore_to_database(run_id: str, timestamp: str, clip_score: float) -> bool:
    """
    Unified function to save ClipScore to database (NEW SCHEMA)
    Used by: ClipScore calculation modules
    """
    try:
        # Use the new upsert_metric method
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'data', 'scripts'))
        from queries import DreamLayerQueries
        
        queries = DreamLayerQueries()
        return queries.save_clip_score(run_id, timestamp, clip_score)
        
    except Exception as e:
        print(f"Error saving ClipScore to database: {e}")
        return False

def save_fidscore_to_database(run_id: str, timestamp: str, fid_score: float) -> bool:
    """
    Unified function to save FID score to database (NEW SCHEMA)
    Used by: FID calculation modules
    """
    try:
        # Use the new upsert_metric method
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'data', 'scripts'))
        from queries import DreamLayerQueries
        
        queries = DreamLayerQueries()
        return queries.save_fid_score(run_id, timestamp, fid_score)
        
    except Exception as e:
        print(f"Error saving FID score to database: {e}")
        return False

def get_database_stats() -> Dict[str, Any]:
    """Get database statistics"""
    try:
        db = get_database_connection()
        
        with db.get_connection() as conn:
            # Count runs
            cursor = conn.execute("SELECT COUNT(*) as count FROM runs")
            total_runs = cursor.fetchone()['count']
            
            # Count runs with ClipScore
            cursor = conn.execute("""
                SELECT COUNT(*) as count FROM runs r
                INNER JOIN metrics m ON r.run_id = m.run_id 
                WHERE m.metric_name = 'clip_score_mean'
            """)
            runs_with_clipscore = cursor.fetchone()['count']
            
            # Count total assets
            cursor = conn.execute("SELECT COUNT(*) as count FROM assets")
            total_assets = cursor.fetchone()['count']
            
            return {
                'database_path': db.db_path,
                'total_runs': total_runs,
                'runs_with_clipscore': runs_with_clipscore,
                'total_assets': total_assets,
                'runs_without_clipscore': total_runs - runs_with_clipscore
            }
            
    except Exception as e:
        return {'error': str(e)}

if __name__ == "__main__":
    # Test unified queries
    print("🧪 Testing Unified Database Queries")
    print("=" * 40)
    
    # Test database stats
    stats = get_database_stats()
    print(f"Database stats: {stats}")
    
    # Test getting all runs
    runs = get_all_runs_with_clipscore()
    print(f"Total runs with ClipScore: {len(runs)}")
    
    if runs:
        sample = runs[0]
        print(f"Sample run: {sample['run_id'][:8]}... ClipScore: {sample.get('clip_score_mean', 'None')}")
