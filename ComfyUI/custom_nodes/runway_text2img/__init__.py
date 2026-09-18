import requests
import os
import time
from io import BytesIO
from PIL import Image
import numpy as np
import torch
from dotenv import load_dotenv

# Load API key
load_dotenv()
RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")
RUNWAY_API_URL = "https://api.dev.runwayml.com/v1/text_to_image"

class RunwayTextToImage:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "a fantasy landscape with mountains and rivers"
                }),
                "ratio": ([
                    "1920:1080", "1080:1920", "1024:1024", "1280:720", "720:1280",
                    "720:720", "960:720", "720:960", "1360:768", "1168:880",
                    "1440:1080", "1080:1440", "1808:768", "2112:912", "1680:720"
                ], {"default": "1024:1024"}),
                "timeout": ("INT", {"default": 30, "min": 1, "max": 1200}),
                "seed": ("INT", {"default": 42, "min": 0, "max": 4294967295}),
                "mock": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "run"
    CATEGORY = "Runway"

# ✅ ComfyUI expects this function to exist at module level
def run(prompt, ratio, timeout, seed, mock):
    width, height = map(int, ratio.split(":"))

    if mock:
        print("✅ Mock mode enabled – skipping real API call.")

        dummy_np = (np.random.rand(height, width, 3) * 255).astype(np.uint8)  # [H, W, 3]
        dummy_tensor = torch.from_numpy(dummy_np).permute(2, 0, 1).float() / 255.0  # [3, H, W]
        print(f"✅ Dummy tensor created with shape: {dummy_tensor.shape}, dtype: {dummy_tensor.dtype}")

        return (dummy_tensor,)


    api_key = os.getenv("RUNWAY_API_KEY")
    if not api_key:
        raise RuntimeError("❌ Missing RUNWAY_API_KEY environment variable.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Runway-Version": "2024-11-06"
    }

    payload = {
        "model": "gen4_image",
        "promptText": prompt,
        "ratio": ratio,
        "seed": seed
    }

    print("got prompt")
    print("=== Runway Payload ===")
    print(payload)

    response = requests.post(RUNWAY_API_URL, json=payload, headers=headers)
    print("=== Response Code ===", response.status_code)
    print("=== Response Body ===", response.text)
    response.raise_for_status()

    job_id = response.json()["id"]

    # Polling for result
    image_url = None
    for _ in range(timeout):
        poll = requests.get(f"{RUNWAY_API_URL}/{job_id}", headers=headers)
        poll_data = poll.json()
        if poll_data.get("status") == "succeeded":
            image_url = poll_data["outputs"][0]["uri"]
            break
        elif poll_data.get("status") == "failed":
            raise RuntimeError("❌ Runway generation failed.")
        time.sleep(1)

    if not image_url:
        raise RuntimeError("⏰ Timed out waiting for Runway result.")

    image_bytes = requests.get(image_url).content
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    image_tensor = torch.from_numpy(np.array(image)).float() / 255.0
    image_tensor = image_tensor.permute(2, 0, 1)  # [3, H, W]
    return (image_tensor,)  # no batch dim

RunwayTextToImage.run = staticmethod(run)

NODE_CLASS_MAPPINGS = {
    "RunwayTextToImage": RunwayTextToImage
}
