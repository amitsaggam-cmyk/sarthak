import asyncio
import email
import imaplib
import re
from dataclasses import dataclass
from email.header import decode_header, make_header
from email.message import Message
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Email, EmailAttachment
from app.db.session import AsyncSessionLocal


@dataclass
class ParsedAttachment:
    filename: str
    content_type: str | None
    payload: bytes


@dataclass
class ParsedMail:
    message_id: str
    sender: str
    subject: str
    body: str
    attachments: list[ParsedAttachment]


def _decode(value: str | None) -> str:
    return str(make_header(decode_header(value or ""))).strip()


def _body_from_message(message: Message) -> tuple[str, list[ParsedAttachment]]:
    body_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[ParsedAttachment] = []

    for part in message.walk():
      content_disposition = part.get_content_disposition()
      content_type = part.get_content_type()
      payload = part.get_payload(decode=True) or b""

      if content_disposition == "attachment":
          filename = _decode(part.get_filename()) or f"attachment-{uuid4().hex}"
          attachments.append(ParsedAttachment(filename, content_type, payload))
          continue

      if content_type == "text/plain" and payload:
          charset = part.get_content_charset() or "utf-8"
          body_parts.append(payload.decode(charset, errors="replace"))
      elif content_type == "text/html" and payload:
          charset = part.get_content_charset() or "utf-8"
          html_parts.append(payload.decode(charset, errors="replace"))

    if not body_parts and message.get_payload(decode=True):
        charset = message.get_content_charset() or "utf-8"
        body_parts.append(message.get_payload(decode=True).decode(charset, errors="replace"))

    if not body_parts and html_parts:
        html_text = "\n\n".join(html_parts)
        html_text = re.sub(r"<br\s*/?>", "\n", html_text, flags=re.IGNORECASE)
        html_text = re.sub(r"</p\s*>", "\n", html_text, flags=re.IGNORECASE)
        html_text = re.sub(r"<[^>]+>", " ", html_text)
        body_parts.append(re.sub(r"\s+", " ", html_text).strip())

    return "\n\n".join(body_parts).strip(), attachments


def _fetch_from_imap() -> list[ParsedMail]:
    settings = get_settings()
    mails: list[ParsedMail] = []

    with imaplib.IMAP4_SSL(settings.gmail_imap_host, settings.gmail_imap_port) as mailbox:
        mailbox.login(settings.gmail_imap_username, settings.gmail_imap_password)
        mailbox.select(settings.gmail_imap_mailbox)
        _, search_data = mailbox.search(None, settings.gmail_imap_search_criteria)

        for message_num in search_data[0].split():
            _, message_data = mailbox.fetch(message_num, "(RFC822)")
            raw_message = message_data[0][1]
            message = email.message_from_bytes(raw_message)
            body, attachments = _body_from_message(message)
            mails.append(
                ParsedMail(
                    message_id=message.get("Message-ID") or f"imap-{message_num.decode()}",
                    sender=_decode(message.get("From")),
                    subject=_decode(message.get("Subject")) or "No subject",
                    body=body,
                    attachments=attachments,
                )
            )

    return mails


async def ingest_gmail_messages() -> int:
    """Fetch Gmail IMAP messages and persist unseen emails plus attachments."""

    settings = get_settings()
    if not settings.gmail_imap_username or not settings.gmail_imap_password:
        return 0

    parsed_mails = await asyncio.to_thread(_fetch_from_imap)
    attachment_root = Path(settings.gmail_attachment_dir)
    attachment_root.mkdir(parents=True, exist_ok=True)
    inserted = 0

    async with AsyncSessionLocal() as session:
        for parsed in parsed_mails:
            existing = await session.scalar(
                select(Email.id).where(Email.external_message_id == parsed.message_id)
            )
            if existing:
                continue

            email_row = Email(
                external_message_id=parsed.message_id,
                sender=parsed.sender,
                subject=parsed.subject,
                body=parsed.body,
                status="pending",
                processing_status="new",
            )
            session.add(email_row)
            await session.flush()

            for attachment in parsed.attachments:
                stored_name = f"{email_row.id}-{uuid4().hex}-{attachment.filename}"
                file_path = attachment_root / stored_name
                file_path.write_bytes(attachment.payload)
                session.add(
                    EmailAttachment(
                        email_id=email_row.id,
                        filename=attachment.filename,
                        content_type=attachment.content_type,
                        file_path=str(file_path),
                        size_bytes=len(attachment.payload),
                    )
                )

            inserted += 1

        await session.commit()

    return inserted
