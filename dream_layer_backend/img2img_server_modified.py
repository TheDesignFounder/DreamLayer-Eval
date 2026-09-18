from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import json
import logging
import os
from PIL import Image
import io
import time
from shared_utils import send_to_comfyui
from img2img_workflow import transform_to_img2img_workflow
from shared_utils import COMFY_API_URL
from dream_layer_backend_utils.fetch_advanced_models import get_controlnet_models

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
COMFY_INPUT_DIR = os.path.join(COMFY_UI_DIR, "input")
COMFY_OUTPUT_DIR = os.path.join(COMFY_UI_DIR, "output")

# Create a directory to store our served images
SERVED_IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "served_images")
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

        # Transform data to ComfyUI workflow
        workflow = transform_to_img2img_workflow(data)
        
        # Log the workflow for debugging
        logger.info("Generated workflow:")
        logger.info(json.dumps(workflow, indent=2))
        
        # Send to ComfyUI
        comfy_response = send_to_comfyui(workflow)
        
        if "error" in comfy_response:
            return jsonify({
                "status": "error",
                "message": comfy_response["error"]
            }), 500
        
        # Log generated images if present
        if "generated_images" in comfy_response:
            images = comfy_response["generated_images"]
            logger.info("Generated Images Details:")
            for i, img in enumerate(images):
                logger.info(f"Image {i + 1}:")
                logger.info(f"  Filename: {img.get('filename')}")
                logger.info(f"  Type: {img.get('type')}")
                logger.info(f"  Subfolder: {img.get('subfolder', 'None')}")
                logger.info(f"  URL: {img.get('url')}")
        
        response = jsonify({
            "status": "success",
            "message": "Workflow sent to ComfyUI successfully",
            "comfy_response": comfy_response,
            "workflow": workflow
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

@app.route('/api/pika_frame', methods=['POST'])
def pika_frame():
    """
    Generate a stylized single-frame image using the Pika API.

    Tip: To upgrade this endpoint to full video, set video=True and handle multi-frame outputs as a video file.
    """
    try:
        # Check for required fields in the incoming request
        data = request.json
        if not data or 'input_image' not in data:
            return jsonify({"error": "Missing required field: input_image"}), 400

        motion_strength = float(data.get('motion_strength', 0.5))

        # Process base64 input image
        input_image = data['input_image']
        if input_image.startswith('data:'):
            input_image = input_image.split(',')[1]
        image_bytes = base64.b64decode(input_image)

        # Prepare for Pika API
        api_url = "https://api.pika.art/v2/video"
        api_key = os.getenv("PIKA_API_KEY")

        # If no key or using placeholder, return a gray image (mock)
        if not api_key or api_key == "pk-placeholder":
            image = Image.new("RGB", (256, 256), color="gray")
            img_io = io.BytesIO()
            image.save(img_io, format="PNG")
            img_io.seek(0)
            return (
                img_io.read(),
                200,
                {
                    "Content-Type": "image/png",
                    "Content-Disposition": "inline; filename=mocked.png"
                }
            )

        files = {
            "image": ("input.png", image_bytes, "image/png"),
        }
        data_api = {
            "video": "false",
            "motion_strength": str(motion_strength),
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
        }

        response = requests.post(api_url, files=files, data=data_api, headers=headers)
        if response.status_code != 200:
            return jsonify({"error": f"Pika API error: {response.text}"}), 500

        result = response.json()
        frames = result.get("frames")
        if not frames or len(frames) != 1:
            return jsonify({"error": "Pika API should return exactly one frame"}), 500

        frame_b64 = frames[0]
        frame_bytes = base64.b64decode(frame_b64)
        image = Image.open(io.BytesIO(frame_bytes))

        # Save PNG to BytesIO and return as response
        img_io = io.BytesIO()
        image.save(img_io, format='PNG')
        img_io.seek(0)

        return (
            img_io.read(),
            200,
            {
                "Content-Type": "image/png",
                "Content-Disposition": "inline; filename=stylized.png"
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004, debug=True) 
