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
    workday_field_name: str | None = None,
) -> FieldMatchResult:
    workday_attr = workday_field_name or field_name
    claimed_value = _date_text(getattr(claimed, field_name))
    workday_value = _date_text(getattr(workday, workday_attr)) if workday else None
    return FieldMatchResult(
        field=field_name,
        claimed_value=claimed_value,
        workday_value=workday_value,
        matches=bool(claimed_value and workday_value and claimed_value == workday_value),
    )




def _text_result(
    field_name: str,
    claimed: ClaimedEmployeeDetails,
    workday: WorkdayEmployeeDetails | None,
    workday_field_name: str | None = None,
) -> FieldMatchResult:
    """Compare a text field with case-insensitive, stripped matching.


    `workday_field_name` lets the two sides use different attribute names
    (e.g. claimed.candidate_name vs workday.employee_name) while still being
    reported under a single logical field name.
    """
    workday_attr = workday_field_name or field_name
    claimed_value = getattr(claimed, field_name)
    workday_value = getattr(workday, workday_attr) if workday else None
    cv_clean = str(claimed_value).strip().lower() if claimed_value else None
    wv_clean = str(workday_value).strip().lower() if workday_value else None
    return FieldMatchResult(
        field=field_name,
        claimed_value=claimed_value if claimed_value else None,
        workday_value=workday_value if workday_value else None,
        matches=bool(cv_clean and wv_clean and cv_clean == wv_clean),
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
            claimed = await extract_claimed_details_with_llm(row.body)
        except Exception as exc:
            logger.warning(
                "[LLM] Extraction failed email_id=%s; falling back to regex parser. error=%s",
                email_id,
                exc,
            )
            claimed = parse_verification_email(row.body)


        logger.info(
            "[LLM] Extracted email_id=%s name=%r id=%s",
            email_id,
            claimed.candidate_name,
            claimed.employee_id,
        )


        logger.info("[WORKDAY] Looking up employee email_id=%s name=%r id=%s", email_id, claimed.candidate_name, claimed.employee_id)
        workday = await fetch_workday_details(claimed)
        if workday:
            logger.info(
                "[WORKDAY] Found email_id=%s name=%r id=%s",
                email_id,
                workday.employee_name,
                workday.employee_id,
            )
        else:
            logger.warning("[WORKDAY] No Workday record found email_id=%s", email_id)


        field_results = [
            _text_result("candidate_name", claimed, workday, workday_field_name="employee_name"),
            _text_result("employee_id", claimed, workday),
            _text_result("nature_of_employment", claimed, workday),
            _date_result("start_date", claimed, workday),
            _date_result("end_date", claimed, workday),
            _text_result("last_designation", claimed, workday),
            _text_result("location", claimed, workday),
            _text_result("exit_formalities_completed", claimed, workday),
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


            # Map 8 fields for claimed
            current.claimed_candidate_name = claimed.candidate_name
            current.claimed_employee_id = claimed.employee_id
            current.claimed_nature_of_employment = claimed.nature_of_employment
            current.claimed_start_date = _date_text(claimed.start_date)
            current.claimed_end_date = _date_text(claimed.end_date)
            current.claimed_last_designation = claimed.last_designation
            current.claimed_location = claimed.location
            current.claimed_exit_formalities_completed = claimed.exit_formalities_completed


            # Map 8 fields for workday
            current.workday_candidate_name = workday.employee_name if workday else None
            current.workday_employee_id = workday.employee_id if workday else None
            current.workday_nature_of_employment = workday.nature_of_employment if workday else None
            current.workday_start_date = _date_text(workday.start_date) if workday else None
            current.workday_end_date = _date_text(workday.end_date) if workday else None
            current.workday_last_designation = workday.last_designation if workday else None
            current.workday_location = workday.location if workday else None
            current.workday_exit_formalities_completed = workday.exit_formalities_completed if workday else None


            current.field_results_json = json.dumps([result.model_dump() for result in field_results])
            current.all_fields_match = all_fields_match


            # FIXED: Change status to 'processed' so it doesn't revert to a confusing 'new' state
            current.processing_status = "processed"
            current.processing_error = None


            await session.commit()
        logger.info("[PROCESS] Stored result email_id=%s all_fields_match=%s", email_id, all_fields_match)
        return True


    # Using a generic Exception catch to gracefully fail on unexpected Workday behavior
    except Exception as exc:
        logger.exception("[PROCESS] Failed email_id=%s error=%s", email_id, exc)
        async with AsyncSessionLocal() as session:
            current = await session.get(Email, email_id)
            if current:
                # FIXED: Change status to 'error' to prevent the endless retry loop
                current.processing_status = "error"
                current.processing_error = str(exc)
                await session.commit()
        return False




async def process_next_email() -> int | None:
    """Process the oldest unverified DB email, one at a time."""


    async with AsyncSessionLocal() as session:
        # FIXED: Ensure we are ignoring emails that have already errored out
        result = await session.execute(
            select(Email.id)
            .where(
                Email.field_results_json.is_(None),
                Email.processing_status != "error"
            )
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



