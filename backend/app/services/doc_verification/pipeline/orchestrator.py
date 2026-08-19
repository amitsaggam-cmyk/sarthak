import asyncio
import logging
from typing import Any

from app.core.config import get_settings
from app.services.doc_verification.pipeline.document_loader import DocumentLoader
from app.services.doc_verification.pipeline.stage1_classification import classify_document
from app.services.doc_verification.pipeline.stage2_page_selection import select_target_pages
from app.services.doc_verification.pipeline.stage3_extraction import process_document
from app.services.doc_verification.pipeline.stage4_rule_engine import evaluate_dossier
from app.services.doc_verification.pipeline.stage5_decision_engine import generate_final_verdict


logger = logging.getLogger(__name__)
_vision_semaphore: asyncio.Semaphore | None = None


def _get_vision_semaphore() -> asyncio.Semaphore:
    global _vision_semaphore
    if _vision_semaphore is None:
        _vision_semaphore = asyncio.Semaphore(get_settings().doc_verification_pipeline_concurrency)
    return _vision_semaphore


class DocumentVerificationOrchestrator:
    """Coordinates the candidate document verification pipeline."""

    def __init__(self, candidate_profile: dict[str, Any] | None = None):
        self.candidate_profile = candidate_profile or {}

    async def run(self, uploaded_files: list[dict[str, str]]) -> dict[str, Any]:
        logger.info("[DOC_VERIFY] Orchestrator started file_count=%s", len(uploaded_files))
        dossier: dict[str, Any] = {}
        processing_errors: list[str] = []
        completed_documents = await asyncio.gather(
            *[self._process_single_file(file_info, processing_errors) for file_info in uploaded_files]
        )

        for document in completed_documents:
            if not document:
                continue
            doc_type = document.get("document_type", "UNKNOWN")
            if doc_type == "UNKNOWN":
                dossier.setdefault("UNKNOWN", []).append(document)
            elif doc_type in dossier:
                if not isinstance(dossier[doc_type], list):
                    dossier[doc_type] = [dossier[doc_type]]
                dossier[doc_type].append(document)
            else:
                dossier[doc_type] = document

        rule_engine_result = evaluate_dossier(dossier, self.candidate_profile)
        final_verdict = generate_final_verdict(rule_engine_result, processing_errors)
        logger.info(
            "[DOC_VERIFY] Orchestrator finished status=%s processed=%s unclassified=%s errors=%s",
            final_verdict.get("status"),
            len(uploaded_files),
            len(dossier.get("UNKNOWN", [])),
            len(processing_errors),
        )

        return {
            "status": final_verdict.get("status"),
            "action_items": final_verdict.get("action_items", []),
            "hr_context_notes": final_verdict.get("hr_context_notes", []),
            "summary": final_verdict.get("summary"),
            "pipeline_metrics": {
                "total_documents_processed": len(uploaded_files),
                "unclassified_documents": len(dossier.get("UNKNOWN", [])),
            },
            "detailed_reports": {
                "step3_rule_engine": rule_engine_result,
                "processing_errors": processing_errors,
            },
            "document_extractions": [doc for doc in completed_documents if doc],
        }

    async def _process_single_file(
        self,
        file_info: dict[str, str],
        processing_errors: list[str],
    ) -> dict[str, Any] | None:
        filename = file_info.get("originalName") or "document"
        path = file_info.get("storedPath") or ""

        try:
            async with _get_vision_semaphore():
                logger.info("[DOC_VERIFY] Processing document filename=%r", filename)
                # Opening PDFs/images can touch disk heavily, so do it in a worker thread.
                loader = await asyncio.to_thread(DocumentLoader, path)
                try:
                    page1_bytes = await asyncio.to_thread(loader.render_page, 0)
                    classification = await classify_document(page1_bytes, filename)
                    doc_type = classification["document_type"]
                    logger.info(
                        "[DOC_VERIFY] Classified document filename=%r doc_type=%s confidence=%s",
                        filename,
                        doc_type,
                        classification.get("confidence_score"),
                    )

                    if doc_type == "UNKNOWN":
                        return {
                            "document_type": "UNKNOWN",
                            "confidence_score": classification["confidence_score"],
                            "extracted_data": {},
                            "originalName": filename,
                            "storedPath": path,
                            "warning": "Could not classify this document from its first page.",
                        }

                    target_pages = select_target_pages(loader.page_count, doc_type)
                    page_images = []
                    for page_num in target_pages:
                        if page_num == 1:
                            page_images.append(page1_bytes)
                        else:
                            page_images.append(await asyncio.to_thread(loader.render_page, page_num - 1))

                    extracted_doc = await process_document(page_images, doc_type, filename)
                    logger.info(
                        "[DOC_VERIFY] Extracted document filename=%r doc_type=%s pages=%s has_error=%s",
                        filename,
                        doc_type,
                        target_pages,
                        bool(extracted_doc.get("error")),
                    )
                    extracted_doc["confidence_score"] = classification["confidence_score"]
                    extracted_doc["storedPath"] = path
                    extracted_doc["originalName"] = filename
                    extracted_doc["pagesRead"] = target_pages
                    return extracted_doc
                finally:
                    await asyncio.to_thread(loader.close)
        except Exception as exc:
            logger.exception("Document processing failed filename=%s", filename)
            processing_errors.append(f"Failed processing {filename}: {exc}")
            return None
