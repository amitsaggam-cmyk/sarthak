import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import router
from app.core.config import get_settings
from app.db.init_db import initialize_database
from app.api.auth import router as auth_router
from app.services.gmail_imap_ingestor import ingest_gmail_messages
from app.services.verification_processor import process_pending_emails


def configure_logging() -> None:
    """Make backend workflow steps visible in the terminal."""

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def gmail_ingestion_loop() -> None:
    """Poll Gmail IMAP in the background when enabled in `.env`."""

    while True:
        settings = get_settings()
        try:
            logging.getLogger(__name__).info("[LOOP] Gmail ingestion tick")
            await ingest_gmail_messages()
        except Exception as exc:
            logging.getLogger(__name__).exception("[LOOP] Gmail ingestion failed: %s", exc)
        await asyncio.sleep(settings.mail_poll_interval)


async def verification_processing_loop() -> None:
    """Process stored emails one batch at a time without blocking requests."""

    while True:
        settings = get_settings()
        try:
            logging.getLogger(__name__).info(
                "[LOOP] Verification processing tick batch_size=%s",
                settings.mail_processing_batch_size,
            )
            await process_pending_emails(limit=settings.mail_processing_batch_size)
        except Exception as exc:
            logging.getLogger(__name__).exception("[LOOP] Verification processing failed: %s", exc)
        await asyncio.sleep(settings.mail_poll_interval)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    configure_logging()
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=settings.app_description,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router)
    return application


app = create_app()
app.include_router(
    auth_router,
    prefix="/api",
)

@app.on_event("startup")
async def startup() -> None:
    """Ensure database tables exist when the app is configured for MySQL."""

    if get_settings().email_source.lower() == "file":
        return
    try:
        logging.getLogger(__name__).info("[STARTUP] Initializing database")
        await initialize_database()
    except SQLAlchemyError as exc:
        logging.getLogger(__name__).exception("[STARTUP] Database startup check failed: %s", exc)
    settings = get_settings()
    if settings.enable_background_ingestion:
        logging.getLogger(__name__).info("[STARTUP] Starting Gmail ingestion background loop")
        asyncio.create_task(gmail_ingestion_loop())
    if settings.enable_background_processing:
        logging.getLogger(__name__).info("[STARTUP] Starting verification processing background loop")
        asyncio.create_task(verification_processing_loop())
