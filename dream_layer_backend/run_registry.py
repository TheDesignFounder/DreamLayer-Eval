import sys as _research_sys
from pathlib import Path as _ResearchPath
_research_sys.path.insert(0, str(_ResearchPath(__file__).resolve().parent.parent))
"""
Enhanced Run Registry with Database Integration
Saves new runs to database while maintaining API compatibility
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import database integration
try:
    from database_integration import db_integration
    DATABASE_ENABLED = True
    print("✅ Database integration enabled")
except ImportError as e:
    DATABASE_ENABLED = False
    print(f"⚠️ Database integration not available: {e}")

@dataclass
class RunConfig:
    """Configuration for a completed generation run"""
    run_id: str
    timestamp: str
    model: str
    vae: Optional[str] = None
    loras: Optional[List[str]] = None
    controlnets: List[str] = None
    prompt: str = ""
    negative_prompt: str = ""
    seed: int = 0
    sampler: str = "euler"
    steps: int = 20
    cfg_scale: float = 7.0
    width: int = 512
    height: int = 512
    batch_size: int = 1
    batch_count: int = 1
    workflow: Dict[str, Any] = None
    version: str = "1.0.0"
    generated_images: List[str] = None
    generation_type: str = "txt2img"
    
    def __post_init__(self):
        if self.loras is None:
            self.loras = []
        if self.controlnets is None:
            self.controlnets = []
        if self.workflow is None:
            self.workflow = {}
        if self.generated_images is None:
            self.generated_images = []

class RunRegistry:
    """Registry for managing completed generation runs with database integration"""
    
    def __init__(self, registry_file: str = "run_registry.json"):
        self.registry_file = registry_file
        self.runs: Dict[str, RunConfig] = {}
        self.load_runs()
    
    def load_runs(self):
        """Load existing runs from JSON file"""
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for run_id, run_data in data.items():
                    self.runs[run_id] = RunConfig(**run_data)
                    
                print(f"Loaded {len(self.runs)} runs from {self.registry_file}")
            except Exception as e:
                print(f"Error loading runs: {e}")
                self.runs = {}
        else:
            print(f"Registry file {self.registry_file} not found, starting fresh")
    
    def save_runs(self):
        """Save runs to JSON file (legacy compatibility)"""
        try:
            data = {}
            for run_id, run_config in self.runs.items():
                data[run_id] = asdict(run_config)
            
            with open(self.registry_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            print(f"Saved {len(self.runs)} runs to {self.registry_file}")
        except Exception as e:
            print(f"Error saving runs: {e}")
    
    def add_run(self, run_config: RunConfig):
        """Add a new run to both database and JSON (hybrid approach)"""
        
        # 1. Save to database (primary)
        if DATABASE_ENABLED and db_integration.is_database_enabled():
            try:
                # Convert RunConfig to dict for database
                run_data = asdict(run_config)
                
                # Save run to database
                success = db_integration.queries.db.insert_run(run_data)
                if success:
                    print(f"✅ Saved run {run_config.run_id} to database")
                    
                    # Save assets to database
                    if run_config.generated_images:
                        asset_success = db_integration.queries.db.insert_assets(
                            run_config.run_id,
                            run_config.timestamp,
                            run_config.generated_images
                        )
                        if asset_success:
                            print(f"✅ Saved {len(run_config.generated_images)} assets to database")
                        else:
                            print(f"⚠️ Failed to save assets to database")
                else:
                    print(f"⚠️ Failed to save run to database")
                    
            except Exception as e:
                print(f"⚠️ Database save error: {e}")
        
        # 2. Also save to JSON (for transition period/backup)
        try:
            self.runs[run_config.run_id] = run_config
            self.save_runs()
            print(f"✅ Also saved run {run_config.run_id} to JSON (backup)")
        except Exception as e:
            print(f"⚠️ JSON save error: {e}")
    
    def get_run(self, run_id: str) -> Optional[RunConfig]:
        """Get a specific run by ID"""
        return self.runs.get(run_id)
    
    def get_all_runs(self) -> List[RunConfig]:
        """Get all runs"""
        return list(self.runs.values())
    
    def delete_run(self, run_id: str) -> bool:
        """Delete a run"""
        if run_id in self.runs:
            del self.runs[run_id]
            self.save_runs()
            return True
        return False

def create_run_config_from_generation_data(generation_data: Dict[str, Any], 
                                         generated_images: List[str], 
                                         generation_type: str) -> RunConfig:
    """Create a RunConfig from generation data"""
    
    return RunConfig(
        run_id=str(uuid.uuid4()),
        timestamp=datetime.now().isoformat(),
        model=generation_data.get('model_name', 'unknown'),
        vae=generation_data.get('vae'),
        loras=generation_data.get('loras', []),
        controlnets=generation_data.get('controlnets', []),
        prompt=generation_data.get('prompt', ''),
        negative_prompt=generation_data.get('negative_prompt', ''),
        seed=generation_data.get('seed', 0),
        sampler=generation_data.get('sampler', 'euler'),
        steps=generation_data.get('steps', 20),
        cfg_scale=generation_data.get('cfg_scale', 7.0),
        width=generation_data.get('width', 512),
        height=generation_data.get('height', 512),
        batch_size=generation_data.get('batch_size', 1),
        batch_count=generation_data.get('batch_count', 1),
        workflow=generation_data.get('workflow', {}),
        version="1.0.0",
        generated_images=generated_images,
        generation_type=generation_type
    )

# Initialize registry
registry = RunRegistry()

# Flask app
app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:*", "http://127.0.0.1:*"],
        "methods": ["GET", "POST", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/api/runs', methods=['GET'])
def get_runs():
    """Get all completed runs from database (not JSON)"""
    try:
        # Read from database instead of JSON registry
        from dream_layer_backend_utils.unified_database_queries import get_all_runs_with_metrics
        
        runs = get_all_runs_with_metrics()
        
        return jsonify({
            "status": "success",
            "runs": runs,
            "source": "database",
            "count": len(runs)
        })
    except Exception as e:
        # Fallback to JSON registry only if database fails
        try:
            runs = registry.get_all_runs()
            return jsonify({
                "status": "success",
                "runs": [asdict(run) for run in runs],
                "source": "json_fallback",
                "count": len(runs)
            })
        except Exception as fallback_error:
            return jsonify({
                "status": "error",
                "message": f"Database error: {str(e)}, Fallback error: {str(fallback_error)}"
            }), 500

@app.route('/api/runs/<run_id>', methods=['GET'])
def get_run(run_id: str):
    """Get a specific run by ID from database (not JSON)"""
    try:
        # Read from database instead of JSON registry
        from dream_layer_backend_utils.unified_database_queries import get_single_run_with_clipscore
        
        run = get_single_run_with_clipscore(run_id)
        
        if run:
            return jsonify({
                "status": "success",
                "run": run,
                "source": "database"
            })
        else:
            # Fallback to JSON registry if not found in database
            json_run = registry.get_run(run_id)
            if json_run:
                return jsonify({
                    "status": "success",
                    "run": asdict(json_run),
                    "source": "json_fallback"
                })
            else:
                return jsonify({
                    "status": "error",
                    "message": "Run not found"
                }), 404
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/runs', methods=['POST'])
def add_run():
    """Add a new completed run - Enhanced with database integration"""
    try:
        data = request.json
        if not data:
            return jsonify({
                "status": "error",
                "message": "No data provided"
            }), 400
        
        # Create run config from the provided data
        run_config = RunConfig(
            run_id=data.get('run_id', str(uuid.uuid4())),
            timestamp=data.get('timestamp', datetime.now().isoformat()),
            model=data.get('model', 'unknown'),
            vae=data.get('vae'),
            loras=data.get('loras', []),
            controlnets=data.get('controlnets', []),
            prompt=data.get('prompt', ''),
            negative_prompt=data.get('negative_prompt', ''),
            seed=data.get('seed', 0),
            sampler=data.get('sampler', 'euler'),
            steps=data.get('steps', 20),
            cfg_scale=data.get('cfg_scale', 7.0),
            width=data.get('width', 512),
            height=data.get('height', 512),
            batch_size=data.get('batch_size', 1),
            batch_count=data.get('batch_count', 1),
            workflow=data.get('workflow', {}),
            version=data.get('version', '1.0.0'),
            generated_images=data.get('generated_images', []),
            generation_type=data.get('generation_type', 'txt2img')
        )
        
        # Save to both database and JSON
        registry.add_run(run_config)
        
        # All metrics will be calculated on-demand when accessing Run Registry or Report Bundle
        logger.info(f"Run {run_config.run_id} registered successfully. Metrics will be calculated on-demand.")
        
        return jsonify({
            "status": "success",
            "run_id": run_config.run_id,
            "message": "Run added successfully to database and JSON",
            "database_enabled": DATABASE_ENABLED
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/runs/<run_id>', methods=['DELETE'])
def delete_run(run_id: str):
    """Delete a run"""
    try:
        success = registry.delete_run(run_id)
        if success:
            return jsonify({
                "status": "success",
                "message": "Run deleted successfully"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Run not found"
            }), 404
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/database/stats', methods=['GET'])

# Enhanced API endpoints using unified database queries
@app.route('/api/runs/enhanced', methods=['GET'])
def get_runs_enhanced():
    """Get all completed runs with ClipScore data (v1)"""
    try:
        from dream_layer_backend_utils.unified_database_queries import get_all_runs_with_clipscore
        
        enhanced_runs = get_all_runs_with_clipscore()
        
        return jsonify({
            "status": "success",
            "runs": enhanced_runs,
            "database_enabled": DATABASE_ENABLED,
            "count": len(enhanced_runs)
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/runs/enhanced/v2', methods=['GET'])
def get_runs_enhanced_v2():
    """Get all completed runs with all metrics (ClipScore, FiD, Composition) - v2 unified queries"""
    try:
        from dream_layer_backend_utils.unified_database_queries import get_all_runs_with_metrics
        from data.scripts.queries import DreamLayerQueries
        
        # Get existing data immediately
        enhanced_runs = get_all_runs_with_metrics()
        
        # Count pending metrics
        queries = DreamLayerQueries()
        pending_counts = {
            "clip": len(queries.get_runs_without_clip_score()),
            "fid": len(queries.get_runs_without_fid_score()),
            "composition": len(queries.get_runs_without_composition_metrics())
        }
        
        return jsonify({
            "status": "success",
            "runs": enhanced_runs,
            "pending_metrics": pending_counts,
            "database_enabled": DATABASE_ENABLED,
            "enhancement_available": True,
            "count": len(enhanced_runs),
            "metrics_included": ["clip_score_mean", "fid_score", "macro_precision", "macro_recall", "macro_f1"],
            "version": "v2"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/runs/calculate-metrics', methods=['POST'])
def calculate_metrics_background():
    """Trigger background metrics calculation with WebSocket updates"""
    try:
        from database_integration import ensure_clip_scores_calculated_with_progress, ensure_fid_scores_calculated_with_progress, ensure_composition_metrics_calculated_with_progress
        
        # Start calculations with WebSocket progress updates
        ensure_clip_scores_calculated_with_progress()
        ensure_fid_scores_calculated_with_progress()
        ensure_composition_metrics_calculated_with_progress()
        
        return jsonify({"status": "completed"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/runs/<run_id>/enhanced', methods=['GET'])
def get_run_enhanced(run_id: str):
    """Get a specific run by ID with ClipScore data (v1)"""
    try:
        from dream_layer_backend_utils.unified_database_queries import get_single_run_with_clipscore
        
        enhanced_run = get_single_run_with_clipscore(run_id)
        
        if enhanced_run:
            return jsonify({
                "status": "success",
                "run": enhanced_run,
                "database_enabled": DATABASE_ENABLED
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Run not found"
            }), 404
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/runs/<run_id>/enhanced/v2', methods=['GET'])
def get_run_enhanced_v2(run_id: str):
    """Get a specific run by ID with all metrics (ClipScore, FiD, etc.) - v2 unified queries"""
    try:
        from dream_layer_backend_utils.unified_database_queries import get_single_run_with_metrics
        
        enhanced_run = get_single_run_with_metrics(run_id)
        
        if enhanced_run:
            return jsonify({
                "status": "success",
                "run": enhanced_run,
                "database_enabled": DATABASE_ENABLED,
                "enhancement_available": True,
                "metrics_included": ["clip_score_mean", "fid_score"],
                "version": "v2"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Run not found"
            }), 404
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/runs/enhanced/metrics', methods=['GET'])
def get_runs_enhanced_metrics():
    """Get all completed runs with all metrics (ClipScore and FiD)"""
    try:
        from dream_layer_backend_utils.unified_database_queries import get_all_runs_with_metrics
        
        enhanced_runs = get_all_runs_with_metrics()
        
        return jsonify({
            "status": "success",
            "runs": enhanced_runs,
            "database_enabled": DATABASE_ENABLED,
            "enhancement_available": True,
            "count": len(enhanced_runs),
            "metrics_included": ["clip_score_mean", "fid_score"],
            "version": "metrics"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/runs/<run_id>/enhanced/metrics', methods=['GET'])
def get_run_enhanced_metrics(run_id: str):
    """Get a specific run by ID with all metrics (ClipScore and FiD)"""
    try:
        from dream_layer_backend_utils.unified_database_queries import get_single_run_with_metrics
        
        enhanced_run = get_single_run_with_metrics(run_id)
        
        if enhanced_run:
            return jsonify({
                "status": "success",
                "run": enhanced_run,
                "database_enabled": DATABASE_ENABLED,
                "enhancement_available": True,
                "metrics_included": ["clip_score_mean", "fid_score"],
                "version": "metrics"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Run not found"
            }), 404
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    print("🚀 Starting Enhanced Run Registry with Database Integration")
    print(f"📊 Database enabled: {DATABASE_ENABLED}")
    
    socketio.run(app, host='0.0.0.0', port=5005, debug=True, allow_unsafe_werkzeug=True)

@app.route('/api/database/stats', methods=['GET'])
def get_database_stats():
    """Get database statistics and status"""
    try:
        from dream_layer_backend_utils.unified_database_queries import get_database_stats
        
        stats = get_database_stats()
        
        # Add JSON registry stats for comparison
        json_count = len(registry.get_all_runs()) if registry else 0
        
        return jsonify({
            "status": "success",
            "database_stats": stats,
            "json_registry_count": json_count,
            "primary_source": "database",
            "fallback_source": "json_registry"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
