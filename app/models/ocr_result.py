#ocr result format

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OCRResult:
    text: str = ""
    confidence: float | None = None
    bounding_box: list | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentOCRResult:
    source_path: str
    results: list[OCRResult] = field(default_factory=list)
    full_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)