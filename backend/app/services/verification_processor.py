import json
import logging
from datetime import date

import httpx
from sqlalchemy import select

from app.db.models import Email
from app.db.session import AsyncSessionLocal
from app.core.config import get_settings
from app.models.schemas import ClaimedEmployeeDetails, FieldMatchResult, WorkdayEmployeeDetails
from app.services.llm_client import extract_claimed_details_with_llm
from app.services.parser import parse_verification_email
from app.services.workday_raas import fetch_workday_details


logger = logging.getLogger(__name__)


def _date_text(value: date | str | None) -> str | None:
    if isinstance(value, date):
        return value.isoformat()
    return value


def _date_result(
    field_name: str,
    claimed: ClaimedEmployeeDetails,
    workday: WorkdayEmployeeDetails | None,
) -> FieldMatchResult:
    claimed_value = _date_text(getattr(claimed, field_name))
    workday_value = _date_text(getattr(workday, field_name)) if workday else None
    return FieldMatchResult(
        field=field_name,
        claimed_value=claimed_value,
        workday_value=workday_value,
        matches=bool(claimed_value and workday_value and claimed_value == workday_value),
    )


def _has_claimed_details(claimed: ClaimedEmployeeDetails) -> bool:
    return bool(
        claimed.employee_name
        or claimed.date_of_joining
        or claimed.last_working_day
    )


async def process_email(email_id: int) -> bool:
    """Extract, match with Workday, and store verification data for one DB email."""

    logger.info("[PROCESS] Starting email_id=%s", email_id)
    async with AsyncSessionLocal() as session:
        row = await session.get(Email, email_id)
        if not row:
            logger.warning("[PROCESS] Email not found email_id=%s", email_id)
            return False
        row.processing_status = "pending"
        await session.commit()

    try:
        logger.info("[LLM] Extracting claimed details email_id=%s subject=%r", email_id, row.subject)
        try:
            claimed = extract_claimed_details_with_llm(row.body)
        except Exception as exc:
            logger.warning(
                "[LLM] Extraction failed email_id=%s; falling back to regex parser. error=%s",
                email_id,
                exc,
            )
            claimed = parse_verification_email(row.body)

        if not _has_claimed_details(claimed):
            raise ValueError("Could not extract employee name, date of joining, or last working day from email.")

        logger.info(
            "[LLM] Extracted email_id=%s name=%r doj=%s lwd=%s",
            email_id,
            claimed.employee_name,
            claimed.date_of_joining,
            claimed.last_working_day,
        )

        logger.info("[WORKDAY] Looking up employee email_id=%s name=%r", email_id, claimed.employee_name)
        workday = await fetch_workday_details(claimed)
        if workday:
            logger.info(
                "[WORKDAY] Found email_id=%s name=%r doj=%s lwd=%s",
                email_id,
                workday.employee_name,
                workday.date_of_joining,
                workday.last_working_day,
            )
        else:
            logger.warning("[WORKDAY] No Workday record found email_id=%s", email_id)

        field_results = [
            _date_result("date_of_joining", claimed, workday),
            _date_result("last_working_day", claimed, workday),
        ]
        all_fields_match = all(result.matches for result in field_results)
        for result in field_results:
            logger.info(
                "[MATCH] email_id=%s field=%s claimed=%r workday=%r match=%s",
                email_id,
                result.field,
                result.claimed_value,
                result.workday_value,
                result.matches,
            )

        async with AsyncSessionLocal() as session:
            current = await session.get(Email, email_id)
            if not current:
                return False
            current.claimed_employee_name = claimed.employee_name
            current.claimed_date_of_joining = _date_text(claimed.date_of_joining)
            current.claimed_last_working_day = _date_text(claimed.last_working_day)
            current.workday_employee_name = workday.employee_name if workday else None
            current.workday_date_of_joining = _date_text(workday.date_of_joining) if workday else None
            current.workday_last_working_day = _date_text(workday.last_working_day) if workday else None
            current.field_results_json = json.dumps([result.model_dump() for result in field_results])
            current.all_fields_match = all_fields_match
            current.processing_status = "completed"
            current.processing_error = None
            await session.commit()
        logger.info("[PROCESS] Stored result email_id=%s all_fields_match=%s", email_id, all_fields_match)
        return True
    except (httpx.HTTPError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        logger.exception("[PROCESS] Failed email_id=%s error=%s", email_id, exc)
        async with AsyncSessionLocal() as session:
            current = await session.get(Email, email_id)
            if current:
                current.processing_status = "pending"
                current.processing_error = str(exc)
                await session.commit()
        return False


async def process_next_email() -> int | None:
    """Process the oldest unverified DB email, one at a time."""

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Email.id)
            .where(Email.field_results_json.is_(None))
            .order_by(Email.received_at.asc())
            .limit(1)
        )
        email_id = result.scalar_one_or_none()

    if email_id is None:
        logger.info("[BATCH] No unprocessed emails found")
        return None

    await process_email(email_id)
    return email_id


async def process_pending_emails(limit: int | None = None) -> int:
    """Process a bounded batch for manual API calls or background loops."""

    settings = get_settings()
    batch_limit = limit or settings.mail_processing_batch_size
    logger.info("[BATCH] Starting processing batch limit=%s", batch_limit)
    processed = 0
    for _ in range(batch_limit):
        email_id = await process_next_email()
        if email_id is None:
            break
        processed += 1
    logger.info("[BATCH] Finished processing batch processed=%s", processed)
    return processed
