"""
Luma Text to Image API Node - Fixed Version
Addresses all Sourcery AI review comments
"""

import os
import time
import requests
import torch
from typing import Optional
from io import BytesIO
from PIL import Image
import numpy as np

# Import ComfyUI utilities
from comfy.comfy_types.node_typing import IO, ComfyNodeABC


class LumaTextToImageNode(ComfyNodeABC):
    """
    Generates images from text prompts using Luma AI.
    
    This node takes a text prompt, sends it to Luma's API,
    polls for completion, and returns the generated image.
    """
    
    RETURN_TYPES = (IO.IMAGE,)
    FUNCTION = "generate_image"
    CATEGORY = "api node/image/Luma"
    API_NODE = True
    DESCRIPTION = "Generate images from text prompts using Luma AI"
    
    # Available models and aspect ratios
    MODELS = ["photon-1", "photon-2", "realistic-vision-v5"]
    ASPECT_RATIOS = ["1:1", "4:3", "3:4", "16:9", "9:16"]
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": (
                    IO.STRING,
                    {
                        "multiline": True,
                        "default": "A beautiful landscape with mountains and sunset",
                        "tooltip": "Text prompt describing the image you want to generate",
                    },
                ),
                "model": (
                    IO.COMBO,
                    {
                        "options": cls.MODELS,
                        "default": "photon-1",
                        "tooltip": "Luma AI model to use for generation",
                    },
                ),
                "aspect_ratio": (
                    IO.COMBO,
                    {
                        "options": cls.ASPECT_RATIOS,
                        "default": "16:9",
                        "tooltip": "Aspect ratio of the generated image",
                    },
                ),
                "seed": (
                    IO.INT,
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFF,
                        "tooltip": "Random seed for reproducible results",
                    },
                ),
            },
            "optional": {
                "negative_prompt": (
                    IO.STRING,
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "Negative prompt to avoid certain elements",
                    },
                ),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }
    
    def __init__(self):
        self.api_base_url = "https://api.lumalabs.ai/v1"
        self.api_key = None
        
    def _get_api_key(self):
        """Get the Luma API key from environment variable"""
        if self.api_key is None:
            self.api_key = os.getenv("LUMA_API_KEY")
            if not self.api_key:
                raise ValueError("LUMA_API_KEY environment variable not set. Please set your Luma API key.")
        return self.api_key
    
    def _generate_image(self, prompt: str, model: str, aspect_ratio: str, 
                       seed: int, negative_prompt: str = "") -> dict:
        """Make the API call to Luma for image generation"""
        try:
            headers = {
                "Authorization": f"Bearer {self._get_api_key()}",
                "Content-Type": "application/json"
            }
            
            # Prepare the request payload
            payload = {
                "prompt": prompt,
                "model": model,
                "aspect_ratio": aspect_ratio,
                "seed": seed,
                "negative_prompt": negative_prompt,
                "num_images": 1
            }
            
            # Make the API call
            response = requests.post(
                f"{self.api_base_url}/images/generations",
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            raise RuntimeError(f"Error calling Luma API: {e}") from e
    
    def _poll_for_completion(self, task_id: str) -> dict:
        """Poll the task status until completion"""
        max_attempts = 60  # 5 minutes with 5-second intervals
        attempt = 0
        
        while attempt < max_attempts:
            try:
                headers = {
                    "Authorization": f"Bearer {self._get_api_key()}",
                }
                
                response = requests.get(
                    f"{self.api_base_url}/images/generations/{task_id}",
                    headers=headers,
                    timeout=10
                )
                response.raise_for_status()
                
                task_data = response.json()
                status = task_data.get("status")
                
                if status == "completed":
                    return task_data
                elif status in ["failed", "cancelled"]:
                    raise RuntimeError(f"Task failed with status: {status}")
                
                # Wait before next poll (using proper delay for polling)
                time.sleep(5)
                attempt += 1
                
            except requests.RequestException as e:
                attempt += 1
                if attempt >= max_attempts:
                    raise RuntimeError(f"Error polling task status: {e}") from e
                time.sleep(5)
        
        raise TimeoutError("Task timed out")
    
    def _download_image(self, image_url: str) -> torch.Tensor:
        """Download image from URL and convert to tensor"""
        try:
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Convert to PIL Image
            image = Image.open(BytesIO(response.content))
            
            # Convert to RGB if needed
            if image.mode != "RGB":
                image = image.convert("RGB")
            
            # Convert to numpy array and ensure dtype is uint8
            image_array = np.array(image).astype(np.uint8)
            
            # Convert to tensor (H, W, C) -> (C, H, W)
            image_tensor = torch.from_numpy(image_array).permute(2, 0, 1).float()
            
            # Normalize to [0, 1]
            image_tensor = image_tensor / 255.0
            
            # Add batch dimension
            image_tensor = image_tensor.unsqueeze(0)
            
            return image_tensor
            
        except requests.RequestException as e:
            raise RuntimeError(f"Error downloading image: {e}") from e
    
    def generate_image(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str,
        seed: int,
        negative_prompt: str = "",
        unique_id: Optional[str] = None,
        **kwargs
    ) -> tuple[torch.Tensor]:
        """
        Generate an image from text prompt using Luma API
        
        Args:
            prompt: Text description of the image to generate
            model: Luma AI model to use
            aspect_ratio: Aspect ratio of the output image
            seed: Random seed for reproducible results
            negative_prompt: Negative prompt to avoid certain elements
            unique_id: Unique node ID for progress tracking
            
        Returns:
            Generated image as tensor
        """
        try:
            # Validate inputs
            if not prompt.strip():
                raise ValueError("Prompt cannot be empty")
            
            # Generate image
            generation_response = self._generate_image(
                prompt=prompt,
                model=model,
                aspect_ratio=aspect_ratio,
                seed=seed,
                negative_prompt=negative_prompt
            )
            
            # Get the task ID
            task_id = generation_response.get("id")
            if not task_id:
                raise RuntimeError("No task ID received from API")
            
            # Poll for completion
            final_result = self._poll_for_completion(task_id)
            
            # Extract image URL
            images = final_result.get("images", [])
            if not images:
                raise RuntimeError("No images in response")
            
            image_url = images[0].get("url")
            if not image_url:
                raise RuntimeError("No image URL in response")
            
            # Download and convert to tensor
            image_tensor = self._download_image(image_url)
            
            return (image_tensor,)
            
        except Exception as e:
            raise RuntimeError(f"Error in generate_image: {e}") from e


# Node class mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "LumaTextToImage": LumaTextToImageNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LumaTextToImage": "Luma: Text to Image",
} 