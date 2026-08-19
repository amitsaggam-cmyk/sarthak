from datetime import datetime, timezone
import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import get_current_user, require_module_access
from app.db.models import User, UserManagementAudit
from app.db.models import (
    DocumentVerificationFile,
    DocumentVerificationSubmission,
    Email,
    EmailAttachment,
    VerificationDecision,
)
from app.db.session import AsyncSessionLocal
from app.models.schemas import (
    AuditLogResponse,
    DecisionRequest,
    DecisionResponse,
    DecisionLogResponse,
    EmailSummaryResponse,
    LlmTestRequest,
    LlmTestResponse,
    SafeReplyResponse,
    VerificationResponse,
)
from app.core.config import get_settings
from app.services.email_source_factory import get_email_source
from app.services.email_sources.file_source import FileEmailSource
from app.services.llm_client import test_llm_chat
from app.services.reply_builder import build_recommended_reply
from app.services.gmail_imap_ingestor import ingest_gmail_messages
from app.services.verification import verify_email
from app.services.verification_processor import process_pending_emails
from app.services.smtp_client import send_outbound_email  # Added SMTP client import

router = APIRouter(prefix="/api", tags=["HR Verification"])
logger = logging.getLogger(__name__)


def _json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return loaded if isinstance(loaded, list) else []


def _email_audit_status(decision: str, email: Email) -> str:
    if email.processing_error:
        return "FAILED"
    if decision == "reject_reply" or email.all_fields_match is False:
        return "FLAGGED"
    return "SUCCESS"


def _doc_audit_status(submission: DocumentVerificationSubmission) -> str:
    if submission.processing_error or submission.pipeline_status_raw == "SYSTEM_ERROR":
        return "FAILED"
    if submission.status == "VERIFIED":
        return "SUCCESS"
    return "FLAGGED"


def _trace_id(prefix: str, row_id: int, timestamp: datetime | None) -> str:
    date_part = (timestamp or datetime.now(timezone.utc)).strftime("%Y%m%d")
    return f"trace-{prefix.lower()}-{date_part}-{row_id:04d}"


def _log_id(prefix: str, row_id: int, timestamp: datetime | None) -> str:
    date_part = (timestamp or datetime.now(timezone.utc)).strftime("%Y%m%d")
    return f"LOG-{prefix}-{date_part}-{row_id:04d}"


def _field_discrepancies(email: Email) -> list[dict[str, str]]:
    rows = _json_list(email.field_results_json)
    discrepancies = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        discrepancies.append(
            {
                "item": str(row.get("field") or "Field").replace("_", " ").title(),
                "claimed": str(row.get("claimed_value") or "Missing"),
                "verified": str(row.get("workday_value") or "Not found"),
                "status": "Matched" if row.get("matches") else "Flagged",
            }
        )
    return discrepancies


def raise_database_unavailable(exc: SQLAlchemyError) -> None:
    """Return a clear API error when MySQL is not reachable."""

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database unavailable. Start MySQL on localhost:3306 and ensure hr_background_verification_db exists.",
    ) from exc


def _file_decision_logs(current_user: User) -> list[DecisionLogResponse]:
    email_source = get_email_source()

    if not isinstance(email_source, FileEmailSource):
        return []

    logs: list[DecisionLogResponse] = []

    for item in email_source._load_emails():
        stored_decision = item.get("decision")
        status_value = item.get("status")

        if stored_decision in {"approve_reply", "reject_reply"}:
            decision = stored_decision
        elif status_value in {"approved", "rejected"}:
            decision = "approve_reply" if status_value == "approved" else "reject_reply"
        else:
            continue

        decided_at = item.get("decision_at") or item.get("received_at")

        logs.append(
            DecisionLogResponse(
                id=item["id"],
                email_id=item["id"],
                email_subject=item["subject"],
                user_full_name=item.get("decision_by_name") or current_user.full_name,
                user_email=item.get("decision_by_email") or current_user.email,
                decision=decision,
                note=item.get("decision_note"),
                sent_reply=item.get("sent_reply"),
                decided_at=decided_at,
            )
        )

    return sorted(logs, key=lambda log: log.decided_at, reverse=True)


@router.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> dict[str, str]:
    """Return a simple health signal for local demos and UI checks."""

    return {"status": "ok"}


@router.post("/llm/test", response_model=LlmTestResponse)
async def test_llm_connection(request: LlmTestRequest) -> LlmTestResponse:
    """Test connectivity to the configured Azure OpenAI chat deployment."""

    settings = get_settings()

    try:
        message = await test_llm_chat(request.prompt)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM connection failed: {exc}",
        ) from exc

    return LlmTestResponse(
        provider=settings.llm_provider,
        model=settings.azure_openai_deployment,
        success=True,
        message=message,
    )


