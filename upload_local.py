"""Simple local entry point for Stage 1 document uploads.

Usage:
    python upload_local.py path/to/invoice.pdf path/to/image.jpg
"""

import argparse

from app.ingestion.document_uploader import DocumentUploader

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload PDF, JPG or PNG documents into DocuFlow AI."
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="One or more local PDF, JPG or PNG file paths.",
    )
    parser.add_argument(
        "--max-size-mb",
        type=int,
        default=25,
        help="Maximum size per file in MB (default: 25).",
    )
    args = parser.parse_args()

    uploader = DocumentUploader(max_file_size_mb=args.max_size_mb)
    results = uploader.upload_many(args.files)

    print("\n========== UPLOAD SUMMARY ==========")
    for file_path, result in zip(args.files, results):
        if isinstance(result, Exception):
            print(f"FAILED: {file_path} | {result}")
            continue

        print(
            f"{result.status.upper()}: {result.original_filename} | "
            f"document_id={result.document_id} | "
            f"stored={result.stored_path}"
        )


if __name__ == "__main__":
    main()
