
import json
import sqlite3
from pathlib import Path


class DatabaseExporter:

    def __init__(self, database_path="output/document_ai_v2.db"):

        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.initialize_database()
    def update_processing_status(
        self,
        document_id,
        status,
        error_message=None
    ):
        with self.connect() as db:

            db.execute("""
                UPDATE document_processing
                SET processing_status = ?,
                    error_message = ?,
                    processed_at = CURRENT_TIMESTAMP
                WHERE document_id = ?
            """, (
                status,
                error_message,
                document_id
            ))

    def connect(self):

        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")

        return connection

    # -----------------------------------
    # DATABASE INITIALIZATION
    # -----------------------------------

    def initialize_database(self):

        with self.connect() as db:

            db.executescript("""

                CREATE TABLE IF NOT EXISTS documents (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    document_type TEXT NOT NULL,
                    document_number TEXT,

                    seller_name TEXT,
                    seller_address TEXT,

                    customer_name TEXT,
                    customer_address TEXT,

                    document_date TEXT,
                    due_date TEXT,

                    currency TEXT,

                    subtotal REAL,
                    tax_amount REAL,
                    tax_rate REAL,
                    discount_amount REAL,
                    total_amount REAL,

                    amount_paid REAL,
                    balance_due REAL,

                    is_emi INTEGER
                        CHECK (is_emi IN (0, 1) OR is_emi IS NULL),

                    emi_months INTEGER,
                    emi_amount REAL,

                    payment_status TEXT,

                    date_source TEXT,

                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );


                CREATE TABLE IF NOT EXISTS document_files (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    document_id INTEGER NOT NULL,

                    original_filename TEXT NOT NULL,
                    stored_path TEXT NOT NULL,

                    file_hash TEXT UNIQUE,

                    page_number INTEGER DEFAULT 1,

                    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (document_id)
                        REFERENCES documents(id)
                        ON DELETE CASCADE
                );


                CREATE TABLE IF NOT EXISTS line_items (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    document_id INTEGER NOT NULL,

                    description TEXT,

                    quantity REAL,
                    unit_price REAL,

                    tax_amount REAL,
                    discount_amount REAL,

                    line_total REAL,

                    FOREIGN KEY (document_id)
                        REFERENCES documents(id)
                        ON DELETE CASCADE
                );


                CREATE TABLE IF NOT EXISTS document_processing (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    document_id INTEGER NOT NULL,

                    ocr_engine TEXT,
                    extraction_model TEXT,

                    processing_status TEXT NOT NULL,
                    error_message TEXT,

                    processed_at TEXT DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (document_id)
                        REFERENCES documents(id)
                        ON DELETE CASCADE
                );


                CREATE TABLE IF NOT EXISTS ocr_extractions (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    document_id INTEGER NOT NULL UNIQUE,

                    full_text TEXT NOT NULL,

                    detection_count INTEGER,

                    layout_json TEXT,

                    extracted_at TEXT DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (document_id)
                        REFERENCES documents(id)
                        ON DELETE CASCADE
                );


                CREATE INDEX IF NOT EXISTS idx_document_date
                ON documents(document_date);

                CREATE INDEX IF NOT EXISTS idx_document_type
                ON documents(document_type);

                CREATE INDEX IF NOT EXISTS idx_seller_name
                ON documents(seller_name);

                CREATE INDEX IF NOT EXISTS idx_file_hash
                ON document_files(file_hash);

            """)

        print("Document database initialized successfully.")

    # -----------------------------------
    # REGISTER DOCUMENT
    # -----------------------------------

    def register_document(
        self,
        source_path,
        file_hash=None,
        document_type="unknown",
        processing_status="registered"
    ):

        source_path = str(Path(source_path).resolve())

        with self.connect() as db:

            # Avoid duplicate registration by file hash.
            if file_hash:

                existing = db.execute("""
                    SELECT document_id
                    FROM document_files
                    WHERE file_hash = ?
                """, (file_hash,)).fetchone()

                if existing:
                    print("Document already exists.")
                    return existing[0]

            cursor = db.execute("""
                INSERT INTO documents (document_type)
                VALUES (?)
            """, (document_type,))

            document_id = cursor.lastrowid

            db.execute("""
                INSERT INTO document_files (
                    document_id,
                    original_filename,
                    stored_path,
                    file_hash
                )
                VALUES (?, ?, ?, ?)
            """, (
                document_id,
                Path(source_path).name,
                source_path,
                file_hash
            ))

            db.execute("""
                INSERT INTO document_processing (
                    document_id,
                    ocr_engine,
                    processing_status
                )
                VALUES (?, ?, ?)
            """, (
                document_id,
                "PaddleOCR",
                processing_status
            ))

        return document_id

    # -----------------------------------
    # SAVE OCR RESULTS
    # -----------------------------------

    def save_ocr_results(self, document_id, result, layout):

        with self.connect() as db:

            db.execute("""
                INSERT INTO ocr_extractions (
                    document_id,
                    full_text,
                    detection_count,
                    layout_json
                )
                VALUES (?, ?, ?, ?)

                ON CONFLICT(document_id)
                DO UPDATE SET

                    full_text = excluded.full_text,

                    detection_count = excluded.detection_count,

                    layout_json = excluded.layout_json,

                    extracted_at = CURRENT_TIMESTAMP

            """, (
                document_id,
                result.full_text,
                len(result.results),
                json.dumps(layout, ensure_ascii=False)
            ))

            db.execute("""
                UPDATE document_processing

                SET processing_status = 'ocr_completed',
                    processed_at = CURRENT_TIMESTAMP

                WHERE document_id = ?
            """, (document_id,))

        print("OCR information saved successfully.")

    # -----------------------------------
    # READ OCR RESULTS
    # -----------------------------------

    def get_ocr_results(self, document_id):

        with self.connect() as db:

            return db.execute("""
                SELECT
                    full_text,
                    detection_count,
                    layout_json
                FROM ocr_extractions
                WHERE document_id = ?
            """, (document_id,)).fetchone()

            # -----------------------------------
    # SAVE EXTRACTED INVOICE DATA
    # -----------------------------------

    def save_invoice_data(self, document_id, invoice_data):

        fields = [
            "document_type",
            "document_number",
            "seller_name",
            "seller_address",
            "customer_name",
            "customer_address",
            "document_date",
            "due_date",
            "currency",
            "subtotal",
            "tax_amount",
            "tax_rate",
            "discount_amount",
            "total_amount",
            "amount_paid",
            "balance_due",
            "is_emi",
            "emi_months",
            "emi_amount",
            "payment_status",
            "date_source"
        ]

        values = [
            invoice_data.get(field)
            for field in fields
        ]

        # Keep unknown EMI status as NULL.
        if values[16] is not None:
            values[16] = int(bool(values[16]))

        assignments = ", ".join(
            f"{field} = ?" for field in fields
        )

        with self.connect() as db:

            db.execute(
                f"""
                UPDATE documents
                SET {assignments},
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (*values, document_id)
            )

            # Remove old line items before inserting updated ones.
            db.execute(
                "DELETE FROM line_items WHERE document_id = ?",
                (document_id,)
            )

            for item in invoice_data.get("line_items", []):

                db.execute("""
                    INSERT INTO line_items (
                        document_id,
                        description,
                        quantity,
                        unit_price,
                        tax_amount,
                        discount_amount,
                        line_total
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    document_id,
                    item.get("description"),
                    item.get("quantity"),
                    item.get("unit_price"),
                    item.get("tax_amount"),
                    item.get("discount_amount"),
                    item.get("line_total")
                ))

            db.execute("""
                UPDATE document_processing
                SET processing_status = 'extraction_completed',
                    error_message = NULL,
                    processed_at = CURRENT_TIMESTAMP
                WHERE document_id = ?
            """, (document_id,))

        print("Invoice data saved successfully.")