@router.get("/emails", response_model=list[EmailSummaryResponse])
async def list_emails(current_user: User = Depends(require_module_access("background_verification"))) -> list[EmailSummaryResponse]:
    """List emails available from the configured source."""

    try:
        return await get_email_source().list_pending_emails()
    except SQLAlchemyError as exc:
        raise_database_unavailable(exc)


@router.post("/ingest/gmail", status_code=status.HTTP_202_ACCEPTED)
async def ingest_gmail(current_user: User = Depends(require_module_access("background_verification"))) -> dict[str, int]:
    """Manually pull Gmail IMAP messages into SQL."""

    logger.info("[API] Gmail ingestion requested by user=%s", current_user.email)
    inserted = await ingest_gmail_messages()
    logger.info("[API] Gmail ingestion completed inserted=%s", inserted)
    return {"inserted": inserted}


@router.post("/process", status_code=status.HTTP_202_ACCEPTED)
async def process_emails(current_user: User = Depends(require_module_access("background_verification"))) -> dict[str, int]:
    """Manually process stored emails through LLM + Workday matching."""

    settings = get_settings()
    logger.info(
        "[API] Verification processing requested by user=%s batch_size=%s",
        current_user.email,
        settings.mail_processing_batch_size,
    )
    processed = await process_pending_emails()
    logger.info("[API] Verification processing completed processed=%s", processed)
    return {"processed": processed}


@router.get("/attachments/{attachment_id}/download")
async def download_attachment(
    attachment_id: int,
    current_user: User = Depends(require_module_access("background_verification")),
) -> FileResponse:
    """Download an attachment saved during Gmail IMAP ingestion."""

    async with AsyncSessionLocal() as session:
        attachment = await session.get(EmailAttachment, attachment_id)

    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found.")

    file_path = Path(attachment.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment file missing.")

    return FileResponse(
        file_path,
        media_type=attachment.content_type or "application/octet-stream",
        filename=attachment.filename,
    )


@router.get("/decision-logs", response_model=list[DecisionLogResponse])
async def list_decision_logs_legacy(
    current_user: User = Depends(require_module_access("background_verification")),
) -> list[DecisionLogResponse]:
    """Return legacy decision audit rows."""

    email_source = get_email_source()
    logger.info("[API] Decision logs requested by user=%s", current_user.email)

    if isinstance(email_source, FileEmailSource):
        return _file_decision_logs(current_user)

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(VerificationDecision, Email, User)
                .join(Email, VerificationDecision.email_id == Email.id)
                .outerjoin(User, VerificationDecision.user_id == User.id)
                .order_by(VerificationDecision.decided_at.desc())
            )
            rows = result.all()
    except SQLAlchemyError as exc:
        raise_database_unavailable(exc)

    return [
        DecisionLogResponse(
            id=decision.id,
            email_id=email.id,
            email_subject=email.subject,
            user_full_name=user.full_name if user else None,
            user_email=user.email if user else None,
            decision=decision.decision,
            note=decision.note,
            sent_reply=decision.sent_reply,
            decided_at=decision.decided_at,
        )
        for decision, email, user in rows
    ]


