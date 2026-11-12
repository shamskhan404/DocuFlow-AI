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

## Dependency

PDF rendering uses PyMuPDF. Install the project dependencies:

``` bash
python -m pip install -r requirements.txt
```
