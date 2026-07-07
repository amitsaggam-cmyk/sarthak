from app.core.config import get_settings
from app.services.email_sources.base import EmailSource
from app.services.email_sources.database_source import DatabaseEmailSource
from app.services.email_sources.file_source import FileEmailSource


def get_email_source() -> EmailSource:
    """Choose the configured email source while keeping API routes unchanged."""

    source = get_settings().email_source.lower()
    if source == "file":
        return FileEmailSource()
    # Gmail IMAP is an ingestion source; reviewed emails are served from SQL after storage.
    return DatabaseEmailSource()
