from app.models.schemas import EmailSummaryResponse
from app.services.email_sources.base import EmailSource


class GmailEmailSource(EmailSource):
    """Future Gmail reader placeholder that follows the same email-source contract."""

    async def list_pending_emails(self) -> list[EmailSummaryResponse]:
        """Signal that Gmail integration still needs OAuth implementation."""

        raise NotImplementedError("Gmail source is prepared but not connected yet.")

    async def get_email(self, email_id: int) -> dict | None:
        """Signal that Gmail integration still needs message fetching implementation."""

        raise NotImplementedError("Gmail source is prepared but not connected yet.")
