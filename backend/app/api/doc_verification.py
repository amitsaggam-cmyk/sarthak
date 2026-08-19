from pathlib import Path
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_module_access, require_module_write_access
from app.db.models import User
from app.db.session import get_session
from app.models.schemas import (
    DocumentVerificationDriveSubmitRequest,
    DocumentVerificationSubmissionDetail,
    DocumentVerificationSubmissionSummary,
    DocumentVerificationSubmitResponse,
    DocumentVerificationManualChangesRequest,
    CandidateSummaryResponse,
)
from app.services.doc_verification.repository import DocumentVerificationRepository
from app.services.doc_verification.service import (
    DocumentVerificationService,
    process_document_verification_submission,
)


router = APIRouter(prefix="/api/doc-verification", tags=["Document Verification"])
logger = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[2]


def _resolve_stored_file_path(file_path: str) -> Path:
    path = Path(file_path)
    if path.exists():
        return path

    if not path.is_absolute():
        backend_relative = BACKEND_DIR / path
        if backend_relative.exists():
            return backend_relative

    return path


def _service(session: AsyncSession) -> DocumentVerificationService:
    """Build route-scoped services around the request's database session."""

    return DocumentVerificationService(DocumentVerificationRepository(session))


@router.get(
    "/submissions",
    response_model=list[DocumentVerificationSubmissionSummary],
)
async def list_submissions(
    current_user: User = Depends(require_module_access("document_verification")),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentVerificationSubmissionSummary]:
    try:
        submissions = await _service(session).list_submissions()
        logger.info(
            "[DOC_VERIFY] Listed submissions user=%s count=%s",
            current_user.email,
            len(submissions),
        )
        return submissions
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable while loading document submissions.",
        ) from exc


@router.post(
    "/submit",
    response_model=DocumentVerificationSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_documents(
    background_tasks: BackgroundTasks,
    candidate_name: str = Form(default=""),
    files: list[UploadFile] = File(...),
    current_user: User = Depends(require_module_access("document_verification")),
    session: AsyncSession = Depends(get_session),
) -> DocumentVerificationSubmitResponse:
    try:
        submission_id = await _service(session).submit(candidate_name, files, current_user)
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable while saving document submission.",
        ) from exc

    background_tasks.add_task(process_document_verification_submission, submission_id)
    logger.info(
        "[DOC_VERIFY] Queued local submission processing user=%s submission_id=%s",
        current_user.email,
        submission_id,
    )
    return DocumentVerificationSubmitResponse(
        message="Document submission saved. Verification processing has started.",
        submission_id=submission_id,
    )


@router.post(
    "/drive-submit",
    response_model=DocumentVerificationSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_google_drive_documents(
    request: DocumentVerificationDriveSubmitRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_module_access("document_verification")),
    session: AsyncSession = Depends(get_session),
) -> DocumentVerificationSubmitResponse:
    try:
        submission_id = await _service(session).submit_from_google_drive(
            request.candidate_name,
            request.drive_url,
            current_user,
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable while saving Google Drive document submission.",
        ) from exc

    background_tasks.add_task(process_document_verification_submission, submission_id)
    logger.info(
        "[DOC_VERIFY] Queued Google Drive submission processing user=%s submission_id=%s",
        current_user.email,
        submission_id,
    )
    return DocumentVerificationSubmitResponse(
        message="Google Drive documents imported. Verification processing has started.",
        submission_id=submission_id,
    )


@router.get(
    "/submissions/{submission_id}",
    response_model=DocumentVerificationSubmissionDetail,
)
async def get_submission_detail(
    submission_id: int,
    current_user: User = Depends(require_module_access("document_verification")),
    session: AsyncSession = Depends(get_session),
) -> DocumentVerificationSubmissionDetail:
    try:
        detail = await _service(session).detail(submission_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable while loading document submission.",
        ) from exc

    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
    logger.info(
        "[DOC_VERIFY] Loaded submission detail user=%s submission_id=%s",
        current_user.email,
        submission_id,
    )
    return detail


@router.patch(
    "/submissions/{submission_id}/manual-changes",
    response_model=DocumentVerificationSubmissionDetail,
)
async def confirm_manual_changes(
    submission_id: int,
    request: DocumentVerificationManualChangesRequest,
    current_user: User = Depends(require_module_write_access("document_verification")),
    session: AsyncSession = Depends(get_session),
) -> DocumentVerificationSubmissionDetail:
    try:
        service = _service(session)
        applied = await service.apply_manual_changes(
            submission_id,
            [change.model_dump() for change in request.changes],
        )
        if not applied:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
        detail = await service.detail(submission_id)
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable while confirming manual changes.",
        ) from exc

    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
    logger.info(
        "[DOC_VERIFY] Confirmed manual changes user=%s submission_id=%s count=%s",
        current_user.email,
        submission_id,
        len(request.changes),
    )
    return detail


@router.get(
    "/submissions/{submission_id}/candidate-summary",
    response_model=CandidateSummaryResponse,
)
async def get_candidate_summary(
    submission_id: int,
    current_user: User = Depends(require_module_access("document_verification")),
    session: AsyncSession = Depends(get_session),
) -> CandidateSummaryResponse:
    try:
        summary = await _service(session).candidate_summary(submission_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable while loading candidate summary.",
        ) from exc
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
    return summary


@router.get("/files/{file_id}/download")
async def download_submission_file(
    file_id: int,
    current_user: User = Depends(require_module_access("document_verification")),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    try:
        file = await _service(session).file(file_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable while loading document file.",
        ) from exc

    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    file_path = _resolve_stored_file_path(file.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing on disk.")

    return FileResponse(
        file_path,
        media_type=file.content_type or "application/octet-stream",
        filename=file.filename,
    )


@router.get("/submissions/{submission_id}/files/{filename}")
async def download_submission_file_by_name(
    submission_id: int,
    filename: str,
    current_user: User = Depends(require_module_access("document_verification")),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    try:
        file = await _service(session).file_by_submission_and_name(submission_id, filename)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable while loading document file.",
        ) from exc

    if not file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    file_path = _resolve_stored_file_path(file.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing on disk.")

    return FileResponse(
        file_path,
        media_type=file.content_type or "application/octet-stream",
        filename=file.filename,
    )
