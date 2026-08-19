import json
from pathlib import Path

from app.core.config import get_settings
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


def _email_file_path() -> Path:
    """Resolve the file-backed inbox path relative to the backend folder."""

    backend_root = Path(__file__).resolve().parents[3]
    return backend_root / get_settings().email_file_path


class FileEmailSource(EmailSource):
    """Read and update verification requests from a local JSON file."""

    def _load_emails(self) -> list[dict]:
        """Load all email records from the JSON inbox file."""

        with _email_file_path().open("r", encoding="utf-8") as file:
            return json.load(file)

    def _save_emails(self, emails: list[dict]) -> None:
        """Persist updated email records back to the JSON inbox file."""

        with _email_file_path().open("w", encoding="utf-8") as file:
            json.dump(emails, file, indent=2)

    async def list_pending_emails(self) -> list[EmailSummaryResponse]:
        """Return file-backed emails sorted newest first."""

        emails = sorted(
            self._load_emails(),
            key=lambda email: email["received_at"],
            reverse=True,
        )
        return [
            EmailSummaryResponse(
                **{
                    **email,
                    "status": _normalize_mail_status(email.get("status")),
                    "processing_status": _normalize_processing_status(
                        email.get("processing_status")
                    ),
                }
            )
            for email in emails
        ]

    async def get_email(self, email_id: int) -> dict | None:
        """Return one full email record from the JSON inbox."""

        for email in self._load_emails():
            if email["id"] == email_id:
                return {
                    **email,
                    "status": _normalize_mail_status(email.get("status")),
                    "processing_status": _normalize_processing_status(
                        email.get("processing_status")
                    ),
                }
        return None

    async def mark_reviewed(self, email_id: int) -> bool:
        """Mark an email as opened by HR."""

        emails = self._load_emails()

        for email in emails:
            if email["id"] == email_id:

                # Only change NEW -> PENDING
                if _normalize_mail_status(email.get("status")) == "new":
                    email["status"] = "pending"

                self._save_emails(emails)
                return True

        return False
