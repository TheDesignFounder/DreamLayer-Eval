import os
import requests
import base64
import io
from PIL import Image
from dotenv import load_dotenv

load_dotenv()  # Loads .env variables like RUNWAY_API_KEY


class RunwayText2Image:
    """
    Runway Gen-4 Text-to-Image Node

    Parameters:
        prompt (str): The prompt to generate the image from.

    Requires:
        RUNWAY_API_KEY environment variable to be set.

    Output:
        A PIL Image object for downstream nodes.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "runway_generate"

    def runway_generate(self, prompt):
        api_key = os.getenv("RUNWAY_API_KEY")
        if not api_key:
            raise RuntimeError("RUNWAY_API_KEY not found. Please set it in your .env or system environment.")

        url = "https://api.dev.runwayml.com/v1/text_to_image"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "prompt": prompt
        }

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            raise RuntimeError(f"Runway API error: {response.status_code} - {response.text}")

        image_b64 = response.json().get("image")
        if not image_b64:
            raise RuntimeError("No image returned from Runway API")

        image_data = base64.b64decode(image_b64)
        image = Image.open(io.BytesIO(image_data)).convert("RGB")

        return (image,)
