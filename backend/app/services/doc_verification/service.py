import logging
import asyncio
from pathlib import Path

from fastapi import UploadFile

from app.db.models import DocumentVerificationFile, User
from app.db.session import AsyncSessionLocal
from app.models.schemas import (
    DocumentVerificationFileResponse,
    DocumentVerificationSubmissionDetail,
    DocumentVerificationSubmissionSummary,
    CandidateEducationSummary,
    CandidateEmploymentSummary,
    CandidateSummaryResponse,
)
from app.services.doc_verification.pipeline.orchestrator import DocumentVerificationOrchestrator
from app.services.doc_verification.repository import (
    DocumentVerificationRepository,
    submission_extracted_documents,
    submission_issues,
    submission_manual_changes,
    submission_pending_documents,
)
from app.services.doc_verification.google_drive import GoogleDriveImportService
from app.services.doc_verification.storage import DocumentStorageService


logger = logging.getLogger(__name__)
UNKNOWN_CANDIDATE_LABEL = "Analyzing documents"
BACKEND_DIR = Path(__file__).resolve().parents[3]


def resolve_stored_file_path(file_path: str) -> Path:
    path = Path(file_path)
    if path.exists():
        return path

    if not path.is_absolute():
        backend_relative = BACKEND_DIR / path
        if backend_relative.exists():
            return backend_relative

    return path


def _as_text(value: object) -> str | None:
    return str(value) if value is not None and value != "" else None


def _first_value(data: dict, *keys: str) -> str | None:
    for key in keys:
        value = _as_text(data.get(key))
        if value:
            return value
    return None


class DocumentVerificationService:
    """Use cases for HR onboarding document verification."""

    def __init__(
        self,
        repository: DocumentVerificationRepository,
        storage: DocumentStorageService | None = None,
    ):
        self.repository = repository
        self.storage = storage or DocumentStorageService()

    async def submit(
        self,
        candidate_name: str,
        uploads: list[UploadFile],
        current_user: User,
    ) -> int:
        candidate_name = candidate_name.strip() or UNKNOWN_CANDIDATE_LABEL
        logger.info(
            "[DOC_VERIFY] Creating local document submission candidate=%r user_id=%s upload_count=%s",
            candidate_name,
            current_user.id,
            len(uploads),
        )
        submission = await self.repository.create_submission(candidate_name, current_user.id)
        stored_files = await self.storage.save_uploads(submission.id, candidate_name, uploads)
        if not stored_files:
            raise ValueError("No processable documents were found. Upload PDFs, images, or a ZIP containing them.")
        await self.repository.add_files(submission.id, stored_files)
        await self.repository.session.commit()
        logger.info(
            "[DOC_VERIFY] Local document submission saved submission_id=%s stored_files=%s",
            submission.id,
            len(stored_files),
        )
        return submission.id

    async def submit_from_google_drive(
        self,
        candidate_name: str | None,
        drive_url: str,
        current_user: User,
    ) -> int:
        candidate_name = (candidate_name or "").strip() or UNKNOWN_CANDIDATE_LABEL
        logger.info(
            "[DOC_VERIFY] Creating Google Drive document submission candidate=%r user_id=%s",
            candidate_name,
            current_user.id,
        )
        submission = await self.repository.create_submission(candidate_name, current_user.id)
        destination = self.storage.submission_dir(submission.id, candidate_name)
        # Google's Drive client is synchronous; keep it off the FastAPI event loop.
        drive_documents = await asyncio.to_thread(
            GoogleDriveImportService().import_documents,
            drive_url,
            destination,
        )
        await self.repository.add_files(submission.id, drive_documents)
        await self.repository.session.commit()
        logger.info(
            "[DOC_VERIFY] Google Drive document submission saved submission_id=%s stored_files=%s",
            submission.id,
            len(drive_documents),
        )
        return submission.id

    async def list_submissions(self) -> list[DocumentVerificationSubmissionSummary]:
        submissions = await self.repository.list_submissions()
        return [
            DocumentVerificationSubmissionSummary(
                id=submission.id,
                candidate_name=submission.candidate_name,
                status=submission.status,
                created_at=submission.created_at,
                updated_at=submission.updated_at,
                verdict_summary=submission.summary,
                summary=submission.summary,
                issue_count=len(submission_issues(submission)),
            )
            for submission in submissions
        ]

    async def detail(self, submission_id: int) -> DocumentVerificationSubmissionDetail | None:
        submission = await self.repository.get_submission(submission_id)
        if not submission:
            return None
        files = await self.repository.get_files(submission_id)
        return DocumentVerificationSubmissionDetail(
            id=submission.id,
            candidate_name=submission.candidate_name,
            status=submission.status,
            created_at=submission.created_at,
            updated_at=submission.updated_at,
            summary=submission.summary,
            issues=submission_issues(submission),
            pending_documents=submission_pending_documents(submission),
            extracted_documents=submission_extracted_documents(submission),
            manual_changes=submission_manual_changes(submission),
            files=[self._file_response(file) for file in files],
        )

    async def apply_manual_changes(self, submission_id: int, changes: list[dict]) -> bool:
        applied = await self.repository.apply_manual_changes(submission_id, changes)
        if applied:
            await self.repository.session.commit()
        return applied

    async def candidate_summary(self, submission_id: int) -> CandidateSummaryResponse | None:
        submission = await self.repository.get_submission(submission_id)
        if not submission:
            return None

        education = []
        employment = []
        documents = submission_extracted_documents(submission)
        for document in documents:
            data = document.get("extracted_data") or {}
            if not isinstance(data, dict):
                data = {}
            doc_type = document.get("document_type")
            filename = str(document.get("originalName") or doc_type or "Document")
            if doc_type in {"MARKSHEET", "DEGREE_CERTIFICATE"}:
                passed = data.get("passed")
                if passed is None and data.get("has_supplementary_or_backlog_text") is not None:
                    passed = not bool(data.get("has_supplementary_or_backlog_text"))
                education.append(CandidateEducationSummary(
                    qualification=str(data.get("qualification_level") or "Not extracted"),
                    start_date=_first_value(data, "start_date", "course_start_date", "admission_date"),
                    end_date=_first_value(data, "passing_date", "issue_date", "passing_year"),
                    marks_or_grade=_first_value(data, "marks", "percentage", "cgpa", "grade"),
                    result="Passed" if passed is True else "Not passed" if passed is False else "Not stated",
                    source=filename,
                ))
            if doc_type == "UAN_SCREENSHOT":
                for item in data.get("employment_history") or []:
                    if isinstance(item, dict) and item.get("company_name"):
                        employment.append(CandidateEmploymentSummary(
                            employer_name=str(item["company_name"]),
                            start_date=_as_text(item.get("start_date")),
                            end_date=_as_text(item.get("end_date")),
                            source="UAN document",
                        ))

        if not employment:
            for document in documents:
                if document.get("document_type") not in {"OFFER_LETTER_PREVIOUS_ORG", "RELIEVING_LETTER"}:
                    continue
                data = document.get("extracted_data") or {}
                if not isinstance(data, dict):
                    continue
                company = data.get("company_name")
                if company:
                    employment.append(CandidateEmploymentSummary(
                        employer_name=str(company),
                        start_date=_first_value(data, "start_date", "doj"),
                        end_date=_first_value(data, "end_date", "last_working_day"),
                        source=str(document.get("originalName") or document.get("document_type")),
                    ))

        return CandidateSummaryResponse(
            candidate_name=submission.candidate_name,
            education=education,
            employment_history=employment,
        )

    async def file(self, file_id: int) -> DocumentVerificationFile | None:
        return await self.repository.get_file(file_id)

    async def file_by_submission_and_name(
        self,
        submission_id: int,
        filename: str,
    ) -> DocumentVerificationFile | None:
        return await self.repository.get_file_by_submission_and_name(submission_id, filename)

    @staticmethod
    def _file_response(file: DocumentVerificationFile) -> DocumentVerificationFileResponse:
        return DocumentVerificationFileResponse(
            id=file.id,
            filename=file.filename,
            content_type=file.content_type,
            size_bytes=file.size_bytes,
            url=f"/doc-verification/files/{file.id}/download",
        )