@router.get("/logs", response_model=list[AuditLogResponse])
async def list_audit_logs(
    current_user: User = Depends(get_current_user),
) -> list[AuditLogResponse]:
    """Return a unified dynamic audit feed from application tables."""

    email_source = get_email_source()
    logger.info("[API] Unified audit logs requested by user=%s", current_user.email)
    audit_logs: list[AuditLogResponse] = []

    if isinstance(email_source, FileEmailSource):
        for log in _file_decision_logs(current_user):
            status_value = "SUCCESS" if log.decision == "approve_reply" else "FLAGGED"
            audit_logs.append(
                AuditLogResponse(
                    id=f"email-file-{log.id}",
                    timestamp=log.decided_at,
                    log_id=_log_id("EMAIL", log.id, log.decided_at),
                    module="EMAIL_BGV",
                    action="Verification reply sent",
                    actor_name=log.user_full_name or log.user_email or "Unknown user",
                    target=log.email_subject,
                    status=status_value,
                    details={
                        "senderEmail": "File email source",
                        "recipientInbox": "Background verification inbox",
                        "emailSubject": log.email_subject,
                        "candidateName": log.email_subject,
                        "outcome": status_value,
                        "verifiedStartDate": "Not available",
                        "verifiedEndDate": "Not available",
                        "discrepancies": [],
                        "attachmentFilename": "No attachment captured",
                        "traceId": _trace_id("email", log.id, log.decided_at),
                    },
                )
            )

    try:
        async with AsyncSessionLocal() as session:
            if not isinstance(email_source, FileEmailSource):
                decision_rows = await session.execute(
                    select(VerificationDecision, Email, User)
                    .join(Email, VerificationDecision.email_id == Email.id)
                    .outerjoin(User, VerificationDecision.user_id == User.id)
                    .order_by(VerificationDecision.decided_at.desc())
                )
                for decision, email, user in decision_rows.all():
                    attachments = await session.execute(
                        select(EmailAttachment)
                        .where(EmailAttachment.email_id == email.id)
                        .order_by(EmailAttachment.id.asc())
                    )
                    attachment_names = [attachment.filename for attachment in attachments.scalars().all()]
                    status_value = _email_audit_status(decision.decision, email)
                    audit_logs.append(
                        AuditLogResponse(
                            id=f"email-{decision.id}",
                            timestamp=decision.decided_at,
                            log_id=_log_id("EMAIL", decision.id, decision.decided_at),
                            module="EMAIL_BGV",
                            action="Verification reply sent",
                            actor_name=user.full_name if user else "Unknown user",
                            target=email.claimed_candidate_name or email.workday_candidate_name or email.subject,
                            status=status_value,
                            details={
                                "senderEmail": email.sender,
                                "recipientInbox": "Background verification inbox",
                                "emailSubject": email.subject,
                                "candidateName": email.claimed_candidate_name or email.workday_candidate_name or "Not available",
                                "outcome": status_value,
                                "verifiedStartDate": email.workday_start_date or "Not available",
                                "verifiedEndDate": email.workday_end_date or "Not available",
                                "discrepancies": _field_discrepancies(email),
                                "attachmentFilename": ", ".join(attachment_names) if attachment_names else "No attachment processed",
                                "traceId": _trace_id("email", decision.id, decision.decided_at),
                            },
                        )
                    )

            doc_rows = await session.execute(
                select(DocumentVerificationSubmission, User)
                .outerjoin(User, DocumentVerificationSubmission.submitted_by_user_id == User.id)
                .order_by(DocumentVerificationSubmission.created_at.desc())
            )
            for submission, user in doc_rows.all():
                file_rows = await session.execute(
                    select(DocumentVerificationFile)
                    .where(DocumentVerificationFile.submission_id == submission.id)
                    .order_by(DocumentVerificationFile.id.asc())
                )
                issues = [str(issue) for issue in _json_list(submission.issues_json)]
                files = [
                    {
                        "fileName": file.filename,
                        "fileType": file.content_type or "Document",
                        "passed": submission.status == "VERIFIED",
                    }
                    for file in file_rows.scalars().all()
                ]
                status_value = _doc_audit_status(submission)
                audit_logs.append(
                    AuditLogResponse(
                        id=f"doc-{submission.id}",
                        timestamp=submission.updated_at or submission.created_at,
                        log_id=_log_id("DOC", submission.id, submission.created_at),
                        module="DOC_VERIFICATION",
                        action="Document verification processed" if submission.status != "PROCESSING" else "Document verification started",
                        actor_name=user.full_name if user else "Unknown user",
                        target=submission.candidate_name,
                        status=status_value,
                        details={
                            "candidateName": submission.candidate_name,
                            "candidateReferenceId": f"CAND-{submission.id:05d}",
                            "overallDossierStatus": submission.status,
                            "files": files,
                            "flags": issues or ([submission.processing_error] if submission.processing_error else []),
                            "executionDurationMs": 0,
                            "traceId": _trace_id("doc", submission.id, submission.created_at),
                        },
                    )
                )

            user_audit_rows = await session.execute(
                select(UserManagementAudit).order_by(UserManagementAudit.created_at.desc())
            )
            audited_target_user_ids: set[int] = set()
            for audit in user_audit_rows.scalars().all():
                actor = await session.get(User, audit.actor_user_id) if audit.actor_user_id else None
                target_user = await session.get(User, audit.target_user_id) if audit.target_user_id else None
                if audit.target_user_id:
                    audited_target_user_ids.add(audit.target_user_id)
                try:
                    details = json.loads(audit.details_json)
                except json.JSONDecodeError:
                    details = {}

                audit_logs.append(
                    AuditLogResponse(
                        id=f"user-audit-{audit.id}",
                        timestamp=audit.created_at,
                        log_id=_log_id("USERACT", audit.id, audit.created_at),
                        module="USER_MGMT",
                        action=audit.action,
                        actor_name=actor.full_name if actor else "Administrator",
                        target=target_user.full_name if target_user else details.get("targetUserName", "Unknown user"),
                        status=audit.status,
                        details=details,
                    )
                )

            user_rows = await session.execute(select(User).order_by(User.created_at.desc()))
            for user in user_rows.scalars().all():
                if user.id in audited_target_user_ids:
                    continue
                audit_logs.append(
                    AuditLogResponse(
                        id=f"user-{user.id}",
                        timestamp=user.created_at,
                        log_id=_log_id("USER", user.id, user.created_at),
                        module="USER_MGMT",
                        action="User account created",
                        actor_name="System" if user.id == 1 else "Administrator",
                        target=user.full_name,
                        status="SUCCESS" if user.is_active else "FLAGGED",
                        details={
                            "targetUserName": user.full_name,
                            "targetEmail": user.email,
                            "assignedRole": user.role,
                            "actionType": "USER_CREATE",
                            "clientIpAddress": "Not captured",
                            "geographicLocation": "Not captured",
                            "browserUserAgent": "Not captured",
                            "stateChange": {
                                "after": {
                                    "id": user.id,
                                    "full_name": user.full_name,
                                    "email": user.email,
                                    "role": user.role,
                                    "is_active": user.is_active,
                                    "module_access": user.module_access,
                                }
                            },
                        },
                    )
                )
    except SQLAlchemyError as exc:
        raise_database_unavailable(exc)

    return sorted(audit_logs, key=lambda log: log.timestamp, reverse=True)


