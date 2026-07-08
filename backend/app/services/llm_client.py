import httpx
import json
import logging
import re

from app.core.config import get_settings
from app.models.schemas import ClaimedEmployeeDetails


logger = logging.getLogger(__name__)


def test_llama_connection(prompt: str) -> str:
    """Send a single non-streaming chat request to the configured Llama endpoint."""

    settings = get_settings()
    base_url = settings.llama_base_url.rstrip("/")
    payload = {
        "model": settings.llama_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    with httpx.Client(timeout=30.0, verify=settings.llama_verify_ssl) as client:
        response = client.post(
            f"{base_url}/chat",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

    message = data.get("message", {})
    if isinstance(message, dict) and message.get("content"):
        return str(message["content"])
    return str(data)


def _chat(prompt: str) -> str:
    """Send one non-streaming prompt to the configured Llama-compatible endpoint."""

    settings = get_settings()
    base_url = settings.llama_base_url.rstrip("/")
    logger.info("[LLM] Sending chat request model=%s prompt_chars=%s", settings.llama_model, len(prompt))
    payload = {
        "model": settings.llama_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    with httpx.Client(timeout=60.0, verify=settings.llama_verify_ssl) as client:
        response = client.post(
            f"{base_url}/chat",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

    message = data.get("message", {})
    content = str(message.get("content") if isinstance(message, dict) else data)
    logger.info("[LLM] Received chat response chars=%s", len(content))
    return content


def _json_from_text(value: str) -> dict:
    """Recover a JSON object even when the model wraps it in prose."""

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", value, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def extract_claimed_details_with_llm(mail_text: str) -> ClaimedEmployeeDetails:
    """Use the LLM to extract only the HR fields the UI needs."""

    prompt = f"""
Extract employee verification details from this email.
Return only valid JSON with these keys:
employee_name, date_of_joining, last_working_day.
Dates must be ISO format YYYY-MM-DD. Use null when a value is absent.

Email:
{mail_text}
"""
    data = _json_from_text(_chat(prompt))
    return ClaimedEmployeeDetails(
        employee_name=data.get("employee_name"),
        date_of_joining=data.get("date_of_joining"),
        last_working_day=data.get("last_working_day"),
    )
