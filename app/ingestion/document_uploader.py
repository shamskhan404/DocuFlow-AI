"""Local document intake for PDF, JPG and PNG files.

Stage 1 responsibilities:
- validate the supplied file and its actual content type;
- enforce a configurable upload-size limit;
- calculate SHA-256 for duplicate detection;
- copy the original file into the configured input directory;
- register the uploaded document in the existing SQLite database.

This module deliberately does not convert PDFs, preprocess images, run OCR,
or classify documents. Those are later pipeline stages.
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, UnidentifiedImageError

from app.exporters.database_exporter import DatabaseExporter


@dataclass(frozen=True)
class UploadResult:
    document_id: int
    original_filename: str
    stored_path: str
    file_hash: str
    status: str
    duplicate: bool


class DocumentUploader:
    """Validate, store and register local document uploads."""

    ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
    DEFAULT_MAX_FILE_SIZE_MB = 25
    HASH_CHUNK_SIZE = 1024 * 1024

    def __init__(
        self,
        input_dir: str | Path = "input",
        database: DatabaseExporter | None = None,
        max_file_size_mb: int = DEFAULT_MAX_FILE_SIZE_MB,
    ) -> None:
        if max_file_size_mb <= 0:
            raise ValueError("max_file_size_mb must be greater than zero.")

        self.input_dir = Path(input_dir)
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.database = database or DatabaseExporter()
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

    def calculate_hash(self, file_path: str | Path) -> str:
        digest = hashlib.sha256()
        with Path(file_path).open("rb") as file:
            for chunk in iter(
                lambda: file.read(self.HASH_CHUNK_SIZE), b""
            ):
                digest.update(chunk)
        return digest.hexdigest()

    def _validate_file(self, source: Path) -> None:
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"Upload file does not exist: {source}")

        suffix = source.suffix.lower()
        if suffix not in self.ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(self.ALLOWED_EXTENSIONS))
            raise ValueError(
                f"Unsupported file extension '{suffix}'. Allowed: {allowed}."
            )

        file_size = source.stat().st_size
        if file_size == 0:
            raise ValueError("Empty files cannot be uploaded.")
        if file_size > self.max_file_size_bytes:
            limit_mb = self.max_file_size_bytes // (1024 * 1024)
            raise ValueError(
                f"File exceeds the {limit_mb} MB upload limit."
            )

        # Check the file signature/content instead of trusting its extension.
        if suffix == ".pdf":
            with source.open("rb") as file:
                header = file.read(1024)
            if b"%PDF-" not in header:
                raise ValueError(
                    "The file has a PDF extension but is not a valid PDF file."
                )
            return

        try:
            with Image.open(source) as image:
                actual_format = (image.format or "").upper()
                expected_formats = {
                    ".jpg": {"JPEG"},
                    ".jpeg": {"JPEG"},
                    ".png": {"PNG"},
                }
                if actual_format not in expected_formats[suffix]:
                    raise ValueError(
                        f"File content does not match its '{suffix}' extension."
                    )
                image.verify()
        except (UnidentifiedImageError, OSError) as error:
            raise ValueError("The uploaded image is invalid or corrupted.") from error

    def _find_existing_by_hash(self, file_hash: str):
        with self.database.connect() as db:
            return db.execute(
                """
                SELECT document_id, stored_path
                FROM document_files
                WHERE file_hash = ?
                LIMIT 1
                """,
                (file_hash,),
            ).fetchone()

    def _destination_path(self, source: Path, file_hash: str) -> Path:
        # A file already inside the intake directory is already in its final
        # storage location; do not try to copy a file onto itself.
        input_root = self.input_dir.resolve()
        if source.resolve().parent == input_root:
            return source.resolve()

        # Keep the original filename where possible. If occupied, add a hash
        # suffix and then a numeric suffix rather than overwriting anything.
        candidates = [
            self.input_dir / source.name,
            self.input_dir / f"{source.stem}_{file_hash[:8]}{source.suffix.lower()}",
        ]
        candidates.extend(
            self.input_dir / (
                f"{source.stem}_{file_hash[:8]}_{number}{source.suffix.lower()}"
            )
            for number in range(1, 1000)
        )

        for candidate in candidates:
            if not candidate.exists():
                return candidate
            if self.calculate_hash(candidate) == file_hash:
                return candidate

        raise RuntimeError("Unable to allocate a unique upload filename.")

    def upload(self, file_path: str | Path) -> UploadResult:
        """Upload one local file and register it in SQLite."""
        source = Path(file_path).expanduser().resolve()
        self._validate_file(source)
        file_hash = self.calculate_hash(source)

        existing = self._find_existing_by_hash(file_hash)
        if existing:
            document_id, stored_path = existing
            return UploadResult(
                document_id=document_id,
                original_filename=source.name,
                stored_path=stored_path,
                file_hash=file_hash,
                status="duplicate",
                duplicate=True,
            )

        destination = self._destination_path(source, file_hash)
        if source.resolve() != destination.resolve():
            if not destination.exists():
                shutil.copy2(source, destination)

        try:
            document_id = self.database.register_document(
                source_path=destination,
                file_hash=file_hash,
                document_type="unknown",
                processing_status="uploaded",
            )
        except Exception:
            # Do not leave an unregistered copy behind if database insertion fails.
            destination.unlink(missing_ok=True)
            raise

        return UploadResult(
            document_id=document_id,
            original_filename=source.name,
            stored_path=str(destination.resolve()),
            file_hash=file_hash,
            status="uploaded",
            duplicate=False,
        )

    def upload_many(
        self, file_paths: Iterable[str | Path]
    ) -> list[UploadResult | Exception]:
        """Upload multiple files; return an exception for each failed file."""
        results: list[UploadResult | Exception] = []
        for file_path in file_paths:
            try:
                results.append(self.upload(file_path))
            except Exception as error:
                results.append(error)
        return results
