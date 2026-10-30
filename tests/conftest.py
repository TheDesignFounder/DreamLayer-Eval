"""
Pytest configuration and shared fixtures for DreamLayer tests
"""
import pytest
import tempfile
import os
import sys
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """A real isolated database path with environment restoration."""
    path = tmp_path / 'test.sqlite3'
    monkeypatch.setenv('TEST_DB_PATH', str(path))
    yield str(path)

@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    """Every legacy relative output and default database stays under pytest's temp root."""
    monkeypatch.chdir(tmp_path)
    for key, name in {'TEST_DB_PATH':'legacy.sqlite3', 'DREAMLAYER_DB_PATH':'legacy.sqlite3',
                      'DREAMLAYER_RESEARCH_DB':'research.sqlite3','DREAMLAYER_HISTORY_DB':'history.sqlite3',
                      'DREAMLAYER_OUTPUT_DIR':'output','DREAMLAYER_INPUT_DIR':'input',
                      'DREAMLAYER_SERVED_IMAGES_DIR':'served','DREAMLAYER_LOG_DIR':'logs',
                      'DREAMLAYER_VIDEO_OUTPUT_DIR':'video','DREAMLAYER_TEMP_IMAGES_DIR':'temporary_images'}.items():
        target = tmp_path/name
        if not name.endswith('.sqlite3'):
            target.mkdir(exist_ok=True)
        monkeypatch.setenv(key,str(target))

@pytest.fixture
def mock_comfyui():
    """Mock ComfyUI responses"""
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = {
            'status': 'success',
            'all_images': [
                {'filename': 'test_image_001.png'},
                {'filename': 'test_image_002.png'}
            ]
        }
        yield mock_post

@pytest.fixture
def test_generation_data():
    """Sample generation data for testing"""
    return {
        'model_name': 'test-model-v1',
        'prompt': 'beautiful sunset over mountains',
        'negative_prompt': 'blurry, low quality',
        'seed': 12345,
        'steps': 20,
        'cfg_scale': 7.0,
        'width': 512,
        'height': 512,
        'batch_size': 1,
        'batch_count': 1
    }

@pytest.fixture
def mock_clip_calculator():
    """Mock CLIP calculator for testing"""
    mock_calc = Mock()
    mock_calc.compute_clip_score.return_value = 0.85
    return mock_calc


@pytest.fixture(autouse=True)
def no_unexpected_http(monkeypatch):
    """Offline defaults. Adapter tests explicitly supply their own synthetic transport."""
    def blocked(*args, **kwargs):
        raise AssertionError("Unexpected network access in offline tests")
    monkeypatch.setattr("requests.sessions.Session.request", blocked)