async def process_document_verification_submission(submission_id: int) -> None:
    """Background job that runs the HRAI document pipeline for one submission."""

    # Load DB state first, then release the session before the long-running LLM work.
    async with AsyncSessionLocal() as session:
        repository = DocumentVerificationRepository(session)
        submission = await repository.get_submission(submission_id)
        if not submission:
            logger.warning("[DOC_VERIFY] Submission not found for processing submission_id=%s", submission_id)
            return
        files = await repository.get_files(submission_id)
        uploaded_files = [
            {"originalName": file.filename, "storedPath": str(resolved_path)}
            for file in files
            for resolved_path in [resolve_stored_file_path(file.file_path)]
            if resolved_path.exists()
        ]

    try:
        logger.info(
            "[DOC_VERIFY] Starting pipeline submission_id=%s candidate=%r file_count=%s",
            submission_id,
            submission.candidate_name,
            len(uploaded_files),
        )
        orchestrator = DocumentVerificationOrchestrator(
            candidate_profile={"name": submission.candidate_name}
        )
        result = await orchestrator.run(uploaded_files)
        async with AsyncSessionLocal() as session:
            repository = DocumentVerificationRepository(session)
            await repository.mark_completed(submission_id, result)
            await session.commit()
        logger.info(
            "[DOC_VERIFY] Pipeline completed submission_id=%s status=%s issues=%s",
            submission_id,
            result.get("status"),
            len(result.get("action_items", [])),
        )
    except Exception as exc:
        logger.exception("Document verification pipeline failed submission_id=%s", submission_id)
        async with AsyncSessionLocal() as session:
            repository = DocumentVerificationRepository(session)
            await repository.mark_failed(submission_id, str(exc))
            await session.commit()
