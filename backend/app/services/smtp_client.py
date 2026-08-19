from email.message import EmailMessage
import smtplib
import ssl
import asyncio
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)

def _send_smtp_message(from_addr: str, to_addr: str, subject: str, body: str) -> None:
    settings = get_settings()
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    # Use SMTP_SSL for port 465, or standard SMTP with starttls for port 587
    context = ssl.create_default_context()
    
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context) as server:
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls(context=context)
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
            
    logger.info(f"[SMTP] Successfully sent outbound email to {to_addr}")


async def send_password_reset_email(to_addr: str, pin: str, reset_url: str) -> bool:
    subject = "Reset your password"
    body = (
        "Hello,\n\n"
        "We received a request to reset your password.\n\n"
        f"Your reset PIN is: {pin}\n\n"
        "Enter this PIN on the reset page within 30 minutes, then choose a new password.\n\n"
        "Reset page:\n"
        f"{reset_url}\n\n"
        "If you did not request this reset, please ignore this message.\n"
    )

    return await send_outbound_email(to_addr, subject, body)


async def send_outbound_email(to_addr: str, subject: str, body: str) -> bool:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_username:
        logger.warning("[SMTP] SMTP not configured; skipping send")
        return False
        
    try:
        # Runs the blocking SMTP call in a separate thread so FastAPI stays fast
        await asyncio.to_thread(
            _send_smtp_message, 
            settings.smtp_username, 
            to_addr, 
            subject, 
            body
        )
        return True
    except Exception as exc:
        logger.exception(f"[SMTP] Failed to send email to {to_addr}: {exc}")
        return False