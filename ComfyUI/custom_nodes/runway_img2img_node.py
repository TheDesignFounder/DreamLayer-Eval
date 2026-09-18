import os
import requests
from PIL import Image
from io import BytesIO
import comfy.utils


class RunwayImg2Img:
    """
    Runway Gen-4 Reference-to-Image Node

    This node sends a prompt and reference image to Runway's closed-source Gen-4 model API
    and receives a generated image in return.

    Environment Variables:
        RUNWAY_API_KEY (str): Required. Your API key for Runway. Must be added to `.env`.

    Inputs:
        image (IMAGE): The reference image as a tensor (1 x H x W x C, normalized 0-1).
        prompt (str): A text prompt describing the desired output.

    Outputs:
        IMAGE: The generated image from Runway's Gen-4 API.

    Notes:
        - You must have access to Runway's Gen-4 API and a valid API key.
        - This node makes an external HTTP request, so it may take several seconds.
        - Requires internet access.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "prompt": ("STRING", {"multiline": True}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "runway_generate"
    CATEGORY = "Runway/API"

    def __init__(self):
        api_key = os.getenv("RUNWAY_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "🚨 RUNWAY_API_KEY not set. Please add it to your .env file:\n\nRUNWAY_API_KEY=your_api_key_here"
            )
        self.api_key = api_key

    def runway_generate(self, image, prompt):
        # Convert tensor to PIL image
        pil_image = comfy.utils.tensor_to_image(image)

        # Save to memory buffer
        buffer = BytesIO()
        pil_image.save(buffer, format="PNG")
        buffer.seek(0)

        # Prepare payload
        files = {"promptImage": ("image.png", buffer, "image/png")}
        data = {"prompt": prompt}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Runway-Version": "2024-11-06"
        }

        # Send request
        try:
            response = requests.post(
                "https://api.runwayml.com/v1/text_to_image",
                headers=headers,
                files=files,
                data=data,
                timeout=60
            )
        except Exception as e:
            raise RuntimeError(f"🛑 Network error when contacting Runway API: {e}")

        # Handle response
        if response.status_code != 200:
            raise RuntimeError(f"🛑 Runway API Error {response.status_code}: {response.text}")

        try:
            output_image = Image.open(BytesIO(response.content)).convert("RGB")
        except Exception as e:
            raise RuntimeError(f"🛑 Failed to decode image from Runway response: {e}")

        # Convert back to tensor
        return (comfy.utils.image_to_tensor(output_image),)

# Register node
NODE_CLASS_MAPPINGS = {
    "RunwayImg2Img": RunwayImg2Img
}
