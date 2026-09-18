"""
Runway Gen-4: Text to Image API node
"""

import os
import requests
from PIL import Image
from io import BytesIO
import comfy.model_management as model_mgmt

class RunwayText2ImageNode:
    """
    A node that sends a text prompt to Runway's Gen-4 model and returns an image.
    Requires the environment variable RUNWAY_API_KEY to be set.

    Inputs:
    - prompt (str): The input text description
    - timeout (int): Optional request timeout (default: 30 seconds)

    Outputs:
    - image (PIL.Image.Image): The generated image
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True}),
                "timeout": ("INT", {"default": 30, "min": 5, "max": 120}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "generate"

    def generate(self, prompt, timeout=30):
        api_key = os.environ.get("RUNWAY_API_KEY")
        if not api_key:
            raise RuntimeError("❌ RUNWAY_API_KEY not found in environment. Please set it before running this node.")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "prompt": prompt
        }

        response = requests.post(
            "https://api.dev.runwayml.com/v1/text_to_image",
            headers=headers,
            json=data,
            timeout=timeout
        )

        response.raise_for_status()
        image_url = response.json().get("image_url")
        if not image_url:
            raise RuntimeError("No image_url returned from Runway API")

        image_data = requests.get(image_url)
        image = Image.open(BytesIO(image_data.content)).convert("RGB")

        return (model_mgmt.upload_PIL_to_comfy(image),)

NODE_CLASS_MAPPINGS = {
    "RunwayText2Image": RunwayText2ImageNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RunwayText2Image": "🛫 Runway Gen-4 Text2Img"
}
