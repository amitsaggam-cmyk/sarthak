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
    with httpx.Client(
        timeout=30.0,
        verify=settings.llama_verify_ssl,
        auth=(settings.llama_username, settings.llama_password),
    ) as client:
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
        "messages": [
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
        ],
        "stream": False,
        "options": {
            "temperature": 0,
            "num_ctx": 8192,
        },
    }
    with httpx.Client(
        timeout=120.0,
        verify=settings.llama_verify_ssl,
        auth=(settings.llama_username, settings.llama_password),
    ) as client:
        response = client.post(
            f"{base_url}/chat",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        logger.info("[LLM] HTTP Status = %s", response.status_code)
        response.raise_for_status()
        data = response.json()
        logger.info("[LLM] Raw response = %s", json.dumps(data, indent=2))


    message = data.get("message", {})
    content = str(message.get("content") if isinstance(message, dict) else data)
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




def extract_claimed_details_with_llm(mail_text: str) -> ClaimedEmployeeDetails:
    """Use the LLM to extract only the HR fields the UI needs."""


    prompt = f"""
You are an HR Background Verification assistant.


Read the email carefully and extract ONLY the candidate details.


The email may contain:
- forwarded email chains
- copied tables
- plain text
- bullet lists
- signatures
- company information


Extract ONLY the candidate's details.


Return ONLY this JSON:


{{
  "employee_name": "...",
  "date_of_joining": "...",
  "last_working_day": "..."
}}


Rules:


- "Candidate Name" is the employee_name.
- "Employee Name" is the employee_name.
- "Date of Joining" is date_of_joining.
- "Last Working Date" and "Last Working Day" mean the same thing.
- Convert dates to YYYY-MM-DD.
- Use null if a value is missing.
- Do not explain.
- Do not wrap the JSON in markdown.


Email:


{mail_text}
"""
    data = _json_from_text(_chat(prompt))
    return ClaimedEmployeeDetails(
        employee_name=data.get("employee_name"),
        date_of_joining=data.get("date_of_joining"),
        last_working_day=data.get("last_working_day"),
    )



