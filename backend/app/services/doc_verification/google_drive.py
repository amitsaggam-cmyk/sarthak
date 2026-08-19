import json
import logging
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import get_settings
from app.services.doc_verification.storage import (
    PROCESSABLE_EXTENSIONS,
    StoredDocument,
    sanitize_path_part,
)


logger = logging.getLogger(__name__)
DRIVE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
GOOGLE_DOC_EXPORT_MIME_TYPES = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.drawing": ("application/pdf", ".pdf"),
}
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


class GoogleDriveImportService:
    """Downloads supported documents from a Google Drive file or folder link."""

    def __init__(self):
        settings = get_settings()
        self.service_account_file = settings.google_drive_service_account_file
        self.service_account_json = settings.google_drive_service_account_json
        self.max_files = settings.doc_verification_max_files
        self.max_file_size = settings.doc_verification_max_file_size_mb * 1024 * 1024

    def import_documents(
        self,
        drive_url: str,
        destination_dir: Path,
    ) -> list[StoredDocument]:
        drive_id = parse_drive_id(drive_url)
        if not drive_id:
            raise ValueError("Enter a valid Google Drive file or folder link.")

        destination_dir.mkdir(parents=True, exist_ok=True)
        service = self._build_service()
        logger.info("[DOC_VERIFY] Importing Google Drive documents drive_id=%s", drive_id)
        metadata = service.files().get(
            fileId=drive_id,
            fields="id,name,mimeType,size",
            supportsAllDrives=True,
        ).execute()

        # A Drive link can point to one file or a folder tree; normalize both to files.
        files = self._list_folder_files(service, drive_id) if metadata["mimeType"] == DRIVE_FOLDER_MIME_TYPE else [metadata]
        logger.info(
            "[DOC_VERIFY] Google Drive source resolved drive_id=%s mime_type=%s file_count=%s",
            drive_id,
            metadata["mimeType"],
            len(files),
        )
        stored: list[StoredDocument] = []
        for item in files:
            document = self._download_file(service, item, destination_dir)
            if document:
                stored.append(document)
            if len(stored) > self.max_files:
                raise ValueError(f"Google Drive import is limited to {self.max_files} processable documents.")

        if not stored:
            raise ValueError("No supported PDF or image documents were found in that Google Drive link.")
        logger.info("[DOC_VERIFY] Google Drive import completed drive_id=%s stored=%s", drive_id, len(stored))
        return stored

    def _build_service(self):
        credentials = self._load_credentials()
        from googleapiclient.discovery import build

        return build("drive", "v3", credentials=credentials, cache_discovery=False)

    def _load_credentials(self):
        if not self.service_account_file and not self.service_account_json:
            raise ValueError(
                "Google Drive credentials are not configured. Set GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE "
                "or GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON in backend/.env."
            )

        from google.oauth2 import service_account

        if self.service_account_file:
            return service_account.Credentials.from_service_account_file(
                self.service_account_file,
                scopes=DRIVE_SCOPES,
            )

        info = json.loads(self.service_account_json)
        return service_account.Credentials.from_service_account_info(info, scopes=DRIVE_SCOPES)

    def _list_folder_files(self, service, folder_id: str) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        page_token = None
        while True:
            response = service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken, files(id,name,mimeType,size)",
                pageSize=100,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            for item in response.get("files", []):
                if item["mimeType"] == DRIVE_FOLDER_MIME_TYPE:
                    files.extend(self._list_folder_files(service, item["id"]))
                else:
                    files.append(item)
            page_token = response.get("nextPageToken")
            if not page_token:
                return files

    def _download_file(self, service, metadata: dict[str, Any], destination_dir: Path) -> StoredDocument | None:
        filename = metadata.get("name") or "document"
        mime_type = metadata.get("mimeType")
        extension = Path(filename).suffix.lower()

        if mime_type in GOOGLE_DOC_EXPORT_MIME_TYPES:
            # Native Google files do not have bytes to download directly, so export them as PDFs.
            export_mime_type, export_extension = GOOGLE_DOC_EXPORT_MIME_TYPES[mime_type]
            if not extension:
                filename = f"{filename}{export_extension}"
            request = service.files().export_media(fileId=metadata["id"], mimeType=export_mime_type)
            content_type = export_mime_type
        else:
            if extension not in PROCESSABLE_EXTENSIONS:
                logger.info(
                    "[DOC_VERIFY] Skipping unsupported Google Drive file file_id=%s filename=%r mime_type=%s",
                    metadata.get("id"),
                    filename,
                    mime_type,
                )
                return None
            request = service.files().get_media(fileId=metadata["id"], supportsAllDrives=True)
            content_type = mime_type

        stored_name = f"{uuid4().hex}_{sanitize_path_part(filename)}"
        destination = destination_dir / stored_name
        size = self._download_request(request, destination)
        if size > self.max_file_size:
            destination.unlink(missing_ok=True)
            raise ValueError(f"{filename} exceeds the {self.max_file_size // (1024 * 1024)} MB file limit.")

        logger.info(
            "[DOC_VERIFY] Downloaded Google Drive file file_id=%s filename=%r bytes=%s",
            metadata.get("id"),
            filename,
            size,
        )
        return StoredDocument(
            original_name=filename,
            stored_name=stored_name,
            content_type=content_type,
            file_path=str(destination),
            size_bytes=size,
        )

    @staticmethod
    def _download_request(request, destination: Path) -> int:
        from googleapiclient.http import MediaIoBaseDownload

        with destination.open("wb") as file_handle:
            downloader = MediaIoBaseDownload(file_handle, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        return destination.stat().st_size


def parse_drive_id(value: str) -> str | None:
    patterns = [
        r"/folders/([A-Za-z0-9_-]+)",
        r"/file/d/([A-Za-z0-9_-]+)",
        r"[?&]id=([A-Za-z0-9_-]+)",
        r"^([A-Za-z0-9_-]{20,})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            return match.group(1)
    return None
