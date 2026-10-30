"""
DreamLayer Database Setup and Schema Management
Handles SQLite database creation, schema setup, and basic operations
"""

import sqlite3
import os
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DreamLayerDB:
    """Main database interface for DreamLayer"""
    
    def __init__(self, db_path: str = None):
        from pathlib import Path
        import sys
        project_root = Path(__file__).resolve().parents[3]
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        self.db_path = str(Path(db_path or os.getenv('TEST_DB_PATH') or os.getenv('DREAMLAYER_DB_PATH') or project_root / 'dream_layer_backend/data/dreamlayer.db').resolve())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        from research.store import Store
        Store(self.db_path)
        self.create_schema()
        self.ensure_all_tables_exist()
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with foreign key support"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        return conn
    
    def ensure_database_exists(self):
        """Create database and tables if they don't exist"""
        if not os.path.exists(self.db_path):
            logger.info(f"Creating new database at {self.db_path}")
            self.create_schema()
        else:
            logger.info(f"Using existing database at {self.db_path}")
            # Check and create any missing tables
            self.ensure_all_tables_exist()
    
    def create_schema(self):
        """Create all database tables with proper schema"""
        with self.get_connection() as conn:
            # Runs table - mirrors run_registry.json exactly
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    model TEXT,
                    vae TEXT,
                    loras TEXT,
                    controlnets TEXT,
                    prompt TEXT,
                    negative_prompt TEXT,
                    seed INTEGER,
                    sampler TEXT,
                    steps INTEGER,
                    cfg_scale REAL,
                    width INTEGER,
                    height INTEGER,
                    batch_size INTEGER,
                    batch_count INTEGER,
                    workflow TEXT,
                    version TEXT,
                    generation_type TEXT,
                    generated_images TEXT
                )
            """)
            
            # Create indexes for runs table
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_model ON runs(model)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_generation_type ON runs(generation_type)")
            
            # Assets table - key-value store for images and files
            conn.execute("""
                CREATE TABLE IF NOT EXISTS assets (
                    run_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    asset_key TEXT NOT NULL,
                    asset_value TEXT,
                    full_path TEXT,
                    file_size INTEGER,
                    metadata TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
                    PRIMARY KEY (run_id, asset_key)
                )
            """)
            
            # Create indexes for assets table
            conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_timestamp ON assets(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_run_id ON assets(run_id)")
            
            # Metrics table - dedicated columns for each metric
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    run_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    clip_score_mean REAL,
                    fid_score REAL,
                    computed_at TEXT DEFAULT (datetime('now')),
                    metadata TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
                    PRIMARY KEY (run_id)
                )
            """)
            
            # Create indexes for metrics table
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_run_id ON metrics(run_id)")
            
            conn.commit()
            logger.info("Database schema created successfully")
    
    def ensure_all_tables_exist(self):
        """Check for missing tables and create them automatically"""
        with self.get_connection() as conn:
            # Check if composition_metrics table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='composition_metrics'
            """)
            
            if not cursor.fetchone():
                logger.info("Creating missing composition_metrics table")
                self.create_composition_metrics_table()

            # Check if embedding_cache table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='embedding_cache'
            """)

            if not cursor.fetchone():
                logger.info("Creating missing embedding_cache table")
                self.create_embedding_cache_table()

            # Check if video_metrics table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='video_metrics'
            """)

            if not cursor.fetchone():
                logger.info("Creating missing video_metrics table")
                self.create_video_metrics_table()
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (table_name,))
            return cursor.fetchone() is not None
    
    def create_composition_metrics_table(self):
        """Create the composition_metrics table"""
        with self.get_connection() as conn:
            # Create composition_metrics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS composition_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    prompt_text TEXT,
                    image_path TEXT,
                    macro_precision REAL,
                    macro_recall REAL,
                    macro_f1 REAL,
                    per_class_metrics TEXT,
                    detected_objects TEXT,
                    missing_objects TEXT,
                    timestamp TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                )
            """)
            
            # Create indexes for composition_metrics table
            conn.execute("CREATE INDEX IF NOT EXISTS idx_composition_metrics_run_id ON composition_metrics(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_composition_metrics_timestamp ON composition_metrics(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_composition_metrics_f1 ON composition_metrics(macro_f1)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_composition_metrics_precision ON composition_metrics(macro_precision)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_composition_metrics_recall ON composition_metrics(macro_recall)")
            
            conn.commit()
            logger.info("composition_metrics table created successfully")

    def create_embedding_cache_table(self):
        """Create the embedding_cache table for storing CLIP and Inception embeddings"""
        with self.get_connection() as conn:
            # Create embedding_cache table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    embedding_type TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    embedding_data BLOB NOT NULL,
                    embedding_dim INTEGER NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(source_type, source_id, embedding_type, model_name)
                )
            """)

            # Create indexes for embedding_cache table
            conn.execute("CREATE INDEX IF NOT EXISTS idx_embedding_cache_source ON embedding_cache(source_type, source_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_embedding_cache_type ON embedding_cache(embedding_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_embedding_cache_model ON embedding_cache(model_name)")

            conn.commit()
            logger.info("embedding_cache table created successfully")

    def create_video_metrics_table(self):
        """Create the video_metrics table for storing video evaluation metrics"""
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS video_metrics (
                    run_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    fvd_score REAL,
                    video_ssim_mean REAL,
                    video_ssim_std REAL,
                    video_psnr_mean REAL,
                    video_psnr_std REAL,
                    video_lpips_mean REAL,
                    video_lpips_std REAL,
                    per_frame_data TEXT,
                    computed_at TEXT DEFAULT (datetime('now')),
                    metadata TEXT,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_video_metrics_run_id ON video_metrics(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_video_metrics_timestamp ON video_metrics(timestamp)")

            conn.commit()
            logger.info("video_metrics table created successfully")

    def upsert_video_metrics(self, run_id: str, timestamp: str,
                             fvd_score: float = None, video_ssim_mean: float = None,
                             video_ssim_std: float = None, video_psnr_mean: float = None,
                             video_psnr_std: float = None, video_lpips_mean: float = None,
                             video_lpips_std: float = None, per_frame_data: Dict = None,
                             metadata: Dict = None) -> bool:
        """Insert or update video metrics for a run"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT run_id FROM video_metrics WHERE run_id = ?", (run_id,))
                exists = cursor.fetchone() is not None

                if exists:
                    updates = []
                    params = []
                    field_map = {
                        'fvd_score': fvd_score,
                        'video_ssim_mean': video_ssim_mean,
                        'video_ssim_std': video_ssim_std,
                        'video_psnr_mean': video_psnr_mean,
                        'video_psnr_std': video_psnr_std,
                        'video_lpips_mean': video_lpips_mean,
                        'video_lpips_std': video_lpips_std,
                    }
                    for field, value in field_map.items():
                        if value is not None:
                            updates.append(f"{field} = ?")
                            params.append(value)
                    if per_frame_data is not None:
                        updates.append("per_frame_data = ?")
                        params.append(json.dumps(per_frame_data))
                    if metadata is not None:
                        updates.append("metadata = ?")
                        params.append(json.dumps(metadata))
                    if updates:
                        params.append(run_id)
                        query = f"UPDATE video_metrics SET {', '.join(updates)} WHERE run_id = ?"
                        conn.execute(query, params)
                else:
                    conn.execute("""
                        INSERT INTO video_metrics (
                            run_id, timestamp, fvd_score, video_ssim_mean, video_ssim_std,
                            video_psnr_mean, video_psnr_std, video_lpips_mean, video_lpips_std,
                            per_frame_data, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        run_id, timestamp, fvd_score, video_ssim_mean, video_ssim_std,
                        video_psnr_mean, video_psnr_std, video_lpips_mean, video_lpips_std,
                        json.dumps(per_frame_data) if per_frame_data else None,
                        json.dumps(metadata) if metadata else None
                    ))

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error upserting video metrics for run {run_id}: {e}")
            return False

    def get_video_metrics(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get video metrics for a run, or None if not found"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM video_metrics WHERE run_id = ?", (run_id,))
                row = cursor.fetchone()
                if row is None:
                    return None
                result = dict(row)
                # Parse JSON fields
                if result.get('per_frame_data'):
                    result['per_frame_data'] = json.loads(result['per_frame_data'])
                if result.get('metadata'):
                    result['metadata'] = json.loads(result['metadata'])
                return result
        except Exception as e:
            logger.error(f"Error getting video metrics for run {run_id}: {e}")
            return None

    def get_video_runs_without_metrics(self) -> List[Dict[str, Any]]:
        """Get video runs that don't have metrics calculated yet"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT r.* FROM runs r
                    LEFT JOIN video_metrics vm ON r.run_id = vm.run_id
                    WHERE r.generation_type IN ('txt2vid', 'img2vid')
                    AND (vm.run_id IS NULL OR vm.metadata IS NULL OR vm.metadata NOT LIKE '%custom-video-v2%')
                    ORDER BY r.timestamp DESC
                """)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting video runs without metrics: {e}")
            return []

    def save_embedding(self, source_type: str, source_id: str, embedding_type: str,
                       model_name: str, embedding_data: bytes, embedding_dim: int) -> bool:
        """Save an embedding to the cache"""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO embedding_cache
                    (source_type, source_id, embedding_type, model_name, embedding_data, embedding_dim)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (source_type, source_id, embedding_type, model_name, embedding_data, embedding_dim))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error saving embedding: {e}")
            return False

    def get_embedding(self, source_type: str, source_id: str, embedding_type: str,
                      model_name: str) -> Optional[bytes]:
        """Retrieve an embedding from the cache"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT embedding_data FROM embedding_cache
                    WHERE source_type=? AND source_id=? AND embedding_type=? AND model_name=?
                """, (source_type, source_id, embedding_type, model_name))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error retrieving embedding: {e}")
            return None

    def embedding_exists(self, source_type: str, source_id: str, embedding_type: str,
                        model_name: str) -> bool:
        """Check if an embedding exists in the cache"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT 1 FROM embedding_cache
                    WHERE source_type=? AND source_id=? AND embedding_type=? AND model_name=?
                    LIMIT 1
                """, (source_type, source_id, embedding_type, model_name))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking embedding existence: {e}")
            return False

    def insert_run(self, run_data: Dict[str, Any]) -> bool:
        """Insert a single run into the database"""
        try:
            with self.get_connection() as conn:
                # Convert lists/dicts to JSON strings for storage
                processed_data = run_data.copy()
                
                # Handle JSON fields
                json_fields = ['loras', 'controlnets', 'workflow', 'generated_images']
                for field in json_fields:
                    if field in processed_data and processed_data[field] is not None:
                        if not isinstance(processed_data[field], str):
                            processed_data[field] = json.dumps(processed_data[field])
                
                # Insert run
                conn.execute("""
                    INSERT OR REPLACE INTO runs (
                        run_id, timestamp, model, vae, loras, controlnets,
                        prompt, negative_prompt, seed, sampler, steps, cfg_scale,
                        width, height, batch_size, batch_count, workflow,
                        version, generation_type, generated_images
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    processed_data.get('run_id'),
                    processed_data.get('timestamp'),
                    processed_data.get('model'),
                    processed_data.get('vae'),
                    processed_data.get('loras'),
                    processed_data.get('controlnets'),
                    processed_data.get('prompt'),
                    processed_data.get('negative_prompt'),
                    processed_data.get('seed'),
                    processed_data.get('sampler'),
                    processed_data.get('steps'),
                    processed_data.get('cfg_scale'),
                    processed_data.get('width'),
                    processed_data.get('height'),
                    processed_data.get('batch_size'),
                    processed_data.get('batch_count'),
                    processed_data.get('workflow'),
                    processed_data.get('version'),
                    processed_data.get('generation_type'),
                    processed_data.get('generated_images')
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error inserting run {run_data.get('run_id', 'unknown')}: {e}")
            return False
    
    def insert_assets(self, run_id: str, timestamp: str, generated_images: List[str], 
                     output_dir: str = "Dream_Layer_Resources/output") -> bool:
        """Insert assets for a run"""
        try:
            with self.get_connection() as conn:
                for i, filename in enumerate(generated_images):
                    full_path = os.path.join(output_dir, filename)
                    
                    # Get file size if file exists
                    file_size = None
                    if os.path.exists(full_path):
                        file_size = os.path.getsize(full_path)
                    
                    # Create metadata
                    metadata = {
                        "filename": filename,
                        "index": i,
                        "exists": os.path.exists(full_path)
                    }
                    
                    conn.execute("""
                        INSERT OR REPLACE INTO assets (
                            run_id, timestamp, asset_key, asset_value, 
                            full_path, file_size, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        run_id,
                        timestamp,
                        f"generated_image_{i}",
                        filename,
                        full_path,
                        file_size,
                        json.dumps(metadata)
                    ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error inserting assets for run {run_id}: {e}")
            return False
    
    def upsert_metric(self, run_id: str, timestamp: str, clip_score_mean: float = None, 
                     fid_score: float = None, metadata: Dict = None) -> bool:
        """Legacy storage only; new versioned results use research_records."""
        import math
        if any(v is not None and not math.isfinite(v) for v in (clip_score_mean, fid_score)):
            raise ValueError('Metric values must be finite or null')
        try:
            with self.get_connection() as conn:
                # Check if record exists
                cursor = conn.execute("SELECT run_id FROM metrics WHERE run_id = ?", (run_id,))
                exists = cursor.fetchone() is not None
                
                if exists:
                    # Update existing record
                    updates = []
                    params = []
                    
                    if clip_score_mean is not None:
                        updates.append("clip_score_mean = ?")
                        params.append(clip_score_mean)
                    
                    if fid_score is not None:
                        updates.append("fid_score = ?")
                        params.append(fid_score)
                    
                    if metadata is not None:
                        updates.append("metadata = ?")
                        params.append(json.dumps(metadata))
                    
                    if updates:
                        params.append(run_id)
                        query = f"UPDATE metrics SET {', '.join(updates)} WHERE run_id = ?"
                        conn.execute(query, params)
                else:
                    # Insert new record
                    conn.execute("""
                        INSERT INTO metrics (
                            run_id, timestamp, clip_score_mean, fid_score, metadata
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (
                        run_id,
                        timestamp,
                        clip_score_mean,
                        fid_score,
                        json.dumps(metadata) if metadata else None
                    ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error upserting metrics for run {run_id}: {e}")
            return False
    
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get a single run by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"Error getting run {run_id}: {e}")
            return None
    
    def get_run_assets(self, run_id: str) -> List[Dict[str, Any]]:
        """Get all assets for a run"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM assets WHERE run_id = ? ORDER BY asset_key
                """, (run_id,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error getting assets for run {run_id}: {e}")
            return []
    
    def get_run_metrics(self, run_id: str) -> Dict[str, Any]:
        """Get metrics for a run as a dictionary"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT clip_score_mean, fid_score FROM metrics WHERE run_id = ?
                """, (run_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'clip_score_mean': row['clip_score_mean'],
                        'fid_score': None, 'legacy_fid_score': row['fid_score'], 'fid_status': 'invalid_legacy_result' if row['fid_score'] is not None else 'not_applicable'
                    }
                return {'clip_score_mean': None, 'fid_score': None}
                
        except Exception as e:
            logger.error(f"Error getting metrics for run {run_id}: {e}")
            return {'clip_score_mean': None, 'fid_score': None}
    
    def get_all_runs(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get all runs, optionally limited"""
        try:
            with self.get_connection() as conn:
                query = "SELECT * FROM runs ORDER BY timestamp DESC"
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor = conn.execute(query)
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Error getting all runs: {e}")
            return []
    
    def get_runs_with_metrics(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get runs with their metrics aggregated"""
        try:
            with self.get_connection() as conn:
                query = """
                    SELECT 
                        r.*,
                        m.clip_score_mean,
                        m.fid_score
                    FROM runs r
                    LEFT JOIN metrics m ON r.run_id = m.run_id
                    ORDER BY r.timestamp DESC
                """
                
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor = conn.execute(query)
                results = []
                
                for row in cursor.fetchall():
                    run_data = dict(row)
                    
                    # Create metrics dictionary
                    run_data['metrics'] = {
                        'clip_score_mean': run_data.pop('clip_score_mean', None),
                        'fid_score': None, 'legacy_fid_score': run_data.pop('fid_score', None), 'fid_status': 'invalid_legacy_result'
                    }
                    
                    results.append(run_data)
                
                return results
                
        except Exception as e:
            logger.error(f"Error getting runs with metrics: {e}")
            return []
    
    def upsert_composition_metrics(self, run_id: str, timestamp: str, prompt_text: str, 
                                 image_path: str, metrics: Dict[str, Any]) -> bool:
        """Insert or update composition metrics for a run"""
        try:
            if 'object_criteria_result' in metrics:
                from research.legacy import save_composition
                return save_composition(self.db_path, run_id, prompt_text, image_path, metrics)
            with self.get_connection() as conn:
                # Check if record exists
                cursor = conn.execute("SELECT run_id FROM composition_metrics WHERE run_id = ?", (run_id,))
                exists = cursor.fetchone() is not None
                
                if exists:
                    # Update existing record
                    conn.execute("""
                        UPDATE composition_metrics SET
                            prompt_text = ?,
                            image_path = ?,
                            macro_precision = ?,
                            macro_recall = ?,
                            macro_f1 = ?,
                            per_class_metrics = ?,
                            detected_objects = ?,
                            missing_objects = ?,
                            timestamp = ?
                        WHERE run_id = ?
                    """, (
                        prompt_text,
                        image_path,
                        metrics.get('macro_precision'),
                        metrics.get('macro_recall'),
                        metrics.get('macro_f1'),
                        json.dumps(metrics.get('per_class_metrics', {})),
                        json.dumps(metrics.get('detected_objects', {})),
                        json.dumps(metrics.get('missing_objects', {})),
                        timestamp,
                        run_id
                    ))
                else:
                    # Insert new record
                    conn.execute("""
                        INSERT INTO composition_metrics (
                            run_id, prompt_text, image_path, macro_precision, macro_recall, macro_f1,
                            per_class_metrics, detected_objects, missing_objects, timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        run_id,
                        prompt_text,
                        image_path,
                        metrics.get('macro_precision'),
                        metrics.get('macro_recall'),
                        metrics.get('macro_f1'),
                        json.dumps(metrics.get('per_class_metrics', {})),
                        json.dumps(metrics.get('detected_objects', {})),
                        json.dumps(metrics.get('missing_objects', {})),
                        timestamp
                    ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error upserting composition metrics for run {run_id}: {e}")
            return False
    
    def get_composition_metrics(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get composition metrics for a run"""
        try:
            with self.get_connection() as conn:
                from research.legacy import composition
                corrected = composition(conn, run_id)
                if corrected is not None:
                    return corrected
                cursor = conn.execute("""
                    SELECT * FROM composition_metrics WHERE run_id = ?
                """, (run_id,))
                
                row = cursor.fetchone()
                if row:
                    metrics = dict(row)
                    # Parse JSON fields
                    for field in ['per_class_metrics', 'detected_objects', 'missing_objects']:
                        if metrics.get(field):
                            try:
                                metrics[field] = json.loads(metrics[field])
                            except (json.JSONDecodeError, TypeError):
                                metrics[field] = {}
                    return metrics
                return None
                
        except Exception as e:
            logger.error(f"Error getting composition metrics for run {run_id}: {e}")
            return None

# Convenience function for getting database instance
def get_database() -> DreamLayerDB:
    """Get a database instance"""
    return DreamLayerDB()

if __name__ == "__main__":
    # Test database creation
    db = DreamLayerDB()
    print(f"Database created at: {db.db_path}")
    print("Schema created successfully!")
