import sys as _research_sys
from pathlib import Path as _ResearchPath
_research_sys.path.insert(0, str(_ResearchPath(__file__).resolve().parent.parent))
"""
History API Server
Provides REST API endpoints for generation history management
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import generation_history as gh

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:*", "http://127.0.0.1:*"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})


@app.route('/api/history/save', methods=['POST', 'OPTIONS'])
def save_generation():
    """Save a generation to history"""
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"})

    try:
        data = request.json

        # Validate required fields
        required_fields = ['id', 'type', 'filename', 'file_path', 'url']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    "status": "error",
                    "message": f"Missing required field: {field}"
                }), 400

        success = gh.save_generation(data)

        if success:
            return jsonify({
                "status": "success",
                "message": "Generation saved successfully"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to save generation"
            }), 500

    except Exception as e:
        print(f"[History API] Error in save_generation: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/history/<gen_type>', methods=['GET'])
def get_generations(gen_type):
    """
    Get generations by type

    Query params:
        - limit: Maximum number of results (default: 100)
    """
    try:
        limit = int(request.args.get('limit', 100))

        # Validate gen_type
        valid_types = ['txt2img', 'img2img', 'txt2vid', 'img2vid', 'img2txt', 'extras', 'all']
        if gen_type not in valid_types:
            return jsonify({
                "status": "error",
                "message": f"Invalid type. Must be one of: {', '.join(valid_types)}"
            }), 400

        # Get generations
        if gen_type == 'all':
            generations = gh.get_generations(gen_type=None, limit=limit)
        else:
            generations = gh.get_generations(gen_type=gen_type, limit=limit)

        return jsonify({
            "status": "success",
            "count": len(generations),
            "generations": generations
        })

    except Exception as e:
        print(f"[History API] Error in get_generations: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/history/<generation_id>/delete', methods=['DELETE', 'OPTIONS'])
def delete_generation(generation_id):
    """Delete a generation"""
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"})

    try:
        # Check if we should delete the file too
        delete_file = request.args.get('delete_file', 'true').lower() == 'true'

        success = gh.delete_generation(generation_id, delete_file=delete_file)

        if success:
            return jsonify({
                "status": "success",
                "message": "Generation deleted successfully"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Generation not found or could not be deleted"
            }), 404

    except Exception as e:
        print(f"[History API] Error in delete_generation: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/history/<generation_id>/download', methods=['POST', 'OPTIONS'])
def mark_downloaded(generation_id):
    """Mark a generation as downloaded"""
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"})

    try:
        success = gh.mark_downloaded(generation_id)

        if success:
            return jsonify({
                "status": "success",
                "message": "Marked as downloaded"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to mark as downloaded"
            }), 500

    except Exception as e:
        print(f"[History API] Error in mark_downloaded: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/history/<generation_id>/favorite', methods=['POST', 'OPTIONS'])
def toggle_favorite(generation_id):
    """Toggle favorite status of a generation"""
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"})

    try:
        data = request.json or {}
        favorited = data.get('favorited', True)

        success = gh.mark_favorited(generation_id, favorited=favorited)

        if success:
            return jsonify({
                "status": "success",
                "message": f"Marked as {'favorited' if favorited else 'unfavorited'}"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to update favorite status"
            }), 500

    except Exception as e:
        print(f"[History API] Error in toggle_favorite: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/history/cleanup', methods=['POST', 'OPTIONS'])
def cleanup():
    """
    Manually trigger cleanup

    Body params:
        - image_retention_days: Days to keep images (default: 7)
        - video_retention_days: Days to keep videos (default: 2)
        - delete_files: Whether to delete files (default: true)
    """
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"})

    try:
        data = request.json or {}

        image_retention_days = data.get('image_retention_days', 7)
        video_retention_days = data.get('video_retention_days', 2)
        delete_files = data.get('delete_files', True)

        stats = gh.cleanup_old_generations(
            image_retention_days=image_retention_days,
            video_retention_days=video_retention_days,
            delete_files=delete_files
        )

        return jsonify({
            "status": "success",
            "message": "Cleanup completed",
            "stats": stats
        })

    except Exception as e:
        print(f"[History API] Error in cleanup: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/history/stats', methods=['GET'])
def get_stats():
    """Get storage statistics"""
    try:
        stats = gh.get_storage_stats()

        return jsonify({
            "status": "success",
            "stats": stats
        })

    except Exception as e:
        print(f"[History API] Error in get_stats: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/history/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "service": "history_server",
        "database": "connected"
    })


if __name__ == '__main__':
    print("\n" + "="*60)
    print("Starting Generation History Server...")
    print("="*60)
    print("Available endpoints:")
    print("  - POST   /api/history/save")
    print("  - GET    /api/history/<type>")
    print("  - DELETE /api/history/<id>/delete")
    print("  - POST   /api/history/<id>/download")
    print("  - POST   /api/history/<id>/favorite")
    print("  - POST   /api/history/cleanup")
    print("  - GET    /api/history/stats")
    print("  - GET    /api/history/health")
    print("="*60)
    print("Server running at http://localhost:5009")
    print("="*60 + "\n")

    app.run(debug=True, host='127.0.0.1', port=5009)
