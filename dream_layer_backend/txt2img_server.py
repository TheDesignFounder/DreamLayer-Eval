from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import json
import os
import requests
import time
import shutil
from dream_layer import get_directories
from dream_layer_backend_utils import interrupt_workflow
from shared_utils import  send_to_comfyui
from dream_layer_backend_utils.fetch_advanced_models import get_controlnet_models
from PIL import Image, ImageDraw
from txt2img_workflow import transform_to_txt2img_workflow
from run_registry import create_run_config_from_generation_data, registry
from dataclasses import asdict
import base64
from datetime import datetime
import generation_history as gh
import cleanup_scheduler

def call_banana_api_directly(data):
    """Call Gemini API directly for banana models, bypassing ComfyUI"""
    try:
        import google.generativeai as genai  # Optional legacy provider; core startup stays offline.
        # Configure Gemini with API key
        from dream_layer_backend_utils.api_key_injector import read_api_keys_from_env
        api_keys = read_api_keys_from_env()
        gemini_key = api_keys.get('GEMINI_API_KEY')
        if not gemini_key:
            raise Exception("No Gemini API key found")
        
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-2.5-flash-image-preview')
        
        # Extract parameters from UI data
        prompt = data.get('prompt', 'beautiful image')
        
        # Generate content
        response = model.generate_content([prompt])
        
        # Extract image data (based on working test)
        generated_images = []
        
        # Calculate filename once outside the loop
        import glob
        from dream_layer import get_directories
        output_dir, _ = get_directories()
        existing_files = glob.glob(os.path.join(output_dir, "DreamLayer_Banana_*.png"))
        next_num = len(existing_files) + 1
        
        for candidate in response.candidates:
            image_parts = [p for p in candidate.content.parts if hasattr(p, 'inline_data')]
            if len(image_parts) >= 2:  # Process second part (index 1)
                image_binary = image_parts[1].inline_data.data
                filename = f"DreamLayer_Banana_{next_num:05d}_.png"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(image_binary)
                
                import shutil
                served_images_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'served_images')
                os.makedirs(served_images_dir, exist_ok=True)
                shutil.copy2(filepath, os.path.join(served_images_dir, filename))
                
                generated_images.append({
                    "filename": filename,
                    "url": f"http://localhost:5001/api/images/{filename}",
                    "type": "output",
                    "subfolder": ""
                })
                break
        
        # Return in expected format
        return {
            "status": "success",
            "all_images": generated_images,
            "generated_images": generated_images
        }
        
    except Exception as e:
        return {"error": f"Banana API error: {str(e)}"}

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:*", "http://127.0.0.1:*"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})
socketio = SocketIO(app, cors_allowed_origins=["http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:*", "http://127.0.0.1:*"])

# Get served images directory
output_dir, _ = get_directories()
SERVED_IMAGES_DIR = os.getenv('DREAMLAYER_SERVED_IMAGES_DIR', os.path.join(os.path.dirname(__file__), 'served_images'))
os.makedirs(SERVED_IMAGES_DIR, exist_ok=True)



