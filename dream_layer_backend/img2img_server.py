from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import json
import logging
import os
import requests
import random
from PIL import Image
import io
import time
from shared_utils import send_to_comfyui
from img2img_workflow import transform_to_img2img_workflow
from shared_utils import COMFY_API_URL
from dream_layer_backend_utils.fetch_advanced_models import get_controlnet_models
from dream_layer_backend_utils.api_key_injector import redact_secrets, _DEBUG
from run_registry import create_run_config_from_generation_data
from dataclasses import asdict
import requests
from datetime import datetime
import generation_history as gh
import cleanup_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Configure CORS to allow requests from frontend
CORS(app, resources={
    r"/*": {  # Allow CORS for all routes
        "origins": ["http://localhost:8080"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})


# Get the absolute path to the ComfyUI root directory (parent of our backend directory)
COMFY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ComfyUI's input directory should be inside the ComfyUI directory
COMFY_UI_DIR = os.path.join(COMFY_ROOT, "ComfyUI")
COMFY_INPUT_DIR = os.getenv("DREAMLAYER_INPUT_DIR", os.path.join(COMFY_UI_DIR, "input"))
COMFY_OUTPUT_DIR = os.path.join(COMFY_UI_DIR, "output")

# Create a directory to store our served images
SERVED_IMAGES_DIR = os.getenv("DREAMLAYER_SERVED_IMAGES_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "served_images"))
os.makedirs(SERVED_IMAGES_DIR, exist_ok=True)

logger.info(f"ComfyUI root directory: {COMFY_ROOT}")
logger.info(f"ComfyUI directory: {COMFY_UI_DIR}")
logger.info(f"ComfyUI input directory: {COMFY_INPUT_DIR}")
logger.info(f"ComfyUI output directory: {COMFY_OUTPUT_DIR}")

def verify_input_directory():
    """Verify that the input directory exists and is writable"""
    if not os.path.exists(COMFY_INPUT_DIR):
        raise RuntimeError(f"Input directory does not exist: {COMFY_INPUT_DIR}")
    if not os.access(COMFY_INPUT_DIR, os.W_OK):
        raise RuntimeError(f"Input directory is not writable: {COMFY_INPUT_DIR}")
    logger.info(f"Verified input directory: {COMFY_INPUT_DIR}")

# Verify input directory on startup
verify_input_directory()


# Using shared functions from shared_utils.py

@app.route('/api/img2img', methods=['POST', 'OPTIONS'])
def handle_img2img():
    if request.method == 'OPTIONS':
        # Handle preflight request
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', 'http://localhost:8080')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response

    try:
        # Verify input directory before processing
        verify_input_directory()
        
        data = request.json
        logger.info("Received img2img request with data: %s", {
            **data,
            'input_image': 'BASE64_IMAGE_DATA' if 'input_image' in data else None
        })

        # Validate required fields
        required_fields = ['prompt', 'input_image', 'denoising_strength']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}'
                }), 400

        # Process the input image
        try:
            # Get the input image from the request
            input_image = data['input_image']
            
            # Check if it's a data URL
            if input_image.startswith('data:'):
                # Extract the base64 part
                if ',' in input_image:
                    input_image = input_image.split(',')[1]
                
                # Decode base64 image
                image_bytes = base64.b64decode(input_image)
                image = Image.open(io.BytesIO(image_bytes))
            else:
                # If it's not a data URL, assume it's already base64 encoded
                image_bytes = base64.b64decode(input_image)
                image = Image.open(io.BytesIO(image_bytes))
            
            # Save the image temporarily in ComfyUI's input directory
            temp_filename = f"input_{int(time.time())}.png"
            temp_filepath = os.path.join(COMFY_INPUT_DIR, temp_filename)
            
            # Convert image to RGB if it's in RGBA mode
            if image.mode == 'RGBA':
                image = image.convert('RGB')
            elif image.mode not in ['RGB', 'L']:
                image = image.convert('RGB')
            
            # Save image and verify it was saved correctly
            image.save(temp_filepath, format='PNG')
            if not os.path.exists(temp_filepath):
                raise RuntimeError(f"Failed to save image to {temp_filepath}")
            
            # Verify the saved image can be opened
            try:
                with Image.open(temp_filepath) as verify_img:
                    verify_img.verify()
                logger.info(f"Verified saved image: {temp_filepath}")
            except Exception as e:
                raise RuntimeError(f"Saved image verification failed: {str(e)}")
            
            # Update the data with just the filename for the workflow
            data['input_image'] = temp_filename
            
            # Log image details
            logger.info("Input image saved as: %s, format=%s, size=%s, mode=%s", 
                       temp_filename, image.format, image.size, image.mode)
            
            # List directory contents for debugging
            logger.info("Input directory contents:")
            for filename in os.listdir(COMFY_INPUT_DIR):
                logger.info(f"  {filename}")
            
        except Exception as e:
            logger.error("Error processing input image: %s", str(e))
            return jsonify({
                'status': 'error',
                'message': f'Invalid input image: {str(e)}'
            }), 400

        # Check if this is a Luma model and route accordingly
        model_name = data.get('model', '')
        if model_name in ['luma-photon', 'luma-photon-flash']:
            # Handle batch_size for Luma models by making multiple sequential calls
            batch_size = data.get('batch_size', 1)
            all_responses = []
            
            for i in range(batch_size):
                logger.info(f"Processing Luma batch item {i+1}/{batch_size}")
                
                # Create single image request
                single_data = data.copy()
                single_data['batch_size'] = 1
                
                # Use Luma workflow for single image
                from workflows.txt2img.luma_core_generation_workflow import get_luma_img2img_workflow
                workflow = get_luma_img2img_workflow(single_data)
                
                # Send to ComfyUI and wait for completion
                comfy_response = send_to_comfyui(workflow)
                
                # Wait for this generation to complete before starting next
                if 'prompt_id' in comfy_response:
                    # Poll ComfyUI until this prompt completes
                    while True:
                        status_response = requests.get(f"{COMFY_API_URL}/history/{comfy_response['prompt_id']}")
                        if status_response.status_code == 200 and status_response.json():
                            break
                        time.sleep(2)
                
                all_responses.append(comfy_response)
            
            # Use the last response structure but indicate batch processing
            comfy_response = all_responses[-1]
            comfy_response['batch_responses'] = all_responses
        else:
            # Extract batch_count and implement loop
            batch_count = data.get('batch_count', 1)
            all_generated_images = []
            
            for iteration in range(batch_count):
                try:
                    logger.info(f"Batch iteration {iteration + 1}/{batch_count}")
                    
                    # Generate new random seed for each iteration
                    iteration_data = data.copy()
                    iteration_data['seed'] = -1  # Force new random seed
                    
                    # Transform to ComfyUI workflow
                    workflow = transform_to_img2img_workflow(iteration_data)
                    logger.info(f"Generated ComfyUI Workflow for iteration {iteration + 1}")
                    
                    # Send to ComfyUI server
                    comfy_response = send_to_comfyui(workflow)
                    
                    if "error" in comfy_response:
                        logger.warning(f"Error in iteration {iteration + 1}: {comfy_response['error']}")
                        continue  # Continue with next iteration
                    
                    # Extract generated image filenames
                    generated_images = []
                    if comfy_response.get("all_images"):
                        for img_data in comfy_response["all_images"]:
                            if isinstance(img_data, dict) and "filename" in img_data:
                                generated_images.append(img_data["filename"])
                        all_generated_images.extend(comfy_response["all_images"])

                    # Save each generated image to history database
                    from dream_layer import get_directories
                    output_dir, _ = get_directories()
                    for img_data in comfy_response.get("all_images", []):
                        if isinstance(img_data, dict) and "filename" in img_data:
                            filename = img_data["filename"]
                            file_path = os.path.join(output_dir, filename)

                            # Create unique ID for this generation
                            gen_id = f"img2img_{int(time.time() * 1000)}_{filename}"

                            # Save to history
                            gh.save_generation({
                                'id': gen_id,
                                'type': 'img2img',
                                'filename': filename,
                                'file_path': file_path,
                                'url': img_data.get("url", f"http://localhost:5004/api/images/{filename}"),
                                'prompt': iteration_data.get('prompt', ''),
                                'negative_prompt': iteration_data.get('negative_prompt', ''),
                                'settings': iteration_data,
                                'created_at': datetime.now().isoformat()
                            })

                    logger.info(f"Registering run for iteration {iteration + 1}")
                    # Register the completed run - each iteration gets unique run_id
                    try:
                        from run_registry import registry
                        run_config = create_run_config_from_generation_data(
                            iteration_data, generated_images, "img2img"
                        )
                        registry.add_run(run_config)
                        logger.info(f"Run registered with unique run_id: {run_config.run_id}")
                    except Exception as e:
                        logger.warning(f"Error registering run for iteration {iteration + 1}: {str(e)}")
                        
                except Exception as e:
                    logger.warning(f"Error in iteration {iteration + 1}: {str(e)}")
                    continue  # Continue with next iteration
        
        # Handle batch_count case vs single execution
        if data.get('batch_count', 1) > 1:
            # batch_count case - all_generated_images already collected in loop above
            final_response = {
                "all_images": all_generated_images
            }
        else:
            # Single execution case - use regular img2img workflow
            workflow = transform_to_img2img_workflow(data)
            
            # Log the workflow for debugging (redacted, debug mode only)
            if _DEBUG:
                logger.info("Generated workflow:")
                logger.info(json.dumps(redact_secrets(workflow), indent=2))
            
            # Send to ComfyUI
            comfy_response = send_to_comfyui(workflow)
            
            if "error" in comfy_response:
                return jsonify({
                    "status": "error",
                    "message": comfy_response["error"]
                }), 500
            
            final_response = comfy_response
        
        # Log generated images if present
        if "generated_images" in final_response:
            images = final_response["generated_images"]
            logger.info("Generated Images Details:")
            for i, img in enumerate(images):
                logger.info(f"Image {i + 1}:")
                logger.info(f"  Filename: {img.get('filename')}")
                logger.info(f"  Type: {img.get('type')}")
                logger.info(f"  Subfolder: {img.get('subfolder', 'None')}")
                logger.info(f"  URL: {img.get('url')}")
        
        # Extract generated image filenames for single execution registration
        if data.get('batch_count', 1) == 1:
            generated_images = []
            if final_response.get("generated_images"):
                for img_data in final_response["generated_images"]:
                    if isinstance(img_data, dict) and "filename" in img_data:
                        generated_images.append(img_data["filename"])

            # Save each generated image to history database for single execution
            from dream_layer import get_directories
            output_dir, _ = get_directories()
            for img_data in final_response.get("generated_images", []):
                if isinstance(img_data, dict) and "filename" in img_data:
                    filename = img_data["filename"]
                    file_path = os.path.join(output_dir, filename)

                    # Create unique ID for this generation
                    gen_id = f"img2img_{int(time.time() * 1000)}_{filename}"

                    # Save to history
                    gh.save_generation({
                        'id': gen_id,
                        'type': 'img2img',
                        'filename': filename,
                        'file_path': file_path,
                        'url': img_data.get("url", f"http://localhost:5004/api/images/{filename}"),
                        'prompt': data.get('prompt', ''),
                        'negative_prompt': data.get('negative_prompt', ''),
                        'settings': data,
                        'created_at': datetime.now().isoformat()
                    })

            # Register the completed run for single execution
            try:
                from run_registry import registry
                run_config = create_run_config_from_generation_data(
                    data, generated_images, "img2img"
                )
                registry.add_run(run_config)
                logger.info(f"Run registered with run_id: {run_config.run_id}")
            except Exception as e:
                logger.warning(f"Error registering run: {str(e)}")
        
        response = jsonify({
            "status": "success",
            "message": "Workflow sent to ComfyUI successfully",
            "comfy_response": {
                "all_images": final_response.get("all_images", final_response.get("generated_images", []))
            },
            "generated_images": final_response.get("all_images", final_response.get("generated_images", []))
        })
        
        # Clean up the temporary image file
        try:
            os.remove(temp_filepath)
            logger.info(f"Cleaned up temporary file: {temp_filepath}")
        except Exception as e:
            logger.warning(f"Failed to remove temporary file {temp_filepath}: {str(e)}")
        
        return response

    except Exception as e:
        logger.error("Error processing request: %s", str(e))
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/img2img/interrupt', methods=['POST'])
def handle_img2img_interrupt():
    print("=== IMG2IMG INTERRUPT REQUEST ===")
    print(request.json)
    return jsonify({"status": "received"})

@app.route('/images/<filename>')
def serve_image_endpoint(filename):
    """Serve images from the served_images directory"""
    try:
        # Use shared function
        from shared_utils import serve_image
        return serve_image(filename)
    except Exception as e:
        logger.error(f"Error serving image {filename}: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    # Note: Cleanup scheduler is initialized in txt2img_server.py
    # to avoid running multiple schedulers
    print("\nStarting Img2Img Handler Server...")
    print("Listening for requests at http://localhost:5004/api/img2img")
    app.run(host='0.0.0.0', port=5004, debug=True) 