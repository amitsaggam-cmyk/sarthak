from app.models.schemas import FieldMatchResult, SafeReplyResponse




def build_recommended_reply(
    email_id: int,
    reply_to: str,
    subject: str,
    field_results: list[FieldMatchResult],
) -> SafeReplyResponse:
    """Build a rich outbound text response with dynamic text list or fallback rejection terms."""
   
    required_match_fields = [
        result for result in field_results
        if result.field != "exit_formalities_completed"
    ]
    all_match = all(result.matches for result in required_match_fields)
   
    if all_match:
        rows = [
            "Hello,\n\n",
            "Based on our background check verification rules, the details match our internal database records:\n\n"
        ]

        for res in field_results:
            clean_label = res.field.replace("_", " ").title()
            system_value = str(res.workday_value) if res.workday_value is not None else "N/A"
            rows.append(f"{clean_label}: {system_value}\n")

        rows.extend([
            "\nRegards,\nHR Verification Team"
        ])
        body = "".join(rows)
    else:
        body = (
            "Hello,\n\n"
            "You need to fill the fields that you require to verify.\n\n"
            "Regards,\nHR Verification Team"
        )


    return SafeReplyResponse(
        email_id=email_id,
        reply_to=reply_to,
        subject=f"Re: {subject}",
        body=body,
    )
