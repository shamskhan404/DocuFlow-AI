"""PaddleOCR-VL 1.6 adapter for the DocuFlow OCR interface."""

import json
from pathlib import Path
from typing import Any

from app.models.base import BaseOCRModel
from app.models.ocr_result import OCRResult, DocumentOCRResult


class PaddleOCRModel(BaseOCRModel):
    """Runs the complete PaddleOCR-VL document-parsing pipeline.

    PaddleOCR-VL performs layout detection and vision-language recognition.
    Its block-level results are adapted to DocuFlow's existing OCRResult
    interface so the database exporter and invoice extractor remain usable.
    """

    MODEL_ID = "PaddleOCR-VL-1.6"

    def __init__(self, settings_path="config/settings.json"):
        self.model = None
        self.settings_path = Path(settings_path)
        self.settings = self._load_settings()

    def _load_settings(self) -> dict[str, Any]:
        if not self.settings_path.exists():
            return {}
        with self.settings_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def _to_python(value):
        """Convert NumPy-like values to ordinary Python values."""
        if hasattr(value, "tolist"):
            return value.tolist()
        return value

    @staticmethod
    def _box_to_polygon(box):
        """Convert PaddleOCR-VL xyxy boxes or polygons to 4-point polygons."""
        if box is None:
            return None

        box = PaddleOCRModel._to_python(box)
        if not isinstance(box, (list, tuple)):
            return None

        # Axis-aligned rectangle: [x_min, y_min, x_max, y_max].
        if len(box) == 4 and all(isinstance(v, (int, float)) for v in box):
            x1, y1, x2, y2 = [float(v) for v in box]
            return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]

        # Already a polygon/quadrilateral: [[x, y], ...].
        try:
            return [[float(point[0]), float(point[1])] for point in box]
        except (TypeError, ValueError, IndexError):
            return None

    def load(self):
        if self.model is not None:
            return

        try:
            from paddleocr import PaddleOCRVL
        except ImportError as error:
            raise ImportError(
                "PaddleOCR-VL dependencies are missing. Install the "
                "Stage 3 requirements using the instructions in README.md."
            ) from error

        version = self.settings.get("pipeline_version", "v1.6")
        device = self.settings.get("device", "cpu")

        if version != "v1.6":
            raise ValueError(
                f"Expected PaddleOCR-VL pipeline_version='v1.6', got {version!r}"
            )

        kwargs = {
            "pipeline_version": version,
            "device": device,
            "use_layout_detection": True,
            "use_doc_orientation_classify": self.settings.get(
                "use_doc_orientation_classify", False
            ),
            "use_doc_unwarping": self.settings.get("use_doc_unwarping", False),
            "format_block_content": True,
        }

        # CPU tuning options are only passed for CPU inference.
        if device == "cpu":
            kwargs["enable_mkldnn"] = self.settings.get("enable_mkldnn", True)
            kwargs["cpu_threads"] = int(self.settings.get("cpu_threads", 6))

        self.model = PaddleOCRVL(**kwargs)
        print(f"{self.MODEL_ID} loaded successfully (device={device}).")

    def predict(self, image_path):
        if self.model is None:
            raise RuntimeError("OCR model is not loaded. Call load() first.")

        image_path = str(Path(image_path).resolve())
        predictions = self.model.predict(image_path)

        extracted_results = []
        full_text_parts = []
        block_count = 0
        output_dir = Path(
            self.settings.get("ocr_output_directory", "output/ocr")
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        for page_index, prediction in enumerate(predictions, start=1):
            data = prediction.json
            if callable(data):
                data = data()
            if not isinstance(data, dict):
                data = {}

            # PaddleX result objects normally expose {"res": {...}}.
            data = data.get("res", data)
            parsing_blocks = data.get("parsing_res_list", [])

            for block_index, block in enumerate(parsing_blocks):
                text = str(block.get("block_content") or "").strip()
                if not text:
                    continue

                bbox = self._box_to_polygon(block.get("block_bbox"))
                metadata = {
                    "block_label": block.get("block_label"),
                    "block_id": block.get("block_id", block_index),
                    "block_order": block.get("block_order"),
                    "page_index": data.get("page_index", page_index - 1),
                }

                extracted_results.append(
                    OCRResult(
                        text=text,
                        confidence=None,
                        bounding_box=bbox,
                        metadata=metadata,
                    )
                )
                full_text_parts.append(text)
                block_count += 1

            # Keep model-native JSON and Markdown for debugging/auditing.
            if self.settings.get("save_model_outputs", True):
                try:
                    prediction.save_to_json(save_path=str(output_dir))
                    prediction.save_to_markdown(save_path=str(output_dir))
                except (AttributeError, TypeError, ValueError) as error:
                    print(f"Warning: could not save model-native output: {error}")

        if not extracted_results:
            raise ValueError(
                "PaddleOCR-VL returned no parsing blocks. "
                "Check the input image and model output."
            )

        return DocumentOCRResult(
            source_path=image_path,
            results=extracted_results,
            full_text="\n".join(full_text_parts),
            metadata={
                "engine": self.MODEL_ID,
                "pipeline_version": "v1.6",
                "result_count": block_count,
            },
        )

    def unload(self):
        self.model = None
        print(f"{self.MODEL_ID} unloaded.")
