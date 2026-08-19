import json

from sqlalchemy import select, update

from app.db.models import Email, EmailAttachment
from app.db.session import AsyncSessionLocal
from app.models.schemas import EmailSummaryResponse
from app.services.email_sources.base import EmailSource


def _normalize_mail_status(value: str | None) -> str:
    if value in {"new", "pending", "completed"}:
        return value
    if value == "reviewed":
        return "pending"
    if value in {"approved", "rejected"}:
        return "completed"
    return "new"


def _normalize_processing_status(value: str | None) -> str:
    allowed = {"new", "pending", "processed", "error", "completed"}
    return value if value in allowed else "new"


class DatabaseEmailSource(EmailSource):
    """Read verification requests from the configured MySQL database."""

    async def list_pending_emails(self) -> list[EmailSummaryResponse]:
        """Fetch inbox rows from MySQL for the review table."""

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Email).order_by(Email.received_at.desc()))
            rows = result.scalars().all()

        return [
            EmailSummaryResponse(
                id=row.id,
                sender=row.sender,
                subject=row.subject,
                status=_normalize_mail_status(row.status),
                processing_status=_normalize_processing_status(row.processing_status),
                received_at=row.received_at,
            )
            for row in rows
        ]

    async def get_email(self, email_id: int) -> dict | None:
        """Fetch one email body from MySQL for parsing and verification."""

        async with AsyncSessionLocal() as session:
            row = await session.get(Email, email_id)
            attachment_result = await session.execute(
                select(EmailAttachment).where(EmailAttachment.email_id == email_id)
            )
            attachments = attachment_result.scalars().all()

        if not row:
            return None

        # Rehydrate field results to pass down to the reply generator dynamically
        from app.models.schemas import FieldMatchResult
        from app.services.reply_builder import build_recommended_reply

        parsed_results = [FieldMatchResult(**res) for res in json.loads(row.field_results_json or "[]")]
        recommended_obj = build_recommended_reply(row.id, row.sender, row.subject, parsed_results)

        return {
            "id": row.id,
            "sender": row.sender,
            "subject": row.subject,
            "body": row.body,
            "claimed_candidate_name": row.claimed_candidate_name,
            "claimed_employee_id": row.claimed_employee_id,
            "claimed_nature_of_employment": row.claimed_nature_of_employment,
            "claimed_start_date": row.claimed_start_date,
            "claimed_end_date": row.claimed_end_date,
            "claimed_last_designation": row.claimed_last_designation,
            "claimed_location": row.claimed_location,
            "claimed_exit_formalities_completed": row.claimed_exit_formalities_completed,
            "workday_candidate_name": row.workday_candidate_name,
            "workday_employee_id": row.workday_employee_id,
            "workday_nature_of_employment": row.workday_nature_of_employment,
            "workday_start_date": row.workday_start_date,
            "workday_end_date": row.workday_end_date,
            "workday_last_designation": row.workday_last_designation,
            "workday_location": row.workday_location,
            "workday_exit_formalities_completed": row.workday_exit_formalities_completed,
            "field_results": json.loads(row.field_results_json or "[]"),
            "all_fields_match": row.all_fields_match,
            "recommended_reply": recommended_obj.body,
            "processing_error": row.processing_error,
            "attachments": [
                {
                    "id": attachment.id,
                    "filename": attachment.filename,
                    "content_type": attachment.content_type,
                    "size_bytes": attachment.size_bytes,
                }
                for attachment in attachments
            ],
            "status": _normalize_mail_status(row.status),
            "processing_status": _normalize_processing_status(row.processing_status),
            "received_at": row.received_at,
        }

    async def mark_reviewed(self, email_id: int) -> bool:
        """Mark a DB-backed email as pending when HR opens it."""

        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Email)
                .where(Email.id == email_id, Email.status == "new")
                .values(status="pending")
            )
            await session.commit()
        return True
