import json
import logging
from typing import Any

from app.services.doc_verification.pipeline.azure_vision_client import (
    build_vision_message,
    call_vision_with_retry,
    image_to_data_url,
)


logger = logging.getLogger(__name__)

VALID_DOC_TYPES = [
    "PAN_CARD",
    "AADHAAR_CARD",
    "MARKSHEET",
    "DEGREE_CERTIFICATE",
    "RESUME",
    "OFFER_LETTER_PREVIOUS_ORG",
    "PAYSLIP",
    "RESIGNATION_ACCEPTANCE",
    "RELIEVING_LETTER",
    "UAN_SCREENSHOT",
    "PF_FORM_11",
    "SELF_DECLARATION_FORM",
    "SIGNED_OFFER_LETTER_JADE",
    "PASSPORT_PHOTO",
    "GAP_DECLARATION_FORM",
    "GAP_AFFIDAVIT",
    "CANCELLED_CHEQUE",
    "UNKNOWN",
]

PROMPT_TEMPLATE = """You are a strict HR document classifier with vision.
Look at this image (page 1 of an uploaded document) and classify it.

FILENAME HINT: "{filename}"

VALID DOCUMENT TYPES:
{doc_types}

RULES:
1. Reply ONLY with valid JSON, no markdown, no extra text.
2. Pick the single best matching type.
3. SIGNED_OFFER_LETTER_JADE = any offer letter issued by Jade Global.
4. OFFER_LETTER_PREVIOUS_ORG = an offer letter from any other company.
5. PASSPORT_PHOTO = a professional candidate photograph/headshot for company identification.
6. If nothing matches confidently, return UNKNOWN.

OUTPUT FORMAT:
{{"document_type": "TYPE_FROM_LIST", "confidence_score": 0.9}}
"""


async def classify_document(first_page_png: bytes, filename: str) -> dict[str, Any]:
    prompt = PROMPT_TEMPLATE.format(filename=filename, doc_types=json.dumps(VALID_DOC_TYPES))
    messages = build_vision_message(prompt, [image_to_data_url(first_page_png)])

    try:
        content = await call_vision_with_retry(messages, response_format={"type": "json_object"})
        
        # DEBUG PRINTS
        print(f"[DEBUG] Raw API content for {filename}:\n{content}")
        
        parsed = json.loads(content)
        print(f"[DEBUG] Parsed JSON dictionary:\n{parsed}")
        
        candidate = str(parsed.get("document_type", "UNKNOWN")).upper().strip()
        doc_type = candidate if candidate in VALID_DOC_TYPES else "UNKNOWN"
        confidence = float(parsed.get("confidence_score", 0.0))
        
        print(f"[DEBUG] Final output -> type: {doc_type}, confidence: {confidence}")
        
        return {"document_type": doc_type, "confidence_score": confidence}
    except Exception as exc:
        logger.warning("Document classification failed filename=%s error=%s", filename, exc)
        return {"document_type": "UNKNOWN", "confidence_score": 0.0}
