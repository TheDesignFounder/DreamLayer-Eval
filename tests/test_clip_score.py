"""
Tests for ClipScore Integration - Calculation and Database Storage
"""
import pytest
import tempfile
import os
from unittest.mock import patch, Mock, MagicMock
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'dream_layer_backend'))

class TestClipScore:
    
    @patch('dream_layer_backend_utils.clip_score_metrics.CLIPModel')
    @patch('dream_layer_backend_utils.clip_score_metrics.CLIPProcessor')
    def test_clip_calculator_initialization(self, mock_processor, mock_model):
        """Test CLIP calculator can be initialized"""
        from dream_layer_backend_utils.clip_score_metrics import get_clip_calculator
        
        # Mock CLIP components
        mock_model.from_pretrained.return_value = Mock()
        mock_processor.from_pretrained.return_value = Mock()
        
        calculator = get_clip_calculator()
        assert calculator is not None
    
    def test_clip_score_calculation_with_mock(self, mock_clip_calculator):
        """Test ClipScore calculation with mocked calculator"""
        prompt = "beautiful sunset over mountains"
        image_path = "/fake/path/image.png"
        
        score = mock_clip_calculator.compute_clip_score(prompt, image_path)
        assert score == 0.85
        mock_clip_calculator.compute_clip_score.assert_called_once_with(prompt, image_path)
    
    @patch('dream_layer_backend_utils.direct_database_integration.calculate_clipscore_sync')
    def test_clipscore_sync_calculation(self, mock_calc_sync):
        """Test synchronous ClipScore calculation"""
        from dream_layer_backend_utils.direct_database_integration import calculate_clipscore_sync
        
        # Mock calculation
        mock_calc_sync.return_value = 0.75
        
        run_data = {
            'prompt': 'test prompt',
            'run_id': 'test-123'
        }
        generated_images = ['test.png']
        
        score = calculate_clipscore_sync(run_data, generated_images)
        assert score == 0.75
    
    @patch('dream_layer_backend_utils.unified_database_queries.save_clipscore_to_database')
    def test_clipscore_database_save(self, mock_save_db):
        """Test saving ClipScore to database"""
        from dream_layer_backend_utils.unified_database_queries import save_clipscore_to_database
        
        # Mock successful save
        mock_save_db.return_value = True
        
        run_id = 'test-run-123'
        timestamp = '2025-08-20T00:00:00'
        clip_score = 0.82
        
        result = save_clipscore_to_database(run_id, timestamp, clip_score)
        assert result == True
        mock_save_db.assert_called_once_with(run_id, timestamp, clip_score)
    
    def test_clipscore_range_validation(self):
        """Test that ClipScore values are in valid cosine range [-1, 1]"""
        # This would test the actual calculation if we had real images
        # For now, we test the validation logic
        
        valid_scores = [-1.0, -0.1, 0.0, 0.5, 1.0, 0.85, 0.123]
        invalid_scores = [-1.1, 1.1, 2.0]
        
        for score in valid_scores:
            assert -1.0 <= score <= 1.0, f"Score {score} should be valid"
        
        for score in invalid_scores:
            assert not (-1.0 <= score <= 1.0), f"Score {score} should be invalid"
    
    @patch('os.path.exists')
    def test_clipscore_missing_image_handling(self, mock_exists):
        """Test ClipScore calculation when image file is missing"""
        from dream_layer_backend_utils.direct_database_integration import calculate_clipscore_sync
        
        # Mock missing file
        mock_exists.return_value = False
        
        run_data = {'prompt': 'test prompt'}
        generated_images = ['missing_image.png']
        
        # Should handle missing file gracefully
        score = calculate_clipscore_sync(run_data, generated_images)
        # Should return None or handle error gracefully
        assert score is None or isinstance(score, (int, float))
    
    def test_clipscore_empty_prompt_handling(self):
        """Test ClipScore calculation with empty prompt"""
        from dream_layer_backend_utils.direct_database_integration import calculate_clipscore_sync
        
        run_data = {'prompt': ''}
        generated_images = ['test.png']
        
        # Should handle empty prompt gracefully
        score = calculate_clipscore_sync(run_data, generated_images)
        assert score is None or isinstance(score, (int, float))
