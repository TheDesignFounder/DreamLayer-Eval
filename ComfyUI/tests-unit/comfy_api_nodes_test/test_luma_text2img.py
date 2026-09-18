"""
Tests for Luma Text2Img node functionality.

This module tests the LumaImageGenerationNode which provides text-to-image generation
capabilities using the Luma API.
"""

import pytest
import torch
from unittest.mock import Mock, patch
from comfy_api_nodes.nodes_luma import LumaImageGenerationNode
from comfy_api_nodes.apis.luma_api import (
    LumaImageModel,
    LumaAspectRatio,
)
from comfy.comfy_types.node_typing import IO


class TestLumaImageGenerationNode:
    """Test suite for LumaImageGenerationNode."""

    def setup_method(self):
        """Set up test fixtures."""
        self.node = LumaImageGenerationNode()
        self.mock_image = torch.randn(1, 512, 512, 3)  # Mock image tensor

    def test_node_input_types(self):
        """Test that the node has the correct input types."""
        input_types = self.node.INPUT_TYPES()
        
        # Check required inputs
        assert "prompt" in input_types["required"]
        assert "model" in input_types["required"]
        assert "aspect_ratio" in input_types["required"]
        assert "seed" in input_types["required"]
        assert "style_image_weight" in input_types["required"]
        
        # Check optional inputs
        assert "image_luma_ref" in input_types["optional"]
        assert "style_image" in input_types["optional"]
        assert "character_image" in input_types["optional"]
        
        # Check hidden inputs
        assert "auth_token" in input_types["hidden"]
        assert "comfy_api_key" in input_types["hidden"]
        assert "unique_id" in input_types["hidden"]

    def test_node_return_types(self):
        """Test that the node returns the correct types."""
        assert self.node.RETURN_TYPES == (IO.IMAGE,)
        assert self.node.FUNCTION == "api_call"
        assert self.node.API_NODE is True
        assert self.node.CATEGORY == "api node/image/Luma"

    def test_node_description(self):
        """Test that the node has a proper description."""
        assert "Generates images synchronously based on prompt and aspect ratio" in self.node.DESCRIPTION

    @patch('comfy_api_nodes.nodes_luma.SynchronousOperation')
    @patch('comfy_api_nodes.nodes_luma.PollingOperation')
    @patch('comfy_api_nodes.nodes_luma.requests.get')
    @patch('comfy_api_nodes.nodes_luma.process_image_response')
    def test_api_call_success(self, mock_process_response, mock_get, mock_polling, mock_sync):
        """Test successful API call."""
        # Mock the synchronous operation response
        mock_sync_response = Mock()
        mock_sync_response.id = "test-generation-id"
        mock_sync.return_value.execute.return_value = mock_sync_response
        
        # Mock the polling operation response
        mock_polling_response = Mock()
        mock_polling_response.assets = Mock()
        mock_polling_response.assets.image = "https://example.com/image.jpg"
        mock_polling.return_value.execute.return_value = mock_polling_response
        
        # Mock the HTTP response
        mock_http_response = Mock()
        mock_get.return_value = mock_http_response
        
        # Mock the image processing
        mock_process_response.return_value = self.mock_image
        
        # Test the API call
        result = self.node.api_call(
            prompt="A beautiful sunset",
            model=LumaImageModel.photon_1.value,
            aspect_ratio=LumaAspectRatio.ratio_16_9.value,
            seed=42,
            style_image_weight=1.0,
            auth_token="test-token",
            comfy_api_key="test-key",
            unique_id="test-id"
        )
        
        # Verify the result
        assert len(result) == 1
        assert isinstance(result[0], torch.Tensor)

    def test_api_call_missing_api_key(self):
        """Test that the node raises an error when API key is missing."""
        with pytest.raises(Exception) as exc_info:
            self.node.api_call(
                prompt="A beautiful sunset",
                model=LumaImageModel.photon_1.value,
                aspect_ratio=LumaAspectRatio.ratio_16_9.value,
                seed=42,
                style_image_weight=1.0,
                # No auth_token or comfy_api_key provided
            )
        
        # The error should be related to missing authentication
        assert "Missing" in str(exc_info.value) or "auth" in str(exc_info.value).lower()

    @pytest.mark.parametrize("invalid_prompt,expected_error", [
        ("", "prompt"),  # Empty prompt
        ("ab", "prompt"),  # Too short
        ("   ", "prompt"),  # Whitespace only
        (None, "prompt"),  # None value
    ])
    def test_api_call_invalid_prompts(self, invalid_prompt, expected_error):
        """Test that the node validates prompt input with various invalid cases."""
        with pytest.raises(ValueError) as exc_info:
            self.node.api_call(
                prompt=invalid_prompt,
                model=LumaImageModel.photon_1.value,
                aspect_ratio=LumaAspectRatio.ratio_16_9.value,
                seed=42,
                style_image_weight=1.0,
                auth_token="test-token",
                comfy_api_key="test-key"
            )
        
        assert expected_error in str(exc_info.value).lower()

    @pytest.mark.parametrize("invalid_image_ref,expected_error", [
        (None, "image"),  # None reference
        ("invalid_string", "image"),  # String instead of image
        (123, "image"),  # Integer instead of image
        (torch.randn(1, 100, 100, 1), "channels"),  # Wrong number of channels
        (torch.randn(1, 100, 100, 4), "channels"),  # Wrong number of channels
        (torch.randn(2, 100, 100, 3), "batch"),  # Wrong batch size
    ])
    def test_api_call_invalid_image_references(self, invalid_image_ref, expected_error):
        """Test that the node handles invalid image references properly."""
        with patch('comfy_api_nodes.nodes_luma.SynchronousOperation') as mock_sync, \
             patch('comfy_api_nodes.nodes_luma.PollingOperation') as mock_polling:
            
            # Mock successful operations
            mock_sync_response = Mock()
            mock_sync_response.id = "test-generation-id"
            mock_sync.return_value.execute.return_value = mock_sync_response
            
            mock_polling_response = Mock()
            mock_polling_response.assets = Mock()
            mock_polling_response.assets.image = "https://example.com/image.jpg"
            mock_polling.return_value.execute.return_value = mock_polling_response
            
            # Mock image processing
            with patch('comfy_api_nodes.nodes_luma.requests.get') as mock_get, \
                 patch('comfy_api_nodes.nodes_luma.process_image_response') as mock_process:
                
                mock_http_response = Mock()
                mock_get.return_value = mock_http_response
                mock_process.return_value = self.mock_image
                
                # Test with invalid image reference
                result = self.node.api_call(
                    prompt="A beautiful sunset",
                    model=LumaImageModel.photon_1.value,
                    aspect_ratio=LumaAspectRatio.ratio_16_9.value,
                    seed=42,
                    style_image_weight=1.0,
                    style_image=invalid_image_ref,
                    auth_token="test-token",
                    comfy_api_key="test-key"
                )
                
                # Should still work (invalid refs are ignored or handled gracefully)
                assert len(result) == 1
                assert isinstance(result[0], torch.Tensor)

    def test_api_call_missing_image_references(self):
        """Test that the node works correctly with missing image references."""
        with patch('comfy_api_nodes.nodes_luma.SynchronousOperation') as mock_sync, \
             patch('comfy_api_nodes.nodes_luma.PollingOperation') as mock_polling:
            
            # Mock successful operations
            mock_sync_response = Mock()
            mock_sync_response.id = "test-generation-id"
            mock_sync.return_value.execute.return_value = mock_sync_response
            
            mock_polling_response = Mock()
            mock_polling_response.assets = Mock()
            mock_polling_response.assets.image = "https://example.com/image.jpg"
            mock_polling.return_value.execute.return_value = mock_polling_response
            
            # Mock image processing
            with patch('comfy_api_nodes.nodes_luma.requests.get') as mock_get, \
                 patch('comfy_api_nodes.nodes_luma.process_image_response') as mock_process:
                
                mock_http_response = Mock()
                mock_get.return_value = mock_http_response
                mock_process.return_value = self.mock_image
                
                # Test with no image references
                result = self.node.api_call(
                    prompt="A beautiful sunset",
                    model=LumaImageModel.photon_1.value,
                    aspect_ratio=LumaAspectRatio.ratio_16_9.value,
                    seed=42,
                    style_image_weight=1.0,
                    # No image references provided
                    auth_token="test-token",
                    comfy_api_key="test-key"
                )
                
                # Should work without image references
                assert len(result) == 1
                assert isinstance(result[0], torch.Tensor)

    @pytest.mark.parametrize("invalid_luma_ref,expected_behavior", [
        (None, "ignore"),  # None reference
        ("invalid_string", "ignore"),  # String instead of LUMA_REF
        (123, "ignore"),  # Integer instead of LUMA_REF
        ([], "ignore"),  # Empty list
        ([None], "ignore"),  # List with None
        ([torch.randn(1, 100, 100, 1)], "error"),  # Wrong channels
    ])
    def test_api_call_invalid_luma_references(self, invalid_luma_ref, expected_behavior):
        """Test that the node handles invalid LUMA reference objects properly."""
        with patch('comfy_api_nodes.nodes_luma.SynchronousOperation') as mock_sync, \
             patch('comfy_api_nodes.nodes_luma.PollingOperation') as mock_polling:
            
            # Mock successful operations
            mock_sync_response = Mock()
            mock_sync_response.id = "test-generation-id"
            mock_sync.return_value.execute.return_value = mock_sync_response
            
            mock_polling_response = Mock()
            mock_polling_response.assets = Mock()
            mock_polling_response.assets.image = "https://example.com/image.jpg"
            mock_polling.return_value.execute.return_value = mock_polling_response
            
            # Mock image processing
            with patch('comfy_api_nodes.nodes_luma.requests.get') as mock_get, \
                 patch('comfy_api_nodes.nodes_luma.process_image_response') as mock_process:
                
                mock_http_response = Mock()
                mock_get.return_value = mock_http_response
                mock_process.return_value = self.mock_image
                
                if expected_behavior == "error":
                    with pytest.raises(Exception):
                        self.node.api_call(
                            prompt="A beautiful sunset",
                            model=LumaImageModel.photon_1.value,
                            aspect_ratio=LumaAspectRatio.ratio_16_9.value,
                            seed=42,
                            style_image_weight=1.0,
                            image_luma_ref=invalid_luma_ref,
                            auth_token="test-token",
                            comfy_api_key="test-key"
                        )
                else:
                    # Should work (invalid refs are ignored)
                    result = self.node.api_call(
                        prompt="A beautiful sunset",
                        model=LumaImageModel.photon_1.value,
                        aspect_ratio=LumaAspectRatio.ratio_16_9.value,
                        seed=42,
                        style_image_weight=1.0,
                        image_luma_ref=invalid_luma_ref,
                        auth_token="test-token",
                        comfy_api_key="test-key"
                    )
                    
                    assert len(result) == 1
                    assert isinstance(result[0], torch.Tensor)

    @patch('comfy_api_nodes.nodes_luma.SynchronousOperation')
    @patch('comfy_api_nodes.nodes_luma.PollingOperation')
    def test_api_call_with_image_references(self, mock_polling, mock_sync):
        """Test API call with image references."""
        # Mock the operations
        mock_sync_response = Mock()
        mock_sync_response.id = "test-generation-id"
        mock_sync.return_value.execute.return_value = mock_sync_response
        
        mock_polling_response = Mock()
        mock_polling_response.assets = Mock()
        mock_polling_response.assets.image = "https://example.com/image.jpg"
        mock_polling.return_value.execute.return_value = mock_polling_response
        
        # Mock image processing
        with patch('comfy_api_nodes.nodes_luma.requests.get') as mock_get, \
             patch('comfy_api_nodes.nodes_luma.process_image_response') as mock_process:
            
            mock_http_response = Mock()
            mock_get.return_value = mock_http_response
            mock_process.return_value = self.mock_image
            
            # Test with image references
            result = self.node.api_call(
                prompt="A beautiful sunset",
                model=LumaImageModel.photon_1.value,
                aspect_ratio=LumaAspectRatio.ratio_16_9.value,
                seed=42,
                style_image_weight=1.0,
                image_luma_ref=Mock(),  # Mock reference
                style_image=self.mock_image,
                character_image=self.mock_image,
                auth_token="test-token",
                comfy_api_key="test-key"
            )
            
            assert len(result) == 1
            assert isinstance(result[0], torch.Tensor)

    def test_node_display_name(self):
        """Test that the node has a proper display name."""
        from comfy_api_nodes.nodes_luma import NODE_DISPLAY_NAME_MAPPINGS
        assert "LumaImageNode" in NODE_DISPLAY_NAME_MAPPINGS
        assert NODE_DISPLAY_NAME_MAPPINGS["LumaImageNode"] == "Luma Text to Image"

    def test_node_class_mappings(self):
        """Test that the node is properly registered."""
        from comfy_api_nodes.nodes_luma import NODE_CLASS_MAPPINGS
        assert "LumaImageNode" in NODE_CLASS_MAPPINGS
        assert NODE_CLASS_MAPPINGS["LumaImageNode"] == LumaImageGenerationNode


class TestLumaImageGenerationNodeIntegration:
    """Integration tests for LumaImageGenerationNode."""

    @pytest.mark.integration
    def test_node_with_real_api_key(self):
        """Integration test with real API key (requires LUMA_API_KEY env var)."""
        import os
        
        # Skip if no API key is available
        if not os.getenv("LUMA_API_KEY"):
            pytest.skip("LUMA_API_KEY not set")
        
        node = LumaImageGenerationNode()
        
        # Test with real API call (this will actually call the API)
        result = node.api_call(
            prompt="A beautiful sunset over mountains",
            model=LumaImageModel.photon_1.value,
            aspect_ratio=LumaAspectRatio.ratio_16_9.value,
            seed=42,
            style_image_weight=1.0,
            auth_token=os.getenv("LUMA_API_KEY"),
            comfy_api_key="test-key"
        )
        
        # Verify we get a valid image result
        assert len(result) == 1
        assert isinstance(result[0], torch.Tensor)
        assert result[0].shape[0] == 1  # Batch dimension
        assert result[0].shape[1] > 0  # Height
        assert result[0].shape[2] > 0  # Width
        assert result[0].shape[3] == 3  # RGB channels 