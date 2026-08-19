import asyncio
import base64
import logging
from typing import Any

from app.core.config import get_settings


MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 3
_client = None
logger = logging.getLogger(__name__)


def _get_client():
    """Create one reusable Azure OpenAI client for document vision calls."""

    global _client
    settings = get_settings()
    if _client is None:
        if not settings.azure_openai_endpoint or not settings.azure_openai_api_key:
            raise RuntimeError("Azure OpenAI document verification settings are not configured.")
        from openai import AsyncAzureOpenAI

        _client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
    return _client


def image_to_data_url(image_bytes: bytes, mime_type: str = "image/png") -> str:
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def build_vision_message(prompt: str, image_urls: list[str]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for url in image_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})
    return [{"role": "user", "content": content}]


async def call_vision_with_retry(
    messages: list[dict[str, Any]],
    response_format: dict[str, str] | None = None,
) -> str:
    settings = get_settings()
    client = _get_client()
    last_exception: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            logger.info("[DOC_VERIFY] Calling Azure vision attempt=%s", attempt + 1)
            kwargs: dict[str, Any] = {
                "model": settings.azure_openai_deployment,
                "messages": messages,
            }
            if response_format:
                kwargs["response_format"] = response_format
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception as err:
            last_exception = err
            status_code = getattr(err, "status_code", None)
            is_retryable = status_code == 429 or (status_code is not None and status_code >= 500)
            if not is_retryable or attempt == MAX_RETRIES - 1:
                raise
            wait_seconds = BASE_BACKOFF_SECONDS * (2**attempt)
            logger.warning(
                "[DOC_VERIFY] Azure vision retryable error attempt=%s wait_seconds=%s error=%s",
                attempt + 1,
                wait_seconds,
                err,
            )
            await asyncio.sleep(wait_seconds)

    raise last_exception or RuntimeError("Vision request failed.")


# The retry helper is not vision-specific: it accepts any Azure chat messages payload,
# so text-only callers (e.g. mail extraction) reuse it under a clearer name.
call_azure_chat_with_retry = call_vision_with_retry
