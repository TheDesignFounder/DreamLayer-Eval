"""Retired contest interface. Historical leaderboard values are not corrected scores.

The old module downloaded unrelated CIFAR references, substituted FID=100 on
failure and defined two incompatible score() functions. It cannot provide a
scientifically interpretable combined ranking. Use versioned research exports.
The original source is retained in the pre-change baseline archive.
"""
class ParticipantVisibleError(ValueError):
    pass


def score(*args, **kwargs):
    raise ParticipantVisibleError('Legacy contest ranking disabled: use separate versioned evaluator results; see docs/metric-corrections.md')


def download_cifar_reference_images(*args, **kwargs):
    raise ParticipantVisibleError('No automatic reference dataset. Supply deliberate image-set membership and provenance.')


def compute_fid_score(csv_data, images_dir, reference_images_dir):
    """No ambiguous CSV/per-image compatibility fallback is permitted."""
    raise ParticipantVisibleError('Use research.fid.calculate(generated_paths, reference_paths) with explicit sets.')
