from app.models.schemas import (
    AttachmentResponse,
    ClaimedEmployeeDetails,
    FieldMatchResult,
    VerificationResponse,
    WorkdayEmployeeDetails,
)
from app.services.reply_builder import build_recommended_reply

# Note: Keeping these helper functions in case your verification_processor.py 
# imports them from here to do the background matching. 
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


def _text_result(
    field_name: str,
    claimed: ClaimedEmployeeDetails,
    workday: WorkdayEmployeeDetails | None,
) -> FieldMatchResult:
    """Compare a text field with case-insensitive, stripped matching."""
    
    claimed_value = getattr(claimed, field_name)
    workday_field_name = "employee_name" if field_name == "candidate_name" else field_name
    workday_value = getattr(workday, workday_field_name) if workday else None
    
    cv_clean = str(claimed_value).strip().lower() if claimed_value else None
    wv_clean = str(workday_value).strip().lower() if workday_value else None

    return FieldMatchResult(
        field=field_name,
        claimed_value=claimed_value if claimed_value else None,
        workday_value=workday_value if workday_value else None,
        matches=bool(cv_clean and wv_clean and cv_clean == wv_clean),
    )


def verify_email(email: dict) -> VerificationResponse:
    """Run the full internal verification workflow for one email."""

    # Check if we already have the processed fields from the DB
    if "field_results" in email and email["field_results"]:
        claimed_details = ClaimedEmployeeDetails(
            candidate_name=email.get("claimed_candidate_name"),
            employee_id=email.get("claimed_employee_id"),
            nature_of_employment=email.get("claimed_nature_of_employment"),
            start_date=email.get("claimed_start_date"),
            end_date=email.get("claimed_end_date"),
            last_designation=email.get("claimed_last_designation"),
            location=email.get("claimed_location"),
            exit_formalities_completed=email.get("claimed_exit_formalities_completed"),
        )
        workday_details = WorkdayEmployeeDetails(
            employee_name=email.get("workday_candidate_name"),
            employee_id=email.get("workday_employee_id"),
            nature_of_employment=email.get("workday_nature_of_employment"),
            start_date=email.get("workday_start_date"),
            end_date=email.get("workday_end_date"),
            last_designation=email.get("workday_last_designation"),
            location=email.get("workday_location"),
            exit_formalities_completed=email.get("workday_exit_formalities_completed"),
        )
        field_results = [FieldMatchResult(**result) for result in email["field_results"]]
        all_fields_match = bool(email.get("all_fields_match"))
        
        safe_reply = build_recommended_reply(
            email_id=email["id"],
            reply_to=email["sender"],
            subject=email["subject"],
            field_results=field_results,
        )
        recommended_reply_text = safe_reply.body
        status = email.get("status", "pending")
        
    else:
        # NO FALLBACK: Do not call the LLM or parse again.
        # Return an empty/pending state indicating it needs background processing.
        claimed_details = ClaimedEmployeeDetails(
            candidate_name=None,
            employee_id=None,
            nature_of_employment=None,
            start_date=None,
            end_date=None,
            last_designation=None,
            location=None,
            exit_formalities_completed=None
        )
        workday_details = None
        field_results = []
        all_fields_match = False
        recommended_reply_text = "This email is pending background processing. No reply can be generated yet."
        status = email.get("status", "pending")
        
    has_results = bool(email.get("field_results"))
    
    return VerificationResponse(
        email_id=email["id"],
        sender=email["sender"],
        subject=email["subject"],
        body=email["body"],
        status=status,
        is_processed=has_results,  # <-- Added flag for frontend to consume
        claimed_details=claimed_details,
        workday_details=workday_details,
        field_results=field_results,
        all_fields_match=all_fields_match,
        recommended_reply=recommended_reply_text,
        attachments=[AttachmentResponse(**attachment) for attachment in email.get("attachments", [])],
    )
