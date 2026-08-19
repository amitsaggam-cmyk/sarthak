from typing import Any


def generate_final_verdict(
    rule_report: dict[str, Any],
    processing_errors: list[str],
) -> dict[str, Any]:
    if processing_errors:
        return {
            "status": "SYSTEM_ERROR",
            "summary": "Pipeline encountered file processing errors that prevented full analysis.",
            "action_items": [f"[System Error] {error}" for error in processing_errors],
            "hr_context_notes": [],
        }

    action_items = list(rule_report.get("issues", []))
    pending_docs = list(rule_report.get("pending_documents", []))

    if action_items:
        status = "NEEDS_HUMAN_REVIEW"
        summary = f"Dossier flagged for HR review with {len(action_items)} total issue(s)."
    elif pending_docs:
        status = "PENDING_DOCUMENTS"
        summary = f"Dossier passes current checks, but waits on {len(pending_docs)} deferred document(s)."
        action_items.extend([f"[Pending Document] {doc}" for doc in pending_docs])
    else:
        status = "VERIFIED"
        summary = "Candidate dossier is verified, compliant, and ready for payroll onboarding."

    return {
        "status": status,
        "summary": summary,
        "action_items": action_items,
        "hr_context_notes": [],
    }
