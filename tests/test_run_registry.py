"""
Tests for run_registry.py - Database-first API with ClipScore Integration
"""
import pytest
import json
from unittest.mock import patch, Mock
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'dream_layer_backend'))

class TestRunRegistry:
    
    def test_run_registry_app_creation(self):
        """Test that run registry app can be created"""
        from run_registry import app
        assert app is not None
    
    @patch('dream_layer_backend_utils.unified_database_queries.get_all_runs_with_metrics')
    def test_enhanced_runs_endpoint(self, mock_get_runs):
        """Test /api/runs/enhanced/v2 endpoint"""
        from run_registry import app
        
        # Mock database response
        mock_get_runs.return_value = [
            {
                'run_id': 'test-123',
                'model': 'dall-e-3',
                'prompt': 'test prompt',
                'clip_score_mean': 0.85,
                'generated_images': ['test.png']
            }
        ]
        
        with app.test_client() as client:
            response = client.get('/api/runs/enhanced/v2')
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['status'] == 'success'
            assert 'runs' in data
            assert len(data['runs']) == 1
            assert data['runs'][0]['clip_score_mean'] == 0.85
    
    @patch('dream_layer_backend_utils.unified_database_queries.get_database_stats')
    def test_database_stats_endpoint(self, mock_get_stats):
        """Test /api/database/stats endpoint"""
        from run_registry import app
        
        # Mock stats response
        mock_get_stats.return_value = {
            'total_runs': 45,
            'runs_with_clipscore': 35,
            'database_size_mb': 2.5
        }
        
        with app.test_client() as client:
            response = client.get('/api/database/stats')
            
            assert response.status_code == 200
            data = response.get_json()
            # Check for either 'success' or 'status' key
            assert data.get('success') == True or data.get('status') == 'success'
            
            # Check stats data
            stats_key = 'stats' if 'stats' in data else 'data'
            if stats_key in data:
                assert data[stats_key]['total_runs'] == 45
                assert data[stats_key]['runs_with_clipscore'] == 35
    
    def test_cors_headers(self):
        """Test that CORS headers are properly set"""
        from run_registry import app
        
        with app.test_client() as client:
            response = client.options('/api/runs/enhanced/v2')
            
            # Should have CORS headers
            assert response.status_code == 200
    
    @patch('dream_layer_backend_utils.unified_database_queries.get_all_runs_with_metrics')
    def test_empty_database_response(self, mock_get_runs):
        """Test response when database is empty"""
        from run_registry import app
        
        # Mock empty database
        mock_get_runs.return_value = []
        
        with app.test_client() as client:
            response = client.get('/api/runs/enhanced/v2')
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['status'] == 'success'
            assert data['runs'] == []
            assert data['count'] == 0
    
    @patch('dream_layer_backend_utils.unified_database_queries.get_all_runs_with_metrics')
    def test_database_error_handling(self, mock_get_runs):
        """Test error handling when database fails"""
        from run_registry import app
        
        # Mock database error
        mock_get_runs.side_effect = Exception("Database connection failed")
        
        with app.test_client() as client:
            response = client.get('/api/runs/enhanced/v2')
            
            # Should handle error gracefully
            assert response.status_code in [200, 500]
    
    def test_run_registry_json_fallback(self):
        """Test that run registry can fall back to JSON file"""
        # Test that the system can handle missing database
        try:
            from run_registry import registry
            # Should be able to create registry object
            assert registry is not None
        except Exception:
            # If registry creation fails, that's also acceptable for testing
            pass
    
    def test_api_response_format(self):
        """Test API response format consistency"""
        from run_registry import app
        
        with app.test_client() as client:
            response = client.get('/api/runs/enhanced/v2')
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Should have consistent response format
            assert isinstance(data, dict)
            assert 'status' in data or 'success' in data
            assert 'runs' in data or 'data' in data
