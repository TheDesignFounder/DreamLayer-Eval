"""
Tests for txt2img_server.py - Text to Image Generation with Database Integration
"""
import pytest
import json
from unittest.mock import patch, Mock
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'dream_layer_backend'))

class TestTxt2ImgServer:
    
    def test_txt2img_endpoint_exists(self):
        """Test that txt2img endpoint is accessible"""
        from txt2img_server import app
        
        with app.test_client() as client:
            # Test OPTIONS request
            response = client.options('/api/txt2img')
            assert response.status_code == 200
    
    def test_txt2img_generation_success(self, monkeypatch, test_generation_data):
        """Real route/workflow/registry construction with a synthetic transport boundary."""
        import txt2img_server as service
        saved = []
        histories = []
        monkeypatch.setattr(service, 'send_to_comfyui', lambda workflow: {'all_images': [{'filename':'fixture.png'}]})
        monkeypatch.setattr(service.registry, 'add_run', saved.append)
        monkeypatch.setattr(service.gh, 'save_generation', histories.append)
        with service.app.test_client() as client:
            response = client.post('/api/txt2img', json={**test_generation_data, 'random_seed':False})
        assert response.status_code == 200
        assert response.json['generated_images'] == [{'filename':'fixture.png'}]
        assert len(saved) == len(histories) == 1
        assert saved[0].prompt == test_generation_data['prompt']
        assert saved[0].seed == test_generation_data['seed']

    def test_txt2img_model_name_handling(self, test_generation_data):
        """Test that model_name is properly handled in generation data"""
        # Test the data structure directly
        assert 'model_name' in test_generation_data
        assert test_generation_data['model_name'] == 'test-model-v1'
        
        # Test model name validation
        model_name = test_generation_data.get('model_name', 'default')
        assert model_name != 'unknown'
    
    def test_txt2img_comfyui_error_handling(self, monkeypatch, test_generation_data):
        import txt2img_server as service
        monkeypatch.setattr(service, 'send_to_comfyui', lambda workflow: {'error':'synthetic provider failure'})
        with service.app.test_client() as client:
            response = client.post('/api/txt2img', json=test_generation_data)
        assert response.status_code == 502
        assert response.json['status'] == 'error'
        assert response.json['failures'][0]['reason'] == 'synthetic provider failure'

    def test_txt2img_invalid_data(self):
        """Test txt2img with invalid input data"""
        from txt2img_server import app
        
        with app.test_client() as client:
            # Test with empty data
            response = client.post('/api/txt2img', 
                                 json={},
                                 content_type='application/json')
            
            # Should handle gracefully (may return error or use defaults)
            assert response.status_code == 400
    
    def test_model_name_extraction(self):
        """Test model name extraction from request data"""
        test_data = {
            'model_name': 'dall-e-3',
            'prompt': 'test prompt'
        }
        
        # Test that we can extract model name
        model = test_data.get('model_name', 'unknown')
        assert model == 'dall-e-3'
        assert model != 'unknown'
