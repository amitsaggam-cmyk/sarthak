from app.models.schemas import (
    AttachmentResponse,
    ClaimedEmployeeDetails,
    FieldMatchResult,
    VerificationResponse,
    WorkdayEmployeeDetails,
)
from app.services.employee_store import find_employee
from app.services.parser import parse_verification_email
from app.services.reply_builder import build_recommended_reply


def _date_result(
    field_name: str,
    claimed: ClaimedEmployeeDetails,
    workday: WorkdayEmployeeDetails | None,
) -> FieldMatchResult:
    """Compare one date field with a strict 100 percent exact-match rule."""

    claimed_value = getattr(claimed, field_name)
    workday_value = getattr(workday, field_name) if workday else None

    return FieldMatchResult(
        field=field_name,
        claimed_value=claimed_value.isoformat() if claimed_value else None,
        workday_value=workday_value.isoformat() if workday_value else None,
        matches=bool(claimed_value and workday_value and claimed_value == workday_value),
    )


def verify_email(email: dict) -> VerificationResponse:
    """Run the full internal verification workflow for one email."""

    if "field_results" in email:
        claimed_details = ClaimedEmployeeDetails(
            employee_name=email.get("claimed_employee_name"),
            date_of_joining=email.get("claimed_date_of_joining"),
            last_working_day=email.get("claimed_last_working_day"),
        )
        workday_details = WorkdayEmployeeDetails(
            employee_name=email.get("workday_employee_name"),
            date_of_joining=email.get("workday_date_of_joining"),
            last_working_day=email.get("workday_last_working_day"),
        )
        field_results = [FieldMatchResult(**result) for result in email["field_results"]]
        all_fields_match = bool(email.get("all_fields_match"))
    else:
        claimed_details = parse_verification_email(email["body"])
        workday_details = find_employee(claimed_details.employee_id, claimed_details.employee_name)
        field_results = [
            _date_result("date_of_joining", claimed_details, workday_details),
            _date_result("last_working_day", claimed_details, workday_details),
        ]
        all_fields_match = all(result.matches for result in field_results)

    safe_reply = build_recommended_reply(
        email_id=email["id"],
        reply_to=email["sender"],
        subject=email["subject"],
        field_results=field_results,
    )

    return VerificationResponse(
        email_id=email["id"],
        sender=email["sender"],
        subject=email["subject"],
        body=email["body"],
        claimed_details=claimed_details,
        workday_details=workday_details,
        field_results=field_results,
        all_fields_match=all_fields_match,
        recommended_reply=safe_reply.body,
        attachments=[AttachmentResponse(**attachment) for attachment in email.get("attachments", [])],
    )
