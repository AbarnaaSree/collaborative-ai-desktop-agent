import httpx

from app.core.config import settings


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


async def generate_ai_reply(message: str) -> str:
    """Send a user message to OpenRouter and return the AI response."""

    api_key = settings.OPENROUTER_API_KEY.get_secret_value()

    if not api_key:
        raise ValueError("OpenRouter API key is not configured")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": settings.APP_NAME,
    }

    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": [
            {
                "role": "user",
                "content": message,
            }
        ],
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            OPENROUTER_API_URL,
            headers=headers,
            json=payload,
        )

    response.raise_for_status()

    result = response.json()

    return result["choices"][0]["message"]["content"]