@app.route('/api/txt2img', methods=['POST', 'OPTIONS'])
def handle_txt2img():
    """Handle text-to-image generation requests"""
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"})
    
    try:
        data = request.json
        if data:
            print("Data:", json.dumps(data, indent=2))
            
            # Print specific fields of interest
            print("\nKey Parameters:")
            print("-"*20)
            print(f"Prompt: {data.get('prompt', 'Not provided')}")
            print(f"Negative Prompt: {data.get('negative_prompt', 'Not provided')}")
            print(f"Batch Count: {data.get('batch_count', 1)}")
            
            # Check ControlNet data specifically
            controlnet_data = data.get('controlnet', {})
            print(f"\n🎮 ControlNet Data:")
            print("-"*20)
            print(f"ControlNet enabled: {controlnet_data.get('enabled', False)}")
            if controlnet_data.get('units'):
                for i, unit in enumerate(controlnet_data['units']):
                    print(f"Unit {i}:")
                    print(f"  Enabled: {unit.get('enabled', False)}")
                    print(f"  Has input_image: {unit.get('input_image') is not None}")
                    print(f"  Input image type: {type(unit.get('input_image'))}")
                    if unit.get('input_image'):
                        print(f"  Input image length: {len(unit['input_image']) if isinstance(unit['input_image'], str) else 'N/A'}")
                        print(f"  Input image preview: {unit['input_image'][:50] if isinstance(unit['input_image'], str) else 'N/A'}...")
            else:
                print("No ControlNet units found")
            
            # Extract batch_count and implement loop
            batch_count = data.get('batch_count', 1)
            all_generated_images = []
            failures = []
            
            for iteration in range(batch_count):
                try:
                    print(f"\n🔄 Batch iteration {iteration + 1}/{batch_count}")
                    
                    # Only generate new random seed if random_seed is enabled
                    iteration_data = data.copy()
                    if data.get('random_seed', True):
                        iteration_data['seed'] = -1  # Force new random seed
                    
                    # Transform to ComfyUI workflow
                    workflow = transform_to_txt2img_workflow(iteration_data)
                    print(f"Generated ComfyUI Workflow for iteration {iteration + 1}")
                    
                    # Check if this is a banana model - bypass ComfyUI
                    model_name = iteration_data.get('model_name', '').lower()
                    if 'banana' in model_name:
                        print("🍌 BANANA: Bypassing ComfyUI, calling Gemini directly")
                        comfy_response = call_banana_api_directly(iteration_data)
                    else:
                        # Send to ComfyUI server
                        comfy_response = send_to_comfyui(workflow)
                    
                    if "error" in comfy_response:
                        failures.append({'iteration': iteration, 'reason': str(comfy_response['error'])})
                        print(f"⚠️ Error in iteration {iteration + 1}: {comfy_response['error']}")
                        continue  # Continue with next iteration
                    
                    # Extract generated image filenames
                    generated_images = []
                    if comfy_response.get("all_images"):
                        for img_data in comfy_response["all_images"]:
                            if isinstance(img_data, dict) and "filename" in img_data:
                                generated_images.append(img_data["filename"])
                        all_generated_images.extend(comfy_response["all_images"])

                    # Save each generated image to history database
                    for img_data in comfy_response.get("all_images", []):
                        if isinstance(img_data, dict) and "filename" in img_data:
                            filename = img_data["filename"]
                            file_path = os.path.join(SERVED_IMAGES_DIR, filename)

                            # Create unique ID for this generation
                            gen_id = f"txt2img_{int(time.time() * 1000)}_{filename}"

                            # Save to history
                            gh.save_generation({
                                'id': gen_id,
                                'type': 'txt2img',
                                'filename': filename,
                                'file_path': file_path,
                                'url': img_data.get("url", f"http://localhost:5001/api/images/{filename}"),
                                'prompt': iteration_data.get('prompt', ''),
                                'negative_prompt': iteration_data.get('negative_prompt', ''),
                                'settings': iteration_data,
                                'created_at': datetime.now().isoformat()
                            })

                    print(f"Registering run for iteration {iteration + 1}")
                    # Register the completed run - each iteration gets unique run_id
                    try:
                        run_config = create_run_config_from_generation_data(
                            iteration_data, generated_images, "txt2img"
                        )
                        registry.add_run(run_config)
                        print(f"✅ Run registered with unique run_id: {run_config.run_id}")
                    except Exception as e:
                        print(f"⚠️ Error registering run for iteration {iteration + 1}: {str(e)}")
                        
                except Exception as e:
                    failures.append({'iteration': iteration, 'reason': str(e)})
                    print(f"⚠️ Error in iteration {iteration + 1}: {str(e)}")
                    continue  # Continue with next iteration
            
            if not all_generated_images:
                return jsonify({'status': 'error', 'message': 'No generation outputs', 'failures': failures}), 502
            response = jsonify({
                "status": "success",
                "failures": failures,
                "message": "Workflow sent to ComfyUI successfully",
                "comfy_response": {
                    "all_images": all_generated_images
                },
                "generated_images": all_generated_images
            })
            
            return response
            
        else:
            return jsonify({
                "status": "error",
                "message": "No data received"
            }), 400
            
    except Exception as e:
        print(f"Error in handle_txt2img: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# WebSocket handlers
@socketio.on('connect')
def handle_connect():
    print("Client connected to batch progress WebSocket")
    emit('connected', {'status': 'connected'})

@app.route('/api/txt2img/batch', methods=['POST'])
def handle_txt2img_batch():
    """Handle batch text-to-image generation from prompts array with progress updates"""
    try:
        data = request.json
        if not data or 'prompts' not in data:
            return jsonify({"status": "error", "message": "No prompts provided"}), 400
        
        prompts = data['prompts']
        all_generated_images = []
        failed_prompts = []
        batch_seeds = []  # Store seeds from first prompt
        
        for i, prompt in enumerate(prompts):
            batch_count = data.get('batch_count', 1)
            for batch_idx in range(batch_count):
                try:
                    # Emit progress update
                    socketio.emit('progress', {
                        'type': 'progress',
                        'current': i + 1,
                        'total': len(prompts),
                        'current_prompt': prompt,
                        'status': 'processing'
                    })
                    
                    iteration_data = data.copy()
                    iteration_data['prompt'] = prompt
                    
                    # Seed handling: store from first prompt, reuse for others
                    if i == 0:  # First prompt: generate and store seeds
                        if data.get('random_seed', True) or batch_idx > 0:
                            iteration_data['seed'] = -1
                        batch_seeds.append(iteration_data.get('seed', -1))
                    else:  # Subsequent prompts: reuse stored seeds
                        iteration_data['seed'] = batch_seeds[batch_idx]
                    
                    workflow = transform_to_txt2img_workflow(iteration_data)
                    
                    # Check if this is a banana model - bypass ComfyUI
                    model_name = iteration_data.get('model_name', '').lower()
                    if 'banana' in model_name:
                        comfy_response = call_banana_api_directly(iteration_data)
                    else:
                        comfy_response = send_to_comfyui(workflow)
                    
                    if "error" in comfy_response:
                        failed_prompts.append(f"Prompt {i+1}: {prompt[:50]}...")
                        socketio.emit('progress', {
                            'type': 'error',
                            'current': i + 1,
                            'total': len(prompts),
                            'current_prompt': prompt,
                            'status': 'failed'
                        })
                        continue
                    
                    generated_images = []
                    if comfy_response.get("all_images"):
                        for img_data in comfy_response["all_images"]:
                            if isinstance(img_data, dict) and "filename" in img_data:
                                generated_images.append(img_data["filename"])
                        all_generated_images.extend(comfy_response["all_images"])
                    
                    run_config = create_run_config_from_generation_data(
                        iteration_data, generated_images, "txt2img"
                    )
                    registry.add_run(run_config)
                    
                    # Emit generated images immediately (one per batch iteration)
                    if comfy_response.get("all_images"):
                        img_data = comfy_response["all_images"][0]  # Only emit first image from this iteration
                        socketio.emit('image_generated', {'prompt': prompt, 'image_data': img_data, 'prompt_index': i + 1})
                    
                    # Emit completion for this prompt
                    socketio.emit('progress', {
                        'type': 'completed',
                        'current': i + 1,
                        'total': len(prompts),
                        'current_prompt': prompt,
                        'status': 'completed'
                    })
                    
                except Exception as e:
                    failed_prompts.append(f"Prompt {i+1}: {prompt[:50]}...")
                    socketio.emit('progress', {
                        'type': 'error',
                        'current': i + 1,
                        'total': len(prompts),
                        'current_prompt': prompt,
                        'status': 'failed'
                    })
                    continue
        
        # Emit batch completion
        socketio.emit('progress', {
            'type': 'batch_complete',
            'total_prompts': len(prompts),
            'processed_prompts': len(prompts) - len(failed_prompts),
            'failed_prompts': len(failed_prompts),
            'status': 'complete'
        })
        
        return jsonify({
            "status": "success",
            "total_prompts": len(prompts),
            "processed_prompts": len(prompts) - len(failed_prompts),
            "failed_prompts": failed_prompts,
            "all_images": all_generated_images
        })
        
    except Exception as e:
        socketio.emit('progress', {
            'type': 'error',
            'status': 'batch_failed',
            'message': str(e)
        })
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/txt2img/create-grid', methods=['POST'])
def create_txt2img_grid():
    """Create grids from recent txt2img generations based on batch settings"""
    try:
        data = request.get_json()
        batch_size = data.get('batch_size', 4)
        batch_count = data.get('batch_count', 1)
        
        print(f"[API] Creating grids for {batch_count} batches of {batch_size} images each")
        
        # Get recent images
        from grid_exporter import LabeledGridExporter
        exporter = LabeledGridExporter()
        
        total_images_needed = batch_size * batch_count
        recent_images = exporter.get_recent_images(total_images_needed)
        
        if len(recent_images) < total_images_needed:
            return jsonify({
                "status": "error",
                "message": f"Not enough recent images. Found {len(recent_images)}, needed {total_images_needed}"
            }), 400
        
        grids = []
        
        # Create one grid per batch
        for batch_idx in range(batch_count):
            start_idx = batch_idx * batch_size
            end_idx = start_idx + batch_size
            batch_images = recent_images[start_idx:end_idx]
            
            # Auto-calculate grid size based on batch_size
            grid_size = exporter.layout_manager.calculate_grid_size(batch_size, None)
            
            # Create grid for this batch
            timestamp = int(time.time())
            filename = f"txt2img_batch_{batch_idx + 1}_{timestamp}.png"
            
            grid_path = exporter.export_grid(
                batch_images,
                filename,
                grid_size,
                show_labels=True,
                show_filenames=False
            )
            
            # Copy to served directory for frontend access
            served_filename = f"txt2img_grid_{timestamp}_{batch_idx}.png"
            served_path = os.path.join(SERVED_IMAGES_DIR, served_filename)
            shutil.copy2(grid_path, served_path)
            
            grids.append({
                'url': f"http://localhost:5001/api/images/{served_filename}",
                'batch_size': batch_size,
                'batch_index': batch_idx + 1,
                'grid_layout': f"{grid_size[0]}x{grid_size[1]}",
                'timestamp': timestamp
            })
            
            print(f"[API] Created grid {batch_idx + 1}/{batch_count}: {grid_size[0]}x{grid_size[1]} layout")
        
        return jsonify({
            'status': 'success',
            'grids': grids,
            'message': f'Created {len(grids)} grids successfully'
        })
        
    except Exception as e:
        print(f"[API] Error creating txt2img grids: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/txt2img/interrupt', methods=['POST'])
def handle_txt2img_interrupt():
    """Handle interruption of txt2img generation"""
    print("Interrupting txt2img generation...")
    success = interrupt_workflow()
    return jsonify({"status": "received", "interrupted": success})

@app.route('/api/images/<filename>', methods=['GET'])
def serve_image_endpoint(filename):
    """
    Serve images from multiple possible directories
    This endpoint is needed here because the frontend expects it on this port
    """
    try:
        # Use shared function
        from shared_utils import serve_image
        return serve_image(filename)
            
    except Exception as e:
        print(f"❌ Error serving image {filename}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/controlnet/models', methods=['GET'])
def get_controlnet_models_endpoint():
    """Get available ControlNet models"""
    try:
        models = get_controlnet_models()
        return jsonify({
            "status": "success",
            "models": models
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to fetch ControlNet models: {str(e)}"
        }), 500

@app.route('/api/upload-controlnet-image', methods=['POST'])
def upload_controlnet_image_endpoint():
    """
    Endpoint to upload ControlNet images directly to ComfyUI input directory
    This endpoint is needed here because the frontend expects it on this port
    """
    try:
        if 'file' not in request.files:
            return jsonify({
                "status": "error",
                "message": "No file provided"
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "status": "error",
                "message": "No file selected"
            }), 400
        
        unit_index = request.form.get('unit_index', '0')
        try:
            unit_index = int(unit_index)
        except ValueError:
            unit_index = 0
        
        # Use shared function
        from shared_utils import upload_controlnet_image as upload_cn_image
        result = upload_cn_image(file, unit_index)
        
        if isinstance(result, tuple):
            return jsonify(result[0]), result[1]
        else:
            return jsonify(result)
            
    except Exception as e:
        print(f"❌ Error uploading ControlNet image: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == "__main__":
    print("\nStarting Text2Image Handler Server with WebSocket support...")
    print("Listening for requests at http://localhost:5001/api/txt2img")
    print("WebSocket available at ws://localhost:5001")
    print("ControlNet endpoints available:")
    print("  - GET /api/controlnet/models")
    print("  - POST /api/upload-controlnet-image")
    print("  - GET /api/images/<filename>")

    # Initialize cleanup scheduler (runs every 3 hours)
    print("\nInitializing cleanup scheduler...")
    cleanup_scheduler.init_scheduler(
        interval_hours=3,
        image_retention_days=7,
        video_retention_days=2
    )

    socketio.run(app, host='127.0.0.1', port=5001, debug=True, allow_unsafe_werkzeug=True) 