@router.get(
    "/emails/{email_id}/verification",
    response_model=VerificationResponse,
)
async def get_verification(
    email_id: int,
    current_user: User = Depends(require_module_access("background_verification"))
    ) -> VerificationResponse:
    """Return internal comparison details for human HR review."""

    email_source = get_email_source()

    try:
        # Mark NEW -> PENDING when HR opens the email
        await email_source.mark_reviewed(email_id)

        email = await email_source.get_email(email_id)

    except SQLAlchemyError as exc:
        raise_database_unavailable(exc)

    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found.",
        )

    return verify_email(email)


@router.get(
    "/emails/{email_id}/safe-reply",
    response_model=SafeReplyResponse,
)
async def get_safe_reply(
    email_id: int,
    current_user: User = Depends(require_module_access("background_verification")),
) -> SafeReplyResponse:
    """Return only the minimal reply that can be sent outside the company."""

    try:
        email = await get_email_source().get_email(email_id)
    except SQLAlchemyError as exc:
        raise_database_unavailable(exc)

    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found.",
        )

    verification = verify_email(email)

    return build_recommended_reply(
        email_id=email["id"],
        reply_to=email["sender"],
        subject=email["subject"],
        field_results=verification.field_results,
    )


@router.post(
    "/emails/{email_id}/decision",
    response_model=DecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_decision(
    email_id: int,
    request: DecisionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_module_access("background_verification")),
) -> DecisionResponse:
    """Store HR's final decision and dispatch an outbound email notification via SMTP."""

    email_source = get_email_source()

    try:
        email = await email_source.get_email(email_id)
    except SQLAlchemyError as exc:
        raise_database_unavailable(exc)

    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found.",
        )

    if email.get("status") == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A decision has already been recorded for this email.",
        )

    # ---------------- FILE MODE ---------------- #

    if isinstance(email_source, FileEmailSource):
        emails = email_source._load_emails()

        for item in emails:
            if item["id"] == email_id:
                item["status"] = "completed"
                item["decision"] = request.decision
                item["decision_by_name"] = current_user.full_name
                item["decision_by_email"] = current_user.email
                item["decision_note"] = request.note
                item["sent_reply"] = request.reply_body
                item["decision_at"] = datetime.now(timezone.utc).isoformat()
                break

        email_source._save_emails(emails)

    # ---------------- DATABASE MODE ---------------- #

    else:
        try:
            async with AsyncSessionLocal() as session:
                session.add(
                    VerificationDecision(
                        email_id=email_id,
                        user_id=current_user.id,
                        decision=request.decision,
                        note=request.note,
                        sent_reply=request.reply_body,
                    )
                )

                await session.execute(
                    update(Email)
                    .where(Email.id == email_id)
                    .values(
                        status="completed",
                    )
                )
                await session.commit()

        except SQLAlchemyError as exc:
            raise_database_unavailable(exc)

    # ---------------- Outbound SMTP Transmission Engine ---------------- #
    
    if request.reply_body:
        recipient_email = email.get("sender")
        email_subject = email.get("subject", "Background Verification Update")
        
        # Ensure we don't duplicate "Re: Re:" in the subject line
        reply_subject = email_subject if str(email_subject).lower().startswith("re:") else f"Re: {email_subject}"
        
        if recipient_email:
            background_tasks.add_task(
                send_outbound_email,
                to_addr=recipient_email,
                subject=reply_subject,
                body=request.reply_body
            )
            logger.info("[API] Queued outbound SMTP background task for email_id=%s", email_id)
        else:
            logger.warning("[API] No sender email found to send reply for email_id=%s", email_id)

    return DecisionResponse(
        email_id=email_id,
        decision=request.decision,
        message="Decision saved and email notification queued successfully.",
    )
