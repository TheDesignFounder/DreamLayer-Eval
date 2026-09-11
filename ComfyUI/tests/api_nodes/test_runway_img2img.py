import os  # Used to set or delete the RUNWAY_API_KEY environment variable
import pytest  # Provides tools like `raises()` for asserting exceptions
import requests  # For HTTP error types
from unittest.mock import patch, mock_open  # Used to mock file handling and HTTP requests

# Import the class you're testing
from comfy_api_nodes.runway.runway_img2img import RunwayImg2Img


# Test that the node works properly when the API call succeeds
@patch("os.path.exists", return_value=True)  # Mock file existence check
@patch("builtins.open", new_callable=mock_open, read_data=b"image bytes")  # Mocks file open call
@patch("requests.post")  # Mocks the HTTP POST request to Runway API
def test_runway_node_process(mock_post, mock_file, mock_exists):
    # Simulate a successful API response with status code 200 and JSON body
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"status": "success"}

    # Set a fake API key to satisfy the environment check
    os.environ["RUNWAY_API_KEY"] = "fake-key"

    try:
        # Initialize and call the node
        node = RunwayImg2Img()
        result = node.process("image.png", "a prompt")

        # Assert that the response JSON matches the mocked response
        assert result["status"] == "success"
    finally:
        # Clean up environment variable
        if "RUNWAY_API_KEY" in os.environ:
            del os.environ["RUNWAY_API_KEY"]


# Test that an appropriate error is raised when the API key is missing
def test_missing_api_key():
    # Ensure the environment variable is not set
    if "RUNWAY_API_KEY" in os.environ:
        del os.environ["RUNWAY_API_KEY"]

    # Check that initializing the node raises an EnvironmentError
    with pytest.raises(EnvironmentError, match="Missing RUNWAY_API_KEY"):
        RunwayImg2Img()


@patch("os.path.exists", return_value=True)  # Mock file existence check
@patch("builtins.open", new_callable=mock_open, read_data=b"image bytes")
@patch("requests.post")
def test_runway_node_http_error(mock_post, mock_file, mock_exists):
    """Test that HTTP errors are properly raised."""
    mock_post.return_value.raise_for_status.side_effect = requests.HTTPError("API Error")
    
    os.environ["RUNWAY_API_KEY"] = "fake-key"
    
    try:
        node = RunwayImg2Img()
        with pytest.raises(requests.HTTPError):
            node.process("image.png", "a prompt")
    finally:
        if "RUNWAY_API_KEY" in os.environ:
            del os.environ["RUNWAY_API_KEY"]


@patch("requests.post")
def test_runway_node_file_not_found(mock_post):
    """Test that FileNotFoundError is raised for missing files."""
    os.environ["RUNWAY_API_KEY"] = "fake-key"
    
    try:
        node = RunwayImg2Img()
        with pytest.raises(FileNotFoundError):
            node.process("nonexistent.png", "a prompt")
    finally:
        if "RUNWAY_API_KEY" in os.environ:
            del os.environ["RUNWAY_API_KEY"]


@patch("os.path.exists", return_value=True)  # Mock file existence check
@patch("builtins.open", new_callable=mock_open, read_data=b"image bytes")
@patch("requests.post")
def test_runway_node_timeout(mock_post, mock_file, mock_exists):
    """Test that timeout errors are handled properly."""
    mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

    os.environ["RUNWAY_API_KEY"] = "fake-key"

    try:
        node = RunwayImg2Img(timeout=1)
        with pytest.raises(requests.exceptions.Timeout):
            node.process("image.png", "a prompt")
    finally:
        if "RUNWAY_API_KEY" in os.environ:
            del os.environ["RUNWAY_API_KEY"]


def test_invalid_input_parameters():
    """Test that invalid input parameters raise appropriate errors."""
    os.environ["RUNWAY_API_KEY"] = "fake-key"
    
    try:
        node = RunwayImg2Img()
        
        # Test invalid input_image
        with pytest.raises(ValueError, match="input_image must be a non-empty string path"):
            node.process("", "a prompt")
        
        with pytest.raises(ValueError, match="input_image must be a non-empty string path"):
            node.process(None, "a prompt")
        
        # Test invalid prompt
        with pytest.raises(ValueError, match="prompt must be a non-empty string"):
            node.process("image.png", "")
        
        with pytest.raises(ValueError, match="prompt must be a non-empty string"):
            node.process("image.png", None)
    finally:
        if "RUNWAY_API_KEY" in os.environ:
            del os.environ["RUNWAY_API_KEY"]
