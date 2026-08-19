from abc import ABC, abstractmethod

from app.models.schemas import EmailSummaryResponse


class EmailSource(ABC):
    """Shared contract for current MySQL and future Gmail email readers."""

    @abstractmethod
    async def list_pending_emails(self) -> list[EmailSummaryResponse]:
        """Return emails waiting for HR review."""

    @abstractmethod
    async def get_email(self, email_id: int) -> dict | None:
        """Return one full email record by id."""

    async def mark_reviewed(self, email_id: int) -> bool:
        """Mark an email as opened by HR when the source supports updates."""

        return False
