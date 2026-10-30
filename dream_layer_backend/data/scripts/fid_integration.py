"""Compatibility entry points. Standard FID lives in research.fid and needs two sets."""
import logging
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from research.fid import calculate, frechet_from_features

logger = logging.getLogger(__name__)
REASON = 'Per-run FID is disabled. Use research experiments with explicit generated/reference image sets.'

class DatabaseFidCalculator:
    def __init__(self):
        self.fid_calculator = False
        self.dataset_stats = None
        self.status = 'not_applicable'
        self.reason = REASON

    def calculate_for_run(self, run_id):
        logger.info(REASON)
        return None

    def _compute_fid_from_images(self, image_paths, batch_size=8, reference_paths=None):
        if reference_paths is None:
            raise ValueError(REASON)
        return calculate(image_paths, reference_paths, batch_size=batch_size)[0]

    def calculate_dataset(self, image_paths, reference_paths, **kwargs):
        return calculate(image_paths, reference_paths, **kwargs)

    def calculate_batch(self, limit=2000):
        return {'success': 0, 'failed': 0, 'total': 0, 'status': self.status, 'reason': REASON, 'results': []}

    def recalculate_all(self, force=False):
        return self.calculate_batch()


def calculate_missing_fid_scores(limit=2000):
    return DatabaseFidCalculator().calculate_batch(limit)


def compute_fid_for_run(run_id):
    return DatabaseFidCalculator().calculate_for_run(run_id)
