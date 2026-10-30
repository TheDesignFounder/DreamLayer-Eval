import pytest

from research.fixtures import create


@pytest.fixture(scope="session")
def fixture_media(tmp_path_factory):
    root = tmp_path_factory.mktemp("real media café")
    config = create(root)
    return root, config


@pytest.fixture(autouse=True)
def no_live_calls(monkeypatch):
    import requests

    def forbidden(*args, **kwargs):
        raise AssertionError("Offline regression suite must not contact providers")

    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
