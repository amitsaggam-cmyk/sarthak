from app.models.schemas import FieldMatchResult, SafeReplyResponse


def build_recommended_reply(
    email_id: int,
    reply_to: str,
    subject: str,
    field_results: list[FieldMatchResult],
) -> SafeReplyResponse:
    """Build a minimal outbound response that never includes internal employee data."""

    all_match = all(result.matches for result in field_results)
    if all_match:
        body = (
            "Hello,\n\n"
            "Based on the limited verification fields permitted by our policy, "
            "the submitted date of joining and last working day match our records.\n\n"
            "Regards,\nHR Verification Team"
        )
    else:
        body = (
            "Hello,\n\n"
            "Based on the limited verification fields permitted by our policy, "
            "we are unable to confirm that the submitted details match our records.\n\n"
            "Regards,\nHR Verification Team"
        )

    return SafeReplyResponse(
        email_id=email_id,
        reply_to=reply_to,
        subject=f"Re: {subject}",
        body=body,
    )
