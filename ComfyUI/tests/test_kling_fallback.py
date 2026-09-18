import pytest
import logging
from unittest.mock import Mock, patch, MagicMock
import sys
import os

from io import BytesIO
import numpy as np

from comfy_api_nodes.nodes_kling import KlingGenerate, ComfyUIWarning


@pytest.fixture
def square_dimensions():
    """
    Returns a (256, 256) tuple simulating a square size.
    """
    return (256, 256)


@pytest.fixture
def nonsquare_dimensions():
    """
     Returns a (256, 720) tuple simulating a non-square size.
    """
    return (256, 720)



def test_missing_api_key(monkeypatch, dummy_image):
    """
    Test that the node raises a clear error when LUMA_API_KEY is missing.
    """
    node = KlingGenerate()

    assert (256, 256) == node._handle_resolution_fallback(square_dimensions[0], square_dimensions[1],  "test_node_id")

    with pytest.raises(Exception) as exc:
        node._handle_resolution_fallback(nonsquare_dimensions[0], nonsquare_dimensions[1], "test_node_id")

    assert "ComfyUI" in str(exc.value)


