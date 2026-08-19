import json
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DocumentVerificationFile, DocumentVerificationSubmission
from app.services.doc_verification.storage import StoredDocument


def _json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return loaded if isinstance(loaded, list) else []


def _public_extractions(documents: list[dict]) -> list[dict]:
    """Strip server-only fields before storing data shown through the API."""

    public_documents = []
    for document in documents:
        if not isinstance(document, dict):
            continue
        public_document = dict(document)
        public_document.pop("storedPath", None)
        public_documents.append(public_document)
    return public_documents


def _first_extracted_candidate_name(documents: list[dict]) -> str | None:
    pan_name = None
    aadhaar_name = None

    for document in documents:
        if not isinstance(document, dict):
            continue
        extracted = document.get("extracted_data") or {}
        if not isinstance(extracted, dict):
            continue
        doc_type = document.get("document_type")
        if doc_type == "PAN_CARD" and extracted.get("name"):
            pan_name = str(extracted["name"]).strip()
        elif doc_type == "AADHAAR_CARD" and extracted.get("name"):
            aadhaar_name = str(extracted["name"]).strip()

    if aadhaar_name and pan_name:
        return aadhaar_name

    for document in documents:
        if not isinstance(document, dict):
            continue
        extracted = document.get("extracted_data") or {}
        if not isinstance(extracted, dict):
            continue
        for field_name in ("candidate_name", "name"):
            value = extracted.get(field_name)
            if value and str(value).strip():
                return str(value).strip()
    return None


