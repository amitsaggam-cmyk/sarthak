import json
import logging
import re

from app.core.config import get_settings
from app.models.schemas import ClaimedEmployeeDetails
from app.services.doc_verification.pipeline.azure_vision_client import call_azure_chat_with_retry


logger = logging.getLogger(__name__)


async def test_llm_chat(prompt: str) -> str:
    """Send a single chat request to the configured Azure OpenAI deployment."""

    return await call_azure_chat_with_retry([{"role": "user", "content": prompt}])


async def _chat(prompt: str) -> str:
    """Send one prompt to Azure OpenAI without blocking the event loop."""

    settings = get_settings()
    logger.info(
        "[LLM] Sending chat request deployment=%s prompt_chars=%s",
        settings.azure_openai_deployment,
        len(prompt),
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are an HR background verification assistant. "
                "Always extract information accurately. "
                "Always return ONLY valid JSON."
            ),
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]
    content = await call_azure_chat_with_retry(messages, response_format={"type": "json_object"})
    logger.info("[LLM] Received chat response chars=%s", len(content))
    return content


def _json_from_text(value: str) -> dict:
    value = value.strip()

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", value, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"LLM did not return valid JSON:\n{value}")


async def extract_claimed_details_with_llm(mail_text: str) -> ClaimedEmployeeDetails:
    """Use the LLM to extract the 8 required HR fields."""

    prompt = f"""
You are an HR Background Verification assistant.

Read the email carefully and extract ONLY the candidate details.
Extract ONLY these fields. Use null if a value is missing.
Convert all dates to YYYY-MM-DD format.

Return ONLY this valid JSON:
{{
  "candidate_name": "...",
  "employee_id": "...",
  "nature_of_employment": "...",
  "start_date": "...",
  "end_date": "...",
  "last_designation": "...",
  "location": "...",
  "exit_formalities_completed": "..."
}}

Email:

{mail_text}
"""
    data = _json_from_text(await _chat(prompt))
    
    # Sanitize boolean field answers from the LLM into text before Pydantic validation
    ef = data.get("exit_formalities_completed")
    if isinstance(ef, bool):
        data["exit_formalities_completed"] = "Yes" if ef else "No"
    elif ef is not None:
        data["exit_formalities_completed"] = str(ef)

    return ClaimedEmployeeDetails(
        candidate_name=data.get("candidate_name"),
        employee_id=data.get("employee_id"),
        nature_of_employment=data.get("nature_of_employment"),
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
        last_designation=data.get("last_designation"),
        location=data.get("location"),
        exit_formalities_completed=data.get("exit_formalities_completed"),
    )