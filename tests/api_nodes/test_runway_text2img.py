import os
import pytest
from unittest import mock
from unittest.mock import patch

from nodes.api_nodes.runway_text2img import RunwayTextToImage

@patch('nodes.api_nodes.runway_text2img.requests.post')
@patch('nodes.api_nodes.runway_text2img.requests.get')
def test_runway_text2img_node(mock_get, mock_post):
    # Set environment variable
    with mock.patch.dict(os.environ, {"RUNWAY_API_KEY": "fake_api_key"}):
        # Mock POST response from API
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "image_url": "http://fakeurl.com/fakeimage.png"
        }

        # Mock GET response with minimal valid PNG bytes
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
            b'\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01'
            b'\xe2!\xbc\x33\x00\x00\x00\x00IEND\xaeB`\x82'
        )

        node = RunwayTextToImage(prompt="A test prompt", timeout=5)

        try:
            result = node.run()
            assert result is not None
        except Exception as e:
            pytest.fail(f"Node run method raised an exception: {e}")
