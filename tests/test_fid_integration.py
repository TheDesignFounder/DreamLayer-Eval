"""
Test FID Integration with New Schema
Tests the updated metrics table structure and FID calculation
"""

import pytest
import sys
import os
import tempfile
import sqlite3
from unittest.mock import Mock, patch, MagicMock

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'dream_layer_backend', 'data', 'scripts'))

from database import DreamLayerDB
from queries import DreamLayerQueries

class TestFidIntegration:
    """Test FID integration with new schema"""
    
    def setup_method(self):
        """Setup test database"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Initialize database with new schema
        self.db = DreamLayerDB(self.temp_db.name)
        self.queries = DreamLayerQueries()
        self.queries.db = self.db
        
        # Insert test run
        self.test_run = {
            'run_id': 'test-run-123',
            'timestamp': '2025-08-23T03:00:00.000Z',
            'model': 'test-model',
            'prompt': 'test prompt',
            'generation_type': 'txt2img',
            'steps': 20,
            'cfg_scale': 7.0,
            'width': 512,
            'height': 512,
            'seed': 12345
        }
        self.db.insert_run(self.test_run)
    
    def teardown_method(self):
        """Cleanup test database"""
        os.unlink(self.temp_db.name)
    
    def test_new_metrics_schema(self):
        """Test that new metrics table has correct schema"""
        with self.db.get_connection() as conn:
            cursor = conn.execute("PRAGMA table_info(metrics)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            # Check required columns exist
            assert 'run_id' in columns
            assert 'timestamp' in columns
            assert 'clip_score_mean' in columns
            assert 'fid_score' in columns
            assert 'computed_at' in columns
            assert 'metadata' in columns
            
            # Check data types
            assert columns['clip_score_mean'] == 'REAL'
            assert columns['fid_score'] == 'REAL'
            
            # Ensure no metric_name column exists
            assert 'metric_name' not in columns
            assert 'metric_value' not in columns
    
    def test_save_clip_score(self):
        """Test saving ClipScore using new schema"""
        run_id = self.test_run['run_id']
        timestamp = self.test_run['timestamp']
        clip_score = 0.75
        
        # Save ClipScore
        success = self.queries.save_clip_score(run_id, timestamp, clip_score)
        assert success
        
        # Verify in database
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT clip_score_mean FROM metrics WHERE run_id = ?", 
                (run_id,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row['clip_score_mean'] == clip_score
    
    def test_save_fid_score(self):
        """Test saving FID score using new schema"""
        run_id = self.test_run['run_id']
        timestamp = self.test_run['timestamp']
        fid_score = 45.2
        
        # Save FID score
        success = self.queries.save_fid_score(run_id, timestamp, fid_score)
        assert success
        
        # Verify in database
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT fid_score FROM metrics WHERE run_id = ?", 
                (run_id,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row['fid_score'] == fid_score
    
    def test_save_both_metrics(self):
        """Test saving both ClipScore and FID for same run"""
        run_id = self.test_run['run_id']
        timestamp = self.test_run['timestamp']
        clip_score = 0.65
        fid_score = 32.1
        
        # Save ClipScore first
        success1 = self.queries.save_clip_score(run_id, timestamp, clip_score)
        assert success1
        
        # Save FID score (should update same row)
        success2 = self.queries.save_fid_score(run_id, timestamp, fid_score)
        assert success2
        
        # Verify both metrics in same row
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT clip_score_mean, fid_score FROM metrics WHERE run_id = ?", 
                (run_id,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row['clip_score_mean'] == clip_score
            assert row['fid_score'] == fid_score
            
            # Verify only one row exists for this run
            cursor = conn.execute("SELECT COUNT(*) FROM metrics WHERE run_id = ?", (run_id,))
            count = cursor.fetchone()[0]
            assert count == 1
    
    def test_get_run_metrics(self):
        """Test retrieving metrics for a run"""
        run_id = self.test_run['run_id']
        timestamp = self.test_run['timestamp']
        
        # Save both metrics
        self.queries.save_clip_score(run_id, timestamp, 0.8)
        self.queries.save_fid_score(run_id, timestamp, 28.5)
        
        # Retrieve metrics
        metrics = self.db.get_run_metrics(run_id)
        
        assert isinstance(metrics, dict)
        assert metrics['clip_score_mean'] == 0.8
        assert metrics['fid_score'] is None
        assert metrics['legacy_fid_score'] == 28.5
        assert metrics['fid_status'] == 'invalid_legacy_result'
    
    def test_get_runs_without_clip_score(self):
        """Test finding runs without ClipScore"""
        # Create run without any metrics
        run_without_metrics = self.test_run['run_id']
        
        # Create another run with only FID
        run_with_fid_only = 'test-run-456'
        self.db.insert_run({
            **self.test_run,
            'run_id': run_with_fid_only
        })
        self.queries.save_fid_score(run_with_fid_only, self.test_run['timestamp'], 40.0)
        
        # Create run with ClipScore
        run_with_clip = 'test-run-789'
        self.db.insert_run({
            **self.test_run,
            'run_id': run_with_clip
        })
        self.queries.save_clip_score(run_with_clip, self.test_run['timestamp'], 0.7)
        
        # Find runs without ClipScore
        runs_without_clip = self.queries.get_runs_without_clip_score()
        run_ids_without_clip = [run['run_id'] for run in runs_without_clip]
        
        assert run_without_metrics in run_ids_without_clip
        assert run_with_fid_only in run_ids_without_clip
        assert run_with_clip not in run_ids_without_clip
    
    def test_get_runs_without_fid_score(self):
        """Test finding runs without FID score"""
        # Create run without any metrics
        run_without_metrics = self.test_run['run_id']
        
        # Create another run with only ClipScore
        run_with_clip_only = 'test-run-456'
        self.db.insert_run({
            **self.test_run,
            'run_id': run_with_clip_only
        })
        self.queries.save_clip_score(run_with_clip_only, self.test_run['timestamp'], 0.6)
        
        # Create run with FID
        run_with_fid = 'test-run-789'
        self.db.insert_run({
            **self.test_run,
            'run_id': run_with_fid
        })
        self.queries.save_fid_score(run_with_fid, self.test_run['timestamp'], 35.0)
        
        # Find runs without FID
        runs_without_fid = self.queries.get_runs_without_fid_score()
        run_ids_without_fid = [run['run_id'] for run in runs_without_fid]
        
        assert run_ids_without_fid == []  # Dataset FID is never pending per run.
    
    def test_get_runs_with_metrics(self):
        """Test retrieving runs with metrics included"""
        run_id = self.test_run['run_id']
        timestamp = self.test_run['timestamp']
        
        # Save metrics
        self.queries.save_clip_score(run_id, timestamp, 0.85)
        self.queries.save_fid_score(run_id, timestamp, 22.3)
        
        # Get runs with metrics
        runs = self.db.get_runs_with_metrics(limit=1)
        
        assert len(runs) == 1
        run = runs[0]
        assert run['run_id'] == run_id
        assert 'metrics' in run
        assert run['metrics']['clip_score_mean'] == 0.85
        assert run['metrics']['fid_score'] is None
        assert run['metrics']['legacy_fid_score'] == 22.3
    
    def test_get_metrics_summary(self):
        """Test metrics summary statistics"""
        # Create multiple runs with different metrics
        runs_data = [
            ('run1', 0.7, 30.0),
            ('run2', 0.8, 25.0),
            ('run3', 0.6, None),  # Only ClipScore
            ('run4', None, 40.0)  # Only FID
        ]
        
        timestamp = self.test_run['timestamp']
        
        for run_id, clip_score, fid_score in runs_data:
            # Insert run
            self.db.insert_run({
                **self.test_run,
                'run_id': run_id
            })
            
            # Save metrics
            if clip_score is not None:
                self.queries.save_clip_score(run_id, timestamp, clip_score)
            if fid_score is not None:
                self.queries.save_fid_score(run_id, timestamp, fid_score)
        
        # Get summary
        summary = self.queries.get_metrics_summary()
        
        # Check ClipScore summary
        assert 'clip_score_mean' in summary
        clip_summary = summary['clip_score_mean']
        assert clip_summary['count'] == 3  # run1, run2, run3
        assert clip_summary['average'] == pytest.approx(0.7, abs=0.01)
        assert clip_summary['minimum'] == 0.6
        assert clip_summary['maximum'] == 0.8
        
        # Check FID summary
        assert 'legacy_fid_score' in summary
        fid_summary = summary['legacy_fid_score']
        assert fid_summary['count'] == 3  # run1, run2, run4
        assert 'average' not in fid_summary
        assert fid_summary['status'] == 'invalid_legacy_result'
    
    def test_csv_export_format(self):
        """Test CSV export includes both metrics"""
        run_id = self.test_run['run_id']
        timestamp = self.test_run['timestamp']
        
        # Save both metrics
        self.queries.save_clip_score(run_id, timestamp, 0.72)
        self.queries.save_fid_score(run_id, timestamp, 33.8)
        
        # Get CSV formatted data
        csv_data = self.queries.get_runs_for_csv_export(limit=1)
        
        assert len(csv_data) == 1
        row = csv_data[0]
        assert row['run_id'] == run_id
        assert row['clip_score_mean'] == 0.72
        assert row['fid_score'] is None
        assert row['legacy_fid_score'] == 33.8

class TestFidCalculator:
    """Test FID calculator functionality"""
    
    def test_fid_calculator_initialization(self):
        from fid_integration import DatabaseFidCalculator
        calculator = DatabaseFidCalculator()
        assert calculator.status == 'not_applicable'
        assert calculator.calculate_for_run('single-output') is None
        assert calculator.calculate_batch()['success'] == 0

    def test_dataset_stats_loader(self, tmp_path):
        from dream_layer_backend.datasets.dataset_utils import DatasetStatsLoader
        loader = DatasetStatsLoader(tmp_path)
        assert loader.get_available_datasets() == []
        with pytest.raises(ValueError, match='Automatic CIFAR'):
            loader.create_cifar10_stats()
        with pytest.raises(ValueError, match='without provenance'):
            loader.load_stats('cifar10')

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
