import os
from dotenv import load_dotenv
load_dotenv()
import google.generativeai as genai
import torch
from PIL import Image
import numpy as np
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

class GeminiVisionNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"default": "Describe this image", "multiline": True}),
                "image": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("description",)
    FUNCTION = "generate"
    OUTPUT_NODE = True

    @staticmethod
    def tensor_to_pil(image_tensor):
        if len(image_tensor.shape) == 4:
            image_tensor = image_tensor[0]  # (1, C, H, W) → (C, H, W)

        image_tensor = image_tensor.detach().cpu().clamp(0, 1)

        if image_tensor.shape[0] == 1:  # grayscale → RGB
            image_tensor = image_tensor.repeat(3, 1, 1)
        elif image_tensor.shape[0] > 3:
            image_tensor = image_tensor[:3]  # drop extra channels if >3

        image_np = (image_tensor.numpy().transpose(1, 2, 0) * 255).astype(np.uint8)
        return Image.fromarray(image_np)

    def __init__(self):
        super().__init__()
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def generate(self, prompt, image):
        pil_image = self.tensor_to_pil(image)
        response = self.model.generate_content([prompt, pil_image])
        return (response.text,)

NODE_CLASS_MAPPINGS = {
    "GeminiVisionNode": GeminiVisionNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GeminiVisionNode": "Gemini Vision"
}

print("✅ GeminiVisionNode registered:", NODE_CLASS_MAPPINGS)
