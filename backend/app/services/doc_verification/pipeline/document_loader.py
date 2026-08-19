import io
from pathlib import Path


RASTER_DPI = 200
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}


class DocumentLoader:
    """Lazily render PDFs or images into PNG page bytes."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.extension = Path(file_path).suffix.lower()
        self._pdf_doc = None

        if self.extension == ".pdf":
            import fitz

            self._pdf_doc = fitz.open(file_path)
            self.page_count = len(self._pdf_doc)
        elif self.extension in IMAGE_EXTENSIONS:
            self.page_count = 1
        else:
            raise ValueError(f"Unsupported file type: {self.extension}")

    def render_page(self, page_index: int) -> bytes:
        if self._pdf_doc is not None:
            pixmap = self._pdf_doc.load_page(page_index).get_pixmap(dpi=RASTER_DPI)
            return pixmap.tobytes("png")

        if page_index != 0:
            raise IndexError("Image files only have one page.")

        from PIL import Image

        with Image.open(self.file_path) as image:
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, format="PNG")
            return buffer.getvalue()

    def close(self) -> None:
        if self._pdf_doc is not None:
            self._pdf_doc.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
