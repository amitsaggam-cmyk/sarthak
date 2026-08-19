import asyncio
import logging
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings


logger = logging.getLogger(__name__)
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".zip"}
PROCESSABLE_EXTENSIONS = ALLOWED_EXTENSIONS - {".zip"}


@dataclass(frozen=True)
class StoredDocument:
    original_name: str
    stored_name: str
    content_type: str | None
    file_path: str
    size_bytes: int


def sanitize_path_part(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value.strip())
    safe = safe.strip("._")
    return safe or "file"


class DocumentStorageService:
    """Owns filesystem writes and extraction for uploaded verification documents."""

    def __init__(self, upload_root: str | None = None):
        settings = get_settings()
        self.upload_root = Path(upload_root or settings.doc_verification_upload_dir)
        self.max_files = settings.doc_verification_max_files
        self.max_file_size = settings.doc_verification_max_file_size_mb * 1024 * 1024

    def submission_dir(self, submission_id: int, candidate_name: str) -> Path:
        folder_name = f"{submission_id}_{sanitize_path_part(candidate_name)[:80]}"
        return self.upload_root / folder_name

    async def save_uploads(
        self,
        submission_id: int,
        candidate_name: str,
        uploads: list[UploadFile],
    ) -> list[StoredDocument]:
        if not uploads:
            raise ValueError("At least one file is required.")

        target_dir = self.submission_dir(submission_id, candidate_name)
        await asyncio.to_thread(target_dir.mkdir, parents=True, exist_ok=True)
        logger.info(
            "[DOC_VERIFY] Saving uploaded documents submission_id=%s candidate=%r uploads=%s",
            submission_id,
            candidate_name,
            len(uploads),
        )

        stored: list[StoredDocument] = []
        for upload in uploads:
            filename = Path(upload.filename or "document").name
            extension = Path(filename).suffix.lower()
            if extension not in ALLOWED_EXTENSIONS:
                raise ValueError(f"Unsupported file type: {filename}")

            temp_path = target_dir / f"{uuid4().hex}_{sanitize_path_part(filename)}"
            size = await self._write_upload(upload, temp_path)
            if size > self.max_file_size:
                temp_path.unlink(missing_ok=True)
                raise ValueError(f"{filename} exceeds the {self.max_file_size // (1024 * 1024)} MB file limit.")

            if extension == ".zip":
                # ZIPs are treated as transport containers; only inner PDFs/images are processed.
                extracted = await asyncio.to_thread(self._extract_zip, temp_path, target_dir)
                stored.extend(extracted)
                logger.info(
                    "[DOC_VERIFY] Extracted zip submission_id=%s filename=%r extracted=%s",
                    submission_id,
                    filename,
                    len(extracted),
                )
                temp_path.unlink(missing_ok=True)
            else:
                stored.append(
                    StoredDocument(
                        original_name=filename,
                        stored_name=temp_path.name,
                        content_type=upload.content_type,
                        file_path=str(temp_path),
                        size_bytes=size,
                    )
                )
                logger.info(
                    "[DOC_VERIFY] Stored document submission_id=%s filename=%r bytes=%s",
                    submission_id,
                    filename,
                    size,
                )

            if len(stored) > self.max_files:
                raise ValueError(f"You can upload at most {self.max_files} processable documents.")

        return stored

    async def _write_upload(self, upload: UploadFile, destination: Path) -> int:
        size = 0
        with destination.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > self.max_file_size:
                    break
                output.write(chunk)
        return size

    def _extract_zip(self, zip_path: Path, target_dir: Path) -> list[StoredDocument]:
        stored: list[StoredDocument] = []
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                source_name = Path(member.filename).name
                if not source_name:
                    continue
                extension = Path(source_name).suffix.lower()
                if extension not in PROCESSABLE_EXTENSIONS:
                    continue
                if member.file_size > self.max_file_size:
                    raise ValueError(f"{source_name} exceeds the {self.max_file_size // (1024 * 1024)} MB file limit.")

                destination = target_dir / f"{uuid4().hex}_{sanitize_path_part(source_name)}"
                with archive.open(member) as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output)
                stored.append(
                    StoredDocument(
                        original_name=source_name,
                        stored_name=destination.name,
                        content_type=self._content_type_for_extension(extension),
                        file_path=str(destination),
                        size_bytes=member.file_size,
                    )
                )
        return stored

    @staticmethod
    def _content_type_for_extension(extension: str) -> str:
        if extension == ".pdf":
            return "application/pdf"
        if extension in {".jpg", ".jpeg"}:
            return "image/jpeg"
        if extension == ".png":
            return "image/png"
        if extension == ".webp":
            return "image/webp"
        if extension in {".tif", ".tiff"}:
            return "image/tiff"
        return "application/octet-stream"
