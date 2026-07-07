import json
from datetime import date

import httpx
from sqlalchemy import select

from app.db.models import Email
from app.db.session import AsyncSessionLocal
from app.models.schemas import ClaimedEmployeeDetails, FieldMatchResult, WorkdayEmployeeDetails
from app.services.llm_client import extract_claimed_details_with_llm
from app.services.parser import parse_verification_email
from app.services.workday_raas import fetch_workday_details


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


async def process_email(email_id: int) -> bool:
    """Extract, match with Workday, and store verification data for one DB email."""

    async with AsyncSessionLocal() as session:
        row = await session.get(Email, email_id)
        if not row:
            return False
        row.processing_status = "pending"
        await session.commit()

    try:
        try:
            claimed = extract_claimed_details_with_llm(row.body)
        except Exception:
            claimed = parse_verification_email(row.body)

        workday = await fetch_workday_details(claimed)
        field_results = [
            _date_result("date_of_joining", claimed, workday),
            _date_result("last_working_day", claimed, workday),
        ]
        all_fields_match = all(result.matches for result in field_results)

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
        return True
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
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
        return None

    await process_email(email_id)
    return email_id


async def process_pending_emails(limit: int = 10) -> int:
    """Process a bounded batch for manual API calls or background loops."""

    processed = 0
    for _ in range(limit):
        email_id = await process_next_email()
        if email_id is None:
            break
        processed += 1
    return processed
