import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.api.auth import router as auth_router
from app.api.doc_verification import router as doc_verification_router
from app.api.routes import router
from app.core.config import get_settings
from app.db.init_db import initialize_database
from app.services.gmail_imap_ingestor import ingest_gmail_messages
from app.services.verification_processor import process_pending_emails


def configure_logging() -> None:
    """Configure application logging."""

    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


logger = logging.getLogger(__name__)


async def gmail_ingestion_loop() -> None:
    """Continuously poll Gmail IMAP for new emails."""

    while True:
        settings = get_settings()

        try:
            logger.info("[GMAIL] Polling inbox...")
            inserted = await ingest_gmail_messages()
            logger.info("[GMAIL] %s new email(s) inserted.", inserted)

        except Exception:
            logger.exception("[GMAIL] Background ingestion failed.")

        await asyncio.sleep(settings.mail_poll_interval)


async def verification_processing_loop() -> None:
    """Continuously process pending verification emails."""

    while True:
        settings = get_settings()

        try:
            logger.info(
                "[PROCESSOR] Processing pending emails (batch=%s)",
                settings.mail_processing_batch_size,
            )

            await process_pending_emails(
                limit=settings.mail_processing_batch_size
            )

        except Exception:
            logger.exception("[PROCESSOR] Background processing failed.")

        await asyncio.sleep(settings.mail_poll_interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles application startup and shutdown.
    """

    logger.info("========== APPLICATION STARTING ==========")

    gmail_task = None
    processor_task = None

    settings = get_settings()

    if settings.email_source.lower() != "file":
        try:
            logger.info("[STARTUP] Initializing database...")
            await initialize_database()
            logger.info("[STARTUP] Database initialized.")

        except SQLAlchemyError:
            logger.exception("[STARTUP] Database initialization failed.")

        if settings.enable_background_ingestion:
            logger.info("[STARTUP] Starting Gmail ingestion loop.")
            gmail_task = asyncio.create_task(gmail_ingestion_loop())

        if settings.enable_background_processing:
            logger.info("[STARTUP] Starting verification processor.")
            processor_task = asyncio.create_task(
                verification_processing_loop()
            )

    logger.info("========== APPLICATION READY ==========")

    yield

    logger.info("========== APPLICATION SHUTTING DOWN ==========")

    tasks = [gmail_task, processor_task]

    for task in tasks:
        if task:
            task.cancel()

    for task in tasks:
        if task:
            try:
                await task
            except asyncio.CancelledError:
                logger.info("Background task stopped.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    configure_logging()

    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=settings.app_description,
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(router)
    application.include_router(doc_verification_router)
    application.include_router(
        auth_router,
        prefix="/api",
    )

    return application


app = create_app()
