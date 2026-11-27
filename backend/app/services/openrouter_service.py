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
    if not isinstance(result, dict):
        raise ValueError("Invalid OpenRouter response")

    choices = result.get("choices")

    if not isinstance(choices, list) or not choices:
        raise ValueError("OpenRouter response contains no choices")

    first_choice = choices[0]

    if not isinstance(first_choice, dict):
        raise ValueError("Invalid OpenRouter choice")

    message_data = first_choice.get("message")

    if not isinstance(message_data, dict):
        raise ValueError("Invalid OpenRouter message")

    content = message_data.get("content")

    if not isinstance(content, str) or not content.strip():
        raise ValueError("OpenRouter response contains no message content")

    return content.strip()
