import sys
import os
import io
import base64
import pytest
from unittest.mock import patch, MagicMock

# Allow import of api_nodes from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from api_nodes.runway_text2img import RunwayText2Image
from PIL import Image

# Helper: create a mock base64 image
def mock_image_base64():
    img = Image.new("RGB", (64, 64), color=(255, 0, 0))  # Red square
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

@patch("requests.post")
def test_runway_text2img_success(mock_post):
    # Mock API response
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "image": mock_image_base64()
    }
    mock_post.return_value = fake_response

    # Set fake API key
    os.environ["RUNWAY_API_KEY"] = "test123"

    node = RunwayText2Image()
    result = node.runway_generate("a cute robot")

    assert result is not None
    assert isinstance(result[0], Image.Image)
    assert result[0].size == (64, 64)

@patch("requests.post")
def test_runway_text2img_no_key(mock_post):
    # Remove API key if it exists
    os.environ.pop("RUNWAY_API_KEY", None)

    node = RunwayText2Image()
    with pytest.raises(RuntimeError, match="RUNWAY_API_KEY not found"):
        node.runway_generate("test prompt")
