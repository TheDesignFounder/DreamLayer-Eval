"""The retired contest must fail explicitly, including when no submission exists."""
import pytest
from kaggle_contest import score, compute_fid_score, download_cifar_reference_images, ParticipantVisibleError


def test_scoring():
    with pytest.raises(ParticipantVisibleError, match='Legacy contest ranking disabled'):
        score(solution=None, submission_zip_path='submissions.zip', row_id_column_name='id')


def test_no_fabricated_fid_or_implicit_reference():
    with pytest.raises(ParticipantVisibleError, match='explicit sets'):
        compute_fid_score(None, 'missing', 'missing')
    with pytest.raises(ParticipantVisibleError, match='No automatic reference'):
        download_cifar_reference_images()
