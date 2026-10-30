import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import cite  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "live: hits the real APIs; run with CITE_LIVE=1")


def fixture(name: str) -> bytes:
    return (HERE / "fixtures" / name).read_bytes()


@pytest.fixture
def net(monkeypatch):
    """Replace cite.http_get with a router: first route whose key is a substring of the URL wins."""
    def fake(url):
        fake.calls.append(url)
        for frag, payload in fake.routes.items():
            if frag in url:
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise cite.LookupFailed("not found")
    fake.routes, fake.calls = {}, []
    monkeypatch.setattr(cite, "http_get", fake)
    monkeypatch.delenv("CITE_MAILTO", raising=False)
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    return fake
