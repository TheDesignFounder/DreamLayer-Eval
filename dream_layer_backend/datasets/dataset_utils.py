"""Explicit reference caches only; unknown legacy CIFAR statistics are invalid."""
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research.fid import features, read_cache, write_cache

class DatasetStatsLoader:
    def __init__(self, stats_dir=None):
        self.stats_dir = Path(stats_dir or Path(__file__).parent)

    def get_available_datasets(self):
        return []  # Selection must be deliberate, never an automatic arbitrary reference.

    def create_reference(self, image_paths, cache_path, **kwargs):
        values, provenance = features(image_paths, **kwargs)
        write_cache(cache_path, values, provenance)
        return provenance

    def load_reference(self, cache_path, expected_provenance):
        values = read_cache(cache_path, expected_provenance)
        return values.mean(0), np.cov(values, rowvar=False)

    def create_cifar10_stats(self):
        raise ValueError('Automatic CIFAR reference construction removed; provide explicit image membership and verified extractor provenance')

    def load_stats(self, dataset_name, expected_provenance=None):
        if expected_provenance is None:
            raise ValueError('Legacy reference statistics without provenance cannot be accepted')
        return self.load_reference(self.stats_dir / (dataset_name + '_inception_stats.npz'), expected_provenance)

    def get_stats(self):
        raise ValueError('Explicit reference selection and cache provenance required')

CIFAR10StatsLoader = DatasetStatsLoader

def get_dataset_stats(dataset_name=None, expected_provenance=None):
    return DatasetStatsLoader().load_stats(dataset_name, expected_provenance)

def ensure_cifar10_stats():
    return False
