# DocuFlow-AI
AI powered document intelligence system for automated document processing, OCR, information extraction, and structured data generation.

# Stage 1 — Local Document Upload

1. Checks that the file exists and is not empty.
2. Accepts only PDF, JPG/JPEG and PNG extensions.
3. Checks the file content signature / decodability instead of trusting the extension.
4. Enforces the maximum file size.
5. Calculates SHA-256 and detects duplicate content.
6. Stores the original file in `input/` without preprocessing it.

## Supported files

- PDF (`.pdf`)
- JPEG (`.jpg`, `.jpeg`)
- PNG (`.png`)

The default maximum file size is 25 MB per file. You can change it using `--max-size-mb` or the `DocumentUploader` constructor.

## Upload from the command line

From the project root, activate your Python environment and run:

```bash
python upload_local.py path/to/invoice.pdf path/to/scan.jpg path/to/image.png
```

For a different size limit:

```bash
python upload_local.py path/to/invoice.pdf --max-size-mb 40
```

`status` is `uploaded` for a new document and `duplicate` when the SHA-256 hash already exists in the database.

# Stage 2 --- Image Preprocessing

Stage 2 prepares uploaded PDF, JPG and PNG documents for downstream
processing while preserving the original files. The existing `main.py`
pipeline discovers documents in `input/`; no separate preprocessing
command or manual file path is required.

## What it does

1.  Reads documents from the existing `input/` directory through the
    pipeline.
2.  Converts PDF pages into images using PyMuPDF (`import pymupdf`).
3.  Preprocesses image copies; original uploads remain unchanged.
4.  Resizes images only when their longest dimension exceeds 3000
    pixels.
5.  Optionally converts images to grayscale (`grayscale=False` by
    default).
6.  Optionally enhances contrast and sharpness (`enhance=True` by
    default; factors are configurable).
7.  Passes prepared images into the existing document-processing
    pipeline.

## Image enhancement

`preprocess_image()` accepts these options:

-   `max_dimension=3000` --- maximum width or height before resizing.
-   `grayscale=False` --- retains colour information by default.
-   `enhance=True` --- enables enhancement.
-   `contrast_factor=1.2` --- adjusts contrast.
-   `sharpness_factor=1.3` --- adjusts sharpness.

# Stage 3: PaddleOCR-VL 1.6 Integration

Stage 3 replaces the previous text-only `PaddleOCR` inference adapter with
the complete **PaddleOCR-VL 1.6 document-parsing pipeline**. Stage 1 upload
and Stage 2 image/PDF preprocessing remain in place.

## What changed

- Uses `PaddleOCRVL(pipeline_version="v1.6")`.
- Enables layout detection and vision-language recognition.
- Converts PaddleOCR-VL reading-order blocks into DocuFlow's existing OCR
  result format, so the layout adapter, invoice extractor, and SQLite
  exporter continue to work.
- Saves model-native JSON and Markdown results under `output/ocr/`.
- Re-runs OCR for cached documents whose previous engine was not
  `PaddleOCR-VL-1.6`. This prevents old PaddleOCR results from being
  mistaken for new model output.
- Keeps PDF page rendering and image preprocessing unchanged.

### CPU installation (current default)

The supplied `config/settings.json` uses CPU inference, matching the
previous project configuration and avoiding VRAM pressure on a 6 GB GPU.

```powershell
python -m pip install paddlepaddle==3.2.1

If PaddleOCR reports a missing optional document-parser dependency, run:

```powershell
python -m pip install -U "paddleocr[doc-parser]"
```

Do not install the CPU and GPU builds of PaddlePaddle in the same
environment.

## Run

Put supported files in `input/`, then run:

```powershell
python main.py
```

On the first run, PaddleOCR-VL downloads its model assets. Keep an internet
connection available until initialization and the first inference complete.

## Output

- `output/processed/` — preprocessed page images from Stage 2.
- `output/ocr/` — PaddleOCR-VL JSON and Markdown parsing results.
- `output/document_ai_v2.db` — structured invoice data and OCR layout.

## Important notes

- The first inference can take longer because model assets must be
  downloaded and initialized.
- PaddleOCR-VL returns layout blocks, not the same word-level detections
  as the old `PaddleOCR` recognizer. DocuFlow adapts those blocks into its
  existing layout format.
- Invoice field extraction is still the current rule-based
  `InvoiceExtractor`; this stage upgrades document parsing, not the
  downstream invoice extraction logic.
- Review OCR JSON/Markdown for each sample before evaluating invoice-field
  accuracy. Do not assume every field is correct simply because inference
  completed successfully.



``` bash
python -m pip install -r requirements.txt
```
Active Development

DocuFlow AI is being developed incrementally, with an emphasis on modular architecture, reliable document processing, and extensibility.

The current implementation focuses on document ingestion and preprocessing. Additional AI capabilities and SaaS components will be introduced progressively.
