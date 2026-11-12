"""Document preprocessing for image and PDF inputs.

Keeps the original image-processing flow and adds multi-page PDF rendering.
"""
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from PIL import Image

from app.processing.image_loader import load_image
from app.processing.image_validator import validate_image
from app.processing.image_preprocessor import preprocess_image


@dataclass
class PreparedDocument:
    source_path: str
    image: Image.Image
    original_width: int
    original_height: int
    width: int
    height: int
    format: str
    page_number: int = 1


class DocumentProcessor:
    SUPPORTED_IMAGE_FORMATS = {
        ".png", ".jpg", ".jpeg", ".bmp",
        ".tiff", ".tif", ".webp"
    }
    PDF_DPI = 200

    def _prepare_image(self, image: Image.Image, source_path: Path,
                       page_number: int = 1) -> PreparedDocument:
        validate_image(image)
        original_width, original_height = image.size
        processed = preprocess_image(image)
        return PreparedDocument(
            source_path=str(source_path.resolve()),
            image=processed,
            original_width=original_width,
            original_height=original_height,
            width=processed.width,
            height=processed.height,
            format=processed.mode,
            page_number=page_number,
        )

    def process(self, image_path: str) -> PreparedDocument:
        """Preserve the original single-image processing API."""
        path = Path(image_path)
        image = load_image(str(path))
        return self._prepare_image(image, path)

    def process_pages(self, document_path: str) -> list[PreparedDocument]:
        """Prepare an image as one page or render every page of a PDF."""
        path = Path(document_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Document not found: {path}")

        suffix = path.suffix.lower()
        if suffix in self.SUPPORTED_IMAGE_FORMATS:
            return [self.process(str(path))]

        if suffix != ".pdf":
            raise ValueError(f"Unsupported document format: {suffix}")

        prepared_pages = []
        with pymupdf.open(str(path)) as pdf:
            if pdf.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported.")
            if len(pdf) == 0:
                raise ValueError("PDF contains no pages.")

            scale = self.PDF_DPI / 72
            matrix = pymupdf.Matrix(scale, scale)

            for page_index, page in enumerate(pdf):
                pixmap = page.get_pixmap(
                    matrix=matrix,
                    colorspace=pymupdf.csRGB,
                    alpha=False,
                )
                image = Image.frombytes(
                    "RGB",
                    (pixmap.width, pixmap.height),
                    pixmap.samples,
                )
                prepared_pages.append(
                    self._prepare_image(
                        image,
                        path,
                        page_number=page_index + 1,
                    )
                )

        return prepared_pages
