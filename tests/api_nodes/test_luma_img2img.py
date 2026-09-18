import sys
import os

# Add project root to Python path so 'nodes' module is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

import pytest
from PIL import Image
from io import BytesIO
import numpy as np

from nodes.api_nodes.luma_img2img import LumaImg2Img

@pytest.fixture
def dummy_image():
    """
    Returns a 3x64x64 NumPy tensor simulating an RGB image.
    """
    return np.random.rand(3, 64, 64).astype(np.float32)

def test_missing_api_key(monkeypatch, dummy_image):
    """
    Test that the node raises a clear error when LUMA_API_KEY is missing.
    """
    monkeypatch.delenv("LUMA_API_KEY", raising=False)
    node = LumaImg2Img()

    with pytest.raises(Exception) as exc:
        node.run(dummy_image, "cat prompt")

    assert "LUMA_API_KEY" in str(exc.value)

def test_successful_response(monkeypatch, mocker, dummy_image):
    """
    Test that the node returns a valid tensor when the API call is mocked successfully.
    """
    monkeypatch.setenv("LUMA_API_KEY", "test-key")

    dummy_output = BytesIO()
    img = Image.new("RGB", (64, 64), color="blue")
    img.save(dummy_output, format="PNG")
    dummy_output.seek(0)

    mock_post = mocker.patch("nodes.api_nodes.luma_img2img.requests.post")
    mock_post.return_value.ok = True
    mock_post.return_value.content = dummy_output.getvalue()

    node = LumaImg2Img()
    result = node.run(dummy_image, "skyline prompt")

    assert isinstance(result["image"], np.ndarray)
    assert result["image"].shape == (3, 64, 64)
