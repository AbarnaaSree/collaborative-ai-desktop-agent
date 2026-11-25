
import asyncio
import ipaddress
import socket
from datetime import datetime, timezone
from time import perf_counter
from urllib.parse import urlparse

import httpx


def validate_website_url(url: str) -> str:
    """Validate URL format and reject obvious local/private destinations."""

    normalized_url = url.strip()
    parsed_url = urlparse(normalized_url)

    if parsed_url.scheme not in {"http", "https"}:
        raise ValueError("Website URL must use HTTP or HTTPS")

    if not parsed_url.hostname:
        raise ValueError("Website URL must contain a valid hostname")

    if parsed_url.username or parsed_url.password:
        raise ValueError("Website URL must not contain credentials")

    hostname = parsed_url.hostname.lower().rstrip(".")

    if (
        hostname == "localhost"
        or hostname.endswith(".localhost")
        or hostname.endswith(".local")
        or hostname.endswith(".internal")
        or hostname.endswith(".lan")
    ):
        raise ValueError("Local or internal hostnames are not allowed")

    try:
        ip_address = ipaddress.ip_address(hostname)
    except ValueError:
        ip_address = None

    if ip_address is not None and not ip_address.is_global:
        raise ValueError("Private or non-public IP addresses are not allowed")

    return normalized_url


async def _ensure_public_host(hostname: str, port: int) -> None:
    """Resolve the hostname and reject non-public IP addresses."""

    loop = asyncio.get_running_loop()

    try:
        results = await loop.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except OSError as error:
        raise ValueError("Website hostname could not be resolved") from error

    if not results:
        raise ValueError("Website hostname has no IP addresses")

    for result in results:
        resolved_ip = ipaddress.ip_address(result[4][0])

        if not resolved_ip.is_global:
            raise ValueError(
                "Website hostname resolves to a private or non-public IP"
            )


async def check_website(
    url: str,
    timeout_seconds: float = 10.0,
) -> dict:
    """Check website availability and measure response time."""

    normalized_url = validate_website_url(url)
    parsed_url = urlparse(normalized_url)

    port = parsed_url.port or (
        443 if parsed_url.scheme == "https" else 80
    )

    await _ensure_public_host(parsed_url.hostname, port)

    started = perf_counter()

    try:
        async with httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = await client.get(normalized_url)

        response_time_ms = round(
            (perf_counter() - started) * 1000,
            2,
        )

        return {
            "url": normalized_url,
            "is_available": response.status_code < 400,
            "status_code": response.status_code,
            "response_time_ms": response_time_ms,
            "error_message": None,
            "checked_at": datetime.now(timezone.utc),
        }

    except httpx.TimeoutException:
        return {
            "url": normalized_url,
            "is_available": False,
            "status_code": None,
            "response_time_ms": round(
                (perf_counter() - started) * 1000,
                2,
            ),
            "error_message": "Website request timed out",
            "checked_at": datetime.now(timezone.utc),
        }

    except httpx.RequestError as error:
        return {
            "url": normalized_url,
            "is_available": False,
            "status_code": None,
            "response_time_ms": round(
                (perf_counter() - started) * 1000,
                2,
            ),
            "error_message": str(error),
            "checked_at": datetime.now(timezone.utc),
        }