class DocumentVerificationRepository:
    """Database access for document verification submissions and files."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_submission(self, candidate_name: str, user_id: int | None) -> DocumentVerificationSubmission:
        submission = DocumentVerificationSubmission(
            candidate_name=candidate_name,
            submitted_by_user_id=user_id,
            status="PROCESSING",
            issues_json="[]",
            pending_documents_json="[]",
            extracted_documents_json="[]",
        )
        self.session.add(submission)
        await self.session.flush()
        return submission

    async def add_files(
        self,
        submission_id: int,
        files: list[StoredDocument],
    ) -> list[DocumentVerificationFile]:
        rows = [
            DocumentVerificationFile(
                submission_id=submission_id,
                filename=file.original_name,
                stored_filename=file.stored_name,
                content_type=file.content_type,
                file_path=file.file_path,
                size_bytes=file.size_bytes,
            )
            for file in files
        ]
        self.session.add_all(rows)
        await self.session.flush()
        return rows

    async def list_submissions(self) -> list[DocumentVerificationSubmission]:
        result = await self.session.execute(
            select(DocumentVerificationSubmission).order_by(DocumentVerificationSubmission.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_submission(self, submission_id: int) -> DocumentVerificationSubmission | None:
        return await self.session.get(DocumentVerificationSubmission, submission_id)

    async def get_files(self, submission_id: int) -> list[DocumentVerificationFile]:
        result = await self.session.execute(
            select(DocumentVerificationFile)
            .where(DocumentVerificationFile.submission_id == submission_id)
            .order_by(DocumentVerificationFile.id.asc())
        )
        return list(result.scalars().all())

    async def get_file(self, file_id: int) -> DocumentVerificationFile | None:
        return await self.session.get(DocumentVerificationFile, file_id)

    async def get_file_by_submission_and_name(
        self,
        submission_id: int,
        filename: str,
    ) -> DocumentVerificationFile | None:
        result = await self.session.execute(
            select(DocumentVerificationFile).where(
                DocumentVerificationFile.submission_id == submission_id,
                DocumentVerificationFile.filename == filename,
            )
        )
        return result.scalars().first()

    async def mark_completed(self, submission_id: int, result: dict, expected_revision: int | None = None) -> bool:
        """Persist the pipeline result without leaking local file paths."""

        pipeline_status = result.get("status")
        final_status = "VERIFIED" if pipeline_status == "VERIFIED" else "NEEDS_HUMAN_REVIEW"
        rule_report = result.get("detailed_reports", {}).get("step3_rule_engine", {})
        extracted_documents = result.get("document_extractions", [])
        candidate_name = _first_extracted_candidate_name(extracted_documents)
        values = {
            "status": final_status,
            "pipeline_status_raw": pipeline_status,
            "summary": result.get("summary"),
            "issues_json": json.dumps(result.get("action_items", [])),
            "pending_documents_json": json.dumps(rule_report.get("pending_documents", [])),
            "extracted_documents_json": json.dumps(_public_extractions(extracted_documents)),
            "processing_error": None,
            "updated_at": datetime.utcnow(),
        }
        if candidate_name:
            values["candidate_name"] = candidate_name
        query = update(DocumentVerificationSubmission).where(DocumentVerificationSubmission.id == submission_id)
        if expected_revision is not None:
            query = query.where(DocumentVerificationSubmission.revision == expected_revision)
        update_result = await self.session.execute(query.values(**values))
        return update_result.rowcount == 1

    async def apply_manual_changes(self, submission_id: int, changes: list[dict], expected_revision: int) -> bool:
        """Persist HR-reviewed extraction values and their explicit field state."""

        submission = await self.get_submission(submission_id)
        if not submission:
            return False
        if submission.revision != expected_revision or submission.status == "PROCESSING":
            raise RuntimeError("This submission was updated by another user or is being analysed. Refresh and try again.")

        documents = submission_extracted_documents(submission)
        for change in changes:
            filename = change["filename"]
            field = change["field"]
            document = next((item for item in documents if item.get("originalName") == filename), None)
            if not document:
                raise ValueError(f"Document '{filename}' was not found in this submission.")
            extracted_data = document.get("extracted_data")
            if not isinstance(extracted_data, dict):
                extracted_data = {}
                document["extracted_data"] = extracted_data
            field_statuses = document.get("field_statuses")
            if not isinstance(field_statuses, dict):
                field_statuses = {}
                document["field_statuses"] = field_statuses
            previous_value = extracted_data.get(field)
            new_value = change.get("value")
            new_status = change["status"]
            extracted_data[field] = new_value
            field_statuses[field] = {
                "status": new_status,
                "label": "Matched" if new_status == "match" else "Mismatch",
                "manual": True,
            }
            manual_changes = document.get("manual_changes")
            if not isinstance(manual_changes, list):
                manual_changes = []
                document["manual_changes"] = manual_changes
            manual_changes.append({
                "filename": filename,
                "field": field,
                "from": previous_value,
                "to": new_value,
                "status": new_status,
            })

        result = await self.session.execute(
            update(DocumentVerificationSubmission)
            .where(
                DocumentVerificationSubmission.id == submission_id,
                DocumentVerificationSubmission.revision == expected_revision,
                DocumentVerificationSubmission.status != "PROCESSING",
            )
            .values(
                extracted_documents_json=json.dumps(_public_extractions(documents)),
                revision=DocumentVerificationSubmission.revision + 1,
                updated_at=datetime.utcnow(),
            )
        )
        if result.rowcount != 1:
            raise RuntimeError("This submission was updated by another user. Refresh and try again.")
        return True

    async def reset_for_reanalysis(
        self,
        submission_id: int,
        expected_revision: int,
        replacement: StoredDocument,
    ) -> tuple[str, list[str], int]:
        """Atomically add or replace a file and reserve this submission for processing."""

        submission = await self.get_submission(submission_id)
        if not submission:
            raise LookupError("Submission not found.")

        files = await self.get_files(submission_id)
        matching_files = [
            file for file in files
            if file.filename.casefold() == replacement.original_name.casefold()
        ]
        action = "replace" if matching_files else "add"
        result = await self.session.execute(
            update(DocumentVerificationSubmission)
            .where(
                DocumentVerificationSubmission.id == submission_id,
                DocumentVerificationSubmission.revision == expected_revision,
                DocumentVerificationSubmission.status != "PROCESSING",
            )
            .values(
                status="PROCESSING",
                pipeline_status_raw="REANALYSIS_QUEUED",
                summary="Document reanalysis is in progress.",
                issues_json="[]",
                pending_documents_json="[]",
                extracted_documents_json="[]",
                processing_error=None,
                revision=DocumentVerificationSubmission.revision + 1,
                updated_at=datetime.utcnow(),
            )
        )
        if result.rowcount != 1:
            raise RuntimeError("This submission was updated by another user or is already being analysed. Refresh and try again.")

        obsolete_paths = [file.file_path for file in matching_files]
        if matching_files:
            await self.session.execute(
                delete(DocumentVerificationFile).where(
                    DocumentVerificationFile.id.in_([file.id for file in matching_files])
                )
            )

        self.session.add(DocumentVerificationFile(
            submission_id=submission_id,
            filename=replacement.original_name,
            stored_filename=replacement.stored_name,
            content_type=replacement.content_type,
            file_path=replacement.file_path,
            size_bytes=replacement.size_bytes,
        ))
        await self.session.flush()
        return action, obsolete_paths, expected_revision + 1

    async def mark_failed(self, submission_id: int, error: str, expected_revision: int | None = None) -> bool:
        query = update(DocumentVerificationSubmission).where(DocumentVerificationSubmission.id == submission_id)
        if expected_revision is not None:
            query = query.where(DocumentVerificationSubmission.revision == expected_revision)
        update_result = await self.session.execute(
            query.values(
                status="NEEDS_HUMAN_REVIEW",
                pipeline_status_raw="SYSTEM_ERROR",
                summary="Pipeline crashed before producing a verdict.",
                issues_json=json.dumps([f"[System Error] {error}"]),
                processing_error=error,
                updated_at=datetime.utcnow(),
            )
        )
        return update_result.rowcount == 1


def submission_issues(submission: DocumentVerificationSubmission) -> list[str]:
    return [str(item) for item in _json_list(submission.issues_json)]


def submission_pending_documents(submission: DocumentVerificationSubmission) -> list[str]:
    return [str(item) for item in _json_list(submission.pending_documents_json)]


def submission_extracted_documents(submission: DocumentVerificationSubmission) -> list[dict]:
    return [item for item in _json_list(submission.extracted_documents_json) if isinstance(item, dict)]


def submission_manual_changes(submission: DocumentVerificationSubmission) -> list[dict]:
    changes = []
    for document in submission_extracted_documents(submission):
        document_changes = document.get("manual_changes", [])
        if isinstance(document_changes, list):
            changes.extend(item for item in document_changes if isinstance(item, dict))
    return changes
