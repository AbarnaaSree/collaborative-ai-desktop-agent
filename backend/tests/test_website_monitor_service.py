
import httpx
import pytest

from app.services import website_monitor_service
from app.services.website_monitor_service import (
    check_website,
    validate_website_url,
)


def test_validate_website_url():
    assert (
        validate_website_url(" https://example.com ")
        == "https://example.com"
    )


def test_validate_website_url_rejects_invalid_scheme():
    with pytest.raises(ValueError):
        validate_website_url("ftp://example.com")


def test_validate_website_url_rejects_missing_hostname():
    with pytest.raises(ValueError):
        validate_website_url("https://")


def test_validate_website_url_rejects_localhost():
    with pytest.raises(ValueError):
        validate_website_url("http://localhost")


def test_validate_website_url_rejects_private_ip():
    with pytest.raises(ValueError):
        validate_website_url("http://192.168.1.10")


def test_validate_website_url_rejects_credentials():
    with pytest.raises(ValueError):
        validate_website_url("https://user:pass@example.com")


@pytest.mark.asyncio
async def test_check_website_success(monkeypatch):
    async def fake_public_host(hostname, port):
        return None

    monkeypatch.setattr(
        website_monitor_service,
        "_ensure_public_host",
        fake_public_host,
    )

    class MockResponse:
        status_code = 200

    class MockClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url):
            return MockResponse()

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        MockClient,
    )

    result = await check_website("https://example.com")

    assert result["is_available"] is True
    assert result["status_code"] == 200
    assert result["response_time_ms"] >= 0
    assert result["error_message"] is None


@pytest.mark.asyncio
async def test_check_website_http_error(monkeypatch):
    async def fake_public_host(hostname, port):
        return None

    monkeypatch.setattr(
        website_monitor_service,
        "_ensure_public_host",
        fake_public_host,
    )

    class MockResponse:
        status_code = 503

    class MockClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url):
            return MockResponse()

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        MockClient,
    )

    result = await check_website("https://example.com")

    assert result["is_available"] is False
    assert result["status_code"] == 503
