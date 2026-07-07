import json

from sqlalchemy import select, update

from app.db.models import Email, EmailAttachment
from app.db.session import AsyncSessionLocal
from app.models.schemas import EmailSummaryResponse
from app.services.email_sources.base import EmailSource


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
                status=row.status,
                processing_status=row.processing_status,
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

        return {
            "id": row.id,
            "sender": row.sender,
            "subject": row.subject,
            "body": row.body,
            "claimed_employee_name": row.claimed_employee_name,
            "claimed_date_of_joining": row.claimed_date_of_joining,
            "claimed_last_working_day": row.claimed_last_working_day,
            "workday_employee_name": row.workday_employee_name,
            "workday_date_of_joining": row.workday_date_of_joining,
            "workday_last_working_day": row.workday_last_working_day,
            "field_results": json.loads(row.field_results_json or "[]"),
            "all_fields_match": row.all_fields_match,
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
            "status": row.status,
            "processing_status": row.processing_status,
            "received_at": row.received_at,
        }

    async def mark_reviewed(self, email_id: int) -> bool:
        """Mark a DB-backed email as pending when HR opens it."""

        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Email)
                .where(Email.id == email_id, Email.processing_status == "new")
                .values(processing_status="pending")
            )
            await session.commit()
        return True
