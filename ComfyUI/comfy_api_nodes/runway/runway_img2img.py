import os  # Used to access environment variables like the API key
import requests  # For making HTTP requests

class RunwayImg2Img:
    def __init__(self, timeout=30):
        # Load API key from environment variable; required for authenticating with Runway API
        self.api_key = os.environ.get("RUNWAY_API_KEY")
        if not self.api_key:
            # Raise an error early if the key is missing to avoid silent failures later
            raise EnvironmentError("Missing RUNWAY_API_KEY in environment variables.")
        self.timeout = timeout  # Max duration (in seconds) to wait for the API response

    def process(self, input_image, prompt):
        """
        Args:
            input_image (str): Path to the input image (will be read as binary).
            prompt (str): A text prompt to guide the image generation.

        Returns:
            dict: JSON response from the Runway API.

        Raises:
            EnvironmentError: If RUNWAY_API_KEY is missing.
            requests.HTTPError: For API call errors.
            ValueError: If input parameters are invalid.
            FileNotFoundError: If input image file doesn't exist.
        """
        # Input validation
        if not input_image or not isinstance(input_image, str):
            raise ValueError("input_image must be a non-empty string path")
        if not prompt or not isinstance(prompt, str):
            raise ValueError("prompt must be a non-empty string")
        if not os.path.exists(input_image):
            raise FileNotFoundError(f"Input image not found: {input_image}")

        # Open the image file in binary mode to send as 'promptImage' in multipart/form-data
        with open(input_image, "rb") as f:
            files = {"promptImage": f}  # The expected key for the image in Runway's API

            # Authorization and version headers required by Runway API
            headers = {
                "Authorization": f"Bearer {self.api_key}",  # Include API key securely in the request
                "X-Runway-Version": os.getenv("RUNWAY_API_VERSION", "2024-11-06")  # Specific API version to ensure compatibility
            }

            # Prompt payload that guides image generation
            data = {"prompt": prompt}

            # Send POST request to Runway's text-to-image endpoint
            response = requests.post(
                "https://api.runwayml.com/v1/text_to_image",
                headers=headers,
                files=files,  # multipart/form-data with binary image
                data=data,    # form-encoded text fields
                timeout=self.timeout  # timeout to prevent hanging on slow networks
            )

            # Raise exception if response status code is not 2xx
            response.raise_for_status()

            # Return JSON response (e.g., status or URL of generated image)
            return response.json()
