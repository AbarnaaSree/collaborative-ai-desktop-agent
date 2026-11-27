import httpx
import pytest

from app.core.config import settings
from app.services import openrouter_service


@pytest.mark.asyncio
async def test_generate_ai_reply_success(monkeypatch):
    """Return the reply from a valid OpenRouter response."""

    monkeypatch.setattr(
        settings.OPENROUTER_API_KEY,
        "get_secret_value",
        lambda: "test-api-key",
    )

    async def mock_post(self, url, headers, json):
        assert url == openrouter_service.OPENROUTER_API_URL
        assert headers["Authorization"] == "Bearer test-api-key"
        assert json["model"] == settings.OPENROUTER_MODEL

        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "Hello from AI",
                        }
                    }
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(
        httpx.AsyncClient,
        "post",
        mock_post,
    )

    reply = await openrouter_service.generate_ai_reply("Hello")

    assert reply == "Hello from AI"


@pytest.mark.asyncio
async def test_generate_ai_reply_missing_api_key(monkeypatch):
    """Raise a clear error when the API key is missing."""

    monkeypatch.setattr(
        settings.OPENROUTER_API_KEY,
        "get_secret_value",
        lambda: "",
    )

    with pytest.raises(
        ValueError,
        match="OpenRouter API key is not configured",
    ):
        await openrouter_service.generate_ai_reply("Hello")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_data",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": ""}}]},
        {"choices": [{"message": {"content": None}}]},
    ],
)
async def test_generate_ai_reply_rejects_invalid_response(
    monkeypatch,
    response_data,
):
    """Reject malformed or empty OpenRouter responses."""

    monkeypatch.setattr(
        settings.OPENROUTER_API_KEY,
        "get_secret_value",
        lambda: "test-api-key",
    )

    async def mock_post(self, url, headers, json):
        return httpx.Response(
            200,
            json=response_data,
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(
        httpx.AsyncClient,
        "post",
        mock_post,
    )

    with pytest.raises(ValueError):
        await openrouter_service.generate_ai_reply("Hello")