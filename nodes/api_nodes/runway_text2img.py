import os
import time
import requests
from PIL import Image
from io import BytesIO

class RunwayTextToImage:
    """
    A ComfyUI-compatible node that generates an image from a text prompt
    using Runway's /v1/text_to_image API.

    Attributes:
        prompt (str): The text description to generate an image from.
        timeout (int): Maximum time (in seconds) to wait while polling the image URL. Default is 10 seconds.

    Raises:
        RuntimeError: 
            - If the RUNWAY_API_KEY environment variable is not set.
            - If the API response is invalid or an error occurs during polling.

    Environment Variables:
        RUNWAY_API_KEY (str): Required API key for authenticating with RunwayML.

    Example:
        >>> node = RunwayTextToImage(prompt="a futuristic cityscape", timeout=15)
        >>> image = node.run()
        >>> image.show()

    Notes:
        - If the API key is missing, a clear error will be raised without crashing the program.
        - To increase or decrease wait time for image generation, adjust the `timeout` parameter.
    """

    def __init__(self, prompt: str, timeout: int = 10):
        self.prompt = prompt
        self.timeout = timeout

    def run(self) -> Image.Image:
        api_key = os.getenv("RUNWAY_API_KEY")
        if not api_key:
            raise RuntimeError("RUNWAY_API_KEY is not set in environment variables.")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "prompt": self.prompt
        }

        # Step 1: Send POST request to initiate generation
        response = requests.post(
            "https://api.dev.runwayml.com/v1/text_to_image",
            json=payload,
            headers=headers
        )

        if response.status_code != 200:
            raise RuntimeError(f"API request failed with status {response.status_code}: {response.text}")

        data = response.json()
        image_url = data.get("image_url")
        if not image_url:
            raise RuntimeError("API response does not contain 'image_url'.")

        # Step 2: Poll the image URL until image is ready or timeout is reached
        start_time = time.time()
        image_data = None

        while time.time() - start_time < self.timeout:
            img_response = requests.get(image_url)
            if img_response.status_code == 200 and img_response.content:
                image_data = img_response.content
                break
            time.sleep(1)  # Polling interval

        if not image_data:
            raise RuntimeError("Failed to fetch image data within timeout period.")

        # Step 3: Load image from bytes into PIL.Image
        return Image.open(BytesIO(image_data))
