# Dream Layer Backend

This directory contains the backend server components for the Dream Layer project.

## Components

-   `dream_layer.py`: Main application file
-   `txt2img_server.py`: Text-to-Image generation server
-   `img2img_server.py`: Image-to-Image generation server

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
Start the servers:

bash
Copy
Edit
# Start comfyui server
python dream_layer.py

# Start txt2img server
python txt2img_server.py

# Start img2img server (in a separate terminal)
python img2img_server.py
The servers will be available at:

Text-to-Image API: http://localhost:5001/api/txt2img

Image-to-Image API: http://localhost:5001/api/img2img

## CLI Options

| Flag     | Description |
|----------|-------------|
| `--safe` | Limit VRAM usage by lowering batch size to 1 and using fp16 precision |

```
