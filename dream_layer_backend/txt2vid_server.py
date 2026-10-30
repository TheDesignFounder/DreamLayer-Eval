import sys as _research_sys
from pathlib import Path as _ResearchPath
_research_sys.path.insert(0, str(_ResearchPath(__file__).resolve().parent.parent))
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import os
import logging
import base64
import uuid
from dream_layer import get_directories
from dream_layer_backend_utils.native_dream_layer_workflows.txt2vid.luma_api import generate_luma_video
from dream_layer_backend_utils.native_dream_layer_workflows.txt2vid.runway_api import generate_runway_video
import generation_history as gh
from run_registry import create_run_config_from_generation_data, registry

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:*", "http://127.0.0.1:*"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Setup logging
logs_dir = os.getenv('DREAMLAYER_LOG_DIR', os.path.join(os.path.dirname(__file__), '..', 'logs'))
os.makedirs(logs_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(logs_dir, 'txt2vid_server.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='a'
)

output_dir, _ = get_directories()
VIDEO_OUTPUT_DIR = os.getenv('DREAMLAYER_VIDEO_OUTPUT_DIR', os.path.join(output_dir, 'videos'))
os.makedirs(VIDEO_OUTPUT_DIR, exist_ok=True)

# Create temp directory for image-to-video input images
TEMP_IMAGES_DIR = os.getenv('DREAMLAYER_TEMP_IMAGES_DIR', os.path.join(output_dir, 'temp_images'))
os.makedirs(TEMP_IMAGES_DIR, exist_ok=True)

@app.route('/api/txt2vid', methods=['POST', 'OPTIONS'])
def handle_txt2vid():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"})

    try:
        data = request.json
        logging.info(f"Received txt2vid request: {json.dumps(data, indent=2)}")

        if not data or 'prompt' not in data:
            logging.error("Missing prompt in request")
            return jsonify({"status": "error", "message": "Missing prompt"}), 400

        provider = data.get('provider', data.get('model', 'luma')).lower()
        logging.info(f"Using provider: {provider}")

        if provider == 'luma':
            luma_model = data.get('luma_model', 'ray-2')
            logging.info(f"Using Luma model: {luma_model}")

            # Luma doesn't support img2vid (requires publicly accessible CDN URL)
            if data.get('input_image'):
                logging.error("Luma AI does not support image-to-video (requires CDN URL)")
                return jsonify({
                    "status": "error",
                    "message": "Luma AI does not support image-to-video. Please use Runway ML for img2vid generation."
                }), 400

            result = generate_luma_video(
                prompt=data['prompt'],
                output_dir=VIDEO_OUTPUT_DIR,
                model=luma_model,
                aspect_ratio=data.get('aspect_ratio', '16:9'),
                loop=data.get('loop', True),
                resolution=data.get('resolution'),
                duration=data.get('duration')
            )
        elif provider == 'runway':
            runway_model = data.get('runway_model', 'veo3')
            runway_mode = data.get('runway_mode', 'text2vid')
            logging.info(f"Using Runway model: {runway_model}, mode: {runway_mode}")
            result = generate_runway_video(
                prompt=data.get('prompt', ''),
                output_dir=VIDEO_OUTPUT_DIR,
                model=runway_model,
                ratio=data.get('ratio', '1280:720'),
                duration=data.get('duration', 4),
                seed=data.get('seed'),
                audio=data.get('audio', False),  # Default to False to save credits
                mode=runway_mode,
                input_image=data.get('input_image')  # Base64 image for img2vid
            )
        else:
            logging.error(f"Unsupported provider: {provider}")
            return jsonify({"status": "error", "message": f"Unsupported provider: {provider}"}), 400

        logging.info(f"Generation result: {result}")

        if "error" in result:
            logging.error(f"Generation failed: {result['error']}")
            return jsonify({"status": "error", "message": result["error"]}), 500

        # Save to history database
        # Determine generation type based on provider and input image
        if provider == 'runway':
            generation_type = data.get('runway_mode', 'text2vid')
        elif provider == 'luma':
            # Luma: img2vid if input_image present, otherwise txt2vid
            generation_type = 'img2vid' if data.get('input_image') else 'txt2vid'
        else:
            generation_type = 'txt2vid'

        if generation_type not in ['txt2vid', 'img2vid']:
            generation_type = 'txt2vid'  # Default to txt2vid

        video_url = f"http://localhost:5008/api/videos/{result['filename']}"
        history_data = {
            'id': result['filename'],
            'type': generation_type,
            'filename': result['filename'],
            'file_path': result['file'],
            'url': video_url,
            'prompt': data.get('prompt', ''),
            'settings': data  # Save all request settings
        }

        try:
            gh.save_generation(history_data)
            logging.info(f"Saved to history: {result['filename']}")
        except Exception as e:
            logging.error(f"Failed to save to history: {str(e)}")
            # Don't fail the request if history save fails

        # Register in run registry for metrics tracking
        generated_run_id = None
        try:
            run_config = create_run_config_from_generation_data(
                data,
                [result['filename']],
                generation_type
            )
            registry.add_run(run_config)
            generated_run_id = run_config.run_id
            logging.info(f"✅ Video run registered with run_id: {generated_run_id}")
        except Exception as e:
            logging.error(f"Failed to register video run: {str(e)}")
            # Don't fail the request if registry fails

        response = {
            "status": "success",
            "message": "Video generated successfully",
            "filename": result["filename"],
            "run_id": generated_run_id
        }
        logging.info(f"Returning success response: {response}")
        return jsonify(response)

    except Exception as e:
        logging.error(f"Error in handle_txt2vid: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/videos/<filename>', methods=['GET'])
def serve_video(filename):
    try:
        logging.info(f"Serving video: {filename}")
        file_path = os.path.join(VIDEO_OUTPUT_DIR, filename)
        if os.path.exists(file_path):
            return send_file(file_path, mimetype='video/mp4')
        logging.error(f"Video not found: {filename}")
        return jsonify({"error": "Video not found"}), 404
    except Exception as e:
        logging.error(f"Error serving video {filename}: {str(e)}")
        return jsonify({"error": str(e)}), 404

@app.route('/api/temp-images/<filename>', methods=['GET'])
def serve_temp_image(filename):
    """Serve temporary images for Luma img2vid (CDN URL requirement)"""
    try:
        logging.info(f"Serving temp image: {filename}")
        file_path = os.path.join(TEMP_IMAGES_DIR, filename)
        if os.path.exists(file_path):
            return send_file(file_path, mimetype='image/png')
        logging.error(f"Temp image not found: {filename}")
        return jsonify({"error": "Image not found"}), 404
    except Exception as e:
        logging.error(f"Error serving temp image {filename}: {str(e)}")
        return jsonify({"error": str(e)}), 404

@app.route('/api/open-videos-folder', methods=['POST', 'OPTIONS'])
def open_videos_folder():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"})

    try:
        import platform
        import subprocess

        logging.info(f"Opening videos folder: {VIDEO_OUTPUT_DIR}")

        system = platform.system()
        if system == 'Darwin':  # macOS
            subprocess.run(['open', VIDEO_OUTPUT_DIR])
        elif system == 'Windows':
            subprocess.run(['explorer', VIDEO_OUTPUT_DIR])
        elif system == 'Linux':
            subprocess.run(['xdg-open', VIDEO_OUTPUT_DIR])

        return jsonify({"status": "success", "message": f"Opened folder: {VIDEO_OUTPUT_DIR}"})
    except Exception as e:
        logging.error(f"Error opening videos folder: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/available-providers', methods=['GET'])
def get_available_providers():
    """Check which video providers have API keys configured"""
    try:
        from dotenv import load_dotenv
        load_dotenv()

        providers = {
            'luma': bool(os.getenv('LUMA_API_KEY')),
            'runway': bool(os.getenv('RUNWAY_API_KEY'))
        }

        logging.info(f"Available providers: {providers}")
        return jsonify({
            "status": "success",
            "providers": providers
        })
    except Exception as e:
        logging.error(f"Error checking available providers: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/calculate-video-metrics', methods=['POST', 'OPTIONS'])
def calculate_video_metrics():
    """Calculate evaluation metrics for a generated video."""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response

    try:
        data = request.json
        video_url = data.get('video_url', '')
        reference_video_url = data.get('reference_video_url', '')
        prompt = data.get('prompt', '')
        run_id = data.get('run_id', '')
        force_recalculate = data.get('force_recalculate', False)

        if not video_url:
            return jsonify({"status": "error", "message": "Missing video_url"}), 400

        # Check DB cache first
        if False:  # Legacy run-only cache has no content/preprocessing identity; research cache is authoritative.
            try:
                from data.scripts.database import DreamLayerDB
                db = DreamLayerDB()
                cached = db.get_video_metrics(run_id)
                if cached:
                    # Reconstruct full metrics dict from DB row
                    metrics = {}
                    for key in ['fvd_score', 'video_ssim_mean', 'video_ssim_std',
                                'video_psnr_mean', 'video_psnr_std',
                                'video_lpips_mean', 'video_lpips_std']:
                        if cached.get(key) is not None:
                            metrics[key] = cached[key]
                    # Phase 2 quality metrics + per-frame data stored in metadata
                    if cached.get('metadata'):
                        metrics.update(cached['metadata'])
                    if cached.get('per_frame_data'):
                        metrics.update(cached['per_frame_data'])
                    metrics['computed_at'] = cached.get('computed_at', '')
                    metrics['_cached'] = True
                    logging.info(f"Returning cached video metrics for run_id: {run_id}")
                    return jsonify({"status": "success", "metrics": metrics})
            except Exception as e:
                logging.warning(f"DB cache lookup failed, computing fresh: {e}")

        # Resolve filename to full path
        video_filename = video_url.split('/')[-1] if '/' in video_url else video_url
        video_path = os.path.join(VIDEO_OUTPUT_DIR, video_filename)

        if not os.path.exists(video_path):
            return jsonify({"status": "error", "message": f"Video not found: {video_filename}"}), 404

        reference_path = None
        if reference_video_url:
            ref_filename = reference_video_url.split('/')[-1] if '/' in reference_video_url else reference_video_url
            ref_path = os.path.join(VIDEO_OUTPUT_DIR, ref_filename)
            if os.path.exists(ref_path):
                reference_path = ref_path

        logging.info(f"Calculating video metrics for: {video_filename}")

        from dream_layer_backend_utils.video_metrics import get_video_calculator
        calculator = get_video_calculator()
        metrics = calculator.compute_all(
            video_path=video_path,
            reference_path=reference_path,
            per_frame=True, alignment=data.get('alignment')
        )

        from datetime import datetime
        metrics['computed_at'] = datetime.now().isoformat()

        # Save to DB if we have a run_id
        if run_id:
            try:
                from data.scripts.database import DreamLayerDB
                db = DreamLayerDB()
                # Separate per-frame data and quality metrics into JSON columns
                per_frame_data = {}
                metadata = {}
                phase1_keys = {'fvd_score', 'video_ssim_mean', 'video_ssim_std',
                               'video_psnr_mean', 'video_psnr_std',
                               'video_lpips_mean', 'video_lpips_std'}
                skip_keys = {'computed_at', '_errors', '_cached'}
                per_frame_keys = {k for k in metrics if 'per_frame' in k}

                for k, v in metrics.items():
                    if k in phase1_keys or k in skip_keys:
                        continue
                    elif k in per_frame_keys:
                        per_frame_data[k] = v
                    else:
                        metadata[k] = v

                db.upsert_video_metrics(
                    run_id=run_id,
                    timestamp=datetime.now().isoformat(),
                    fvd_score=metrics.get('fvd_score'),
                    video_ssim_mean=metrics.get('video_ssim_mean'),
                    video_ssim_std=metrics.get('video_ssim_std'),
                    video_psnr_mean=metrics.get('video_psnr_mean'),
                    video_psnr_std=metrics.get('video_psnr_std'),
                    video_lpips_mean=metrics.get('video_lpips_mean'),
                    video_lpips_std=metrics.get('video_lpips_std'),
                    per_frame_data=per_frame_data if per_frame_data else None,
                    metadata=metadata if metadata else None,
                )
                logging.info(f"Video metrics saved to DB for run_id: {run_id}")
            except Exception as e:
                logging.error(f"Failed to save video metrics to DB: {e}")

        logging.info(f"Video metrics computed: {list(k for k in metrics.keys() if not k.startswith('video_') or 'per_frame' not in k)}")

        return jsonify({
            "status": "success",
            "metrics": metrics
        })

    except Exception as e:
        logging.error(f"Error calculating video metrics: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/video-metrics-cache/<filename>', methods=['GET'])
def get_video_metrics_cache(filename):
    return jsonify({'status':'not_found','reason':'Legacy filename cache invalidated; recompute with content identity'}), 404


@app.route('/api/calculate-all-video-metrics', methods=['POST', 'OPTIONS'])
def calculate_all_video_metrics():
    """Batch calculate video metrics for all unscored video runs."""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response

    try:
        from database_integration import ensure_video_metrics_calculated_with_progress
        stats = ensure_video_metrics_calculated_with_progress()
        return jsonify({"status": "success", "stats": stats})
    except Exception as e:
        logging.error(f"Error in batch video metrics: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/export-video-metrics', methods=['GET'])
def export_video_metrics():
    """Export all video metrics as CSV."""
    try:
        import csv
        import io
        from data.scripts.database import DreamLayerDB

        db = DreamLayerDB()
        with db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT r.run_id, r.timestamp, r.model, r.prompt, r.generation_type,
                       r.generated_images,
                       vm.fvd_score AS legacy_fvd_score, NULL AS fvd_score, vm.video_ssim_mean, vm.video_ssim_std,
                       vm.video_psnr_mean, vm.video_psnr_std,
                       vm.video_lpips_mean, vm.video_lpips_std,
                       vm.metadata, vm.computed_at
                FROM video_metrics vm
                JOIN runs r ON r.run_id = vm.run_id
                ORDER BY r.timestamp DESC
            """)
            rows = [dict(row) for row in cursor.fetchall()]

        if not rows:
            return jsonify({"status": "error", "message": "No video metrics found"}), 404

        # Build CSV
        output = io.StringIO()
        columns = [
            'run_id', 'timestamp', 'model', 'prompt', 'generation_type', 'filename',
            'fvd_score', 'legacy_fvd_score', 'video_ssim_mean', 'video_ssim_std',
            'video_psnr_mean', 'video_psnr_std',
            'video_lpips_mean', 'video_lpips_std',
            'adjacent_pixel_stability', 'whole_frame_anchored_dino_cosine',
            'whole_frame_adjacent_dino_cosine', 'flow_magnitude_stability',
            'video_aesthetic_mean', 'video_aesthetic_min', 'video_aesthetic_std',
            'metric_version', 'legacy_metadata_json', 'computed_at'
        ]
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()

        import json as json_lib
        for row in rows:
            csv_row = {k: row.get(k, '') for k in columns}
            # Extract filename from generated_images
            gen_images = row.get('generated_images', '[]')
            if isinstance(gen_images, str):
                gen_images = json_lib.loads(gen_images)
            csv_row['filename'] = gen_images[0] if gen_images else ''
            # Extract quality metrics from metadata JSON
            metadata = row.get('metadata')
            if metadata:
                if isinstance(metadata, str):
                    metadata = json_lib.loads(metadata)
                for key in ['adjacent_pixel_stability', 'whole_frame_anchored_dino_cosine',
                            'whole_frame_adjacent_dino_cosine', 'flow_magnitude_stability',
                            'video_aesthetic_mean', 'video_aesthetic_min', 'video_aesthetic_std']:
                    csv_row[key] = metadata.get(key, '')
                csv_row['metric_version'] = metadata.get('metric_version', 'invalid_legacy_result')
                csv_row['legacy_metadata_json'] = json_lib.dumps(metadata) if metadata.get('metric_version') != 'custom-video-v2' else ''
            writer.writerow(csv_row)

        from flask import Response
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=video_metrics.csv'}
        )

    except Exception as e:
        logging.error(f"Error exporting video metrics: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/compare-video-metrics', methods=['POST', 'OPTIONS'])
def compare_video_metrics():
    """Compare metrics between two videos."""
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response

    try:
        data = request.json
        run_id_1 = data.get('run_id_1', '')
        run_id_2 = data.get('run_id_2', '')

        if not run_id_1 or not run_id_2:
            return jsonify({"status": "error", "message": "Both run_id_1 and run_id_2 required"}), 400

        from data.scripts.database import DreamLayerDB
        db = DreamLayerDB()

        metrics1 = db.get_video_metrics(run_id_1)
        metrics2 = db.get_video_metrics(run_id_2)

        if not metrics1 or not metrics2:
            missing = []
            if not metrics1:
                missing.append(run_id_1)
            if not metrics2:
                missing.append(run_id_2)
            return jsonify({"status": "error", "message": f"Metrics not found for: {', '.join(missing)}"}), 404

        # Compute deltas for numeric fields
        compare_keys = [
            'fvd_score', 'video_ssim_mean', 'video_psnr_mean', 'video_lpips_mean'
        ]
        # Also compare quality metrics from metadata
        quality_keys = [
            'adjacent_pixel_stability', 'whole_frame_anchored_dino_cosine',
            'whole_frame_adjacent_dino_cosine', 'flow_magnitude_stability',
            'video_aesthetic_mean'
        ]

        def get_metric_value(metrics_row, key):
            if key in metrics_row and metrics_row[key] is not None:
                return metrics_row[key]
            if metrics_row.get('metadata') and key in metrics_row['metadata']:
                return metrics_row['metadata'][key]
            return None

        deltas = {}
        for key in compare_keys + quality_keys:
            v1 = get_metric_value(metrics1, key)
            v2 = get_metric_value(metrics2, key)
            if v1 is not None and v2 is not None:
                deltas[key] = round(v1 - v2, 6)

        return jsonify({
            "status": "success",
            "video_1": {"run_id": run_id_1, "metrics": metrics1},
            "video_2": {"run_id": run_id_2, "metrics": metrics2},
            "deltas": deltas
        })

    except Exception as e:
        logging.error(f"Error comparing video metrics: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    logging.info("Starting Txt2Vid server on port 5008...")
    print("Starting Txt2Vid server on port 5008...")
    app.run(debug=True, host='0.0.0.0', port=5008)
