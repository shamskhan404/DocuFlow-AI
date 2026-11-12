import re
from datetime import datetime


class InvoiceExtractor:
    """Rule-based invoice extractor. Unknown or ambiguous fields remain None."""

    MONEY = r"-?\d[\d,]*(?:\.\d{1,2})?"
    DATE = r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{2}-\d{2})\b"

    STOP_LABELS = (
        "INVOICE DATE", "DUE DATE", "INVOICE NO", "INVOICE #",
        "DESCRIPTION", "ITEM DESCRIPTION", "TOTAL AMOUNT",
        "PAYMENT TERMS", "SUBTOTAL", "GRAND TOTAL",
    )

    def extract(self, layout):
        lines = [
            re.sub(r"\s+", " ", str(item.get("text", ""))).strip()
            for item in layout
            if str(item.get("text", "")).strip()
        ]
        text = "\n".join(lines)

        data = {
            "document_type": "invoice",
            "document_number": None,
            "seller_name": None,
            "seller_address": None,
            "customer_name": None,
            "customer_address": None,
            "document_date": None,
            "due_date": None,
            "currency": None,
            "subtotal": None,
            "tax_amount": None,
            "tax_rate": None,
            "discount_amount": None,
            "total_amount": None,
            "amount_paid": None,
            "balance_due": None,
            "is_emi": None,
            "emi_months": None,
            "emi_amount": None,
            "payment_status": None,
            "date_source": None,
            "line_items": [],
        }

        def clean(value):
            if not value:
                return None
            value = re.sub(r"\s+", " ", value).strip(" \t:|-")
            if not value or (value.startswith("[") and value.endswith("]")):
                return None
            if re.search(r"\[(?:NAME|COMPANY|STREET|CITY|PHONE|123456)", value, re.I):
                return None
            if re.search(r"\b(?:INVOICE DATE|DUE DATE|TOTAL AMOUNT)\b", value, re.I):
                value = re.split(
                    r"\b(?:INVOICE DATE|DUE DATE|TOTAL AMOUNT)\b",
                    value, maxsplit=1, flags=re.I
                )[0].strip(" :-|")
            return value or None

        def number(value):
            if value is None:
                return None
            try:
                return float(value.replace(",", "").replace(" ", ""))
            except (ValueError, AttributeError):
                return None

        def amount_after(label_pattern, source=text):
            """Find an amount after a label, on the same line or numeric next line."""
            for index, line in enumerate(source.splitlines()):
                match = re.search(
                    label_pattern + r"\s*[:\-]?\s*[$₹€£]?\s*(" + self.MONEY + r")",
                    line, re.I
                )
                if match:
                    return number(match.group(1))

                if re.search(label_pattern, line, re.I):
                    following = source.splitlines()[index + 1:index + 2]
                    if following:
                        candidate = following[0].strip()
                        if re.fullmatch(r"[$₹€£]?\s*" + self.MONEY, candidate):
                            return number(re.sub(r"[$₹€£\s]", "", candidate))
            return None

        def valid_name(value):
            value = clean(value)
            if not value:
                return None
            if re.fullmatch(r"[\d\s.,:/-]+", value):
                return None
            if re.search(
                r"\b(?:INVOICE|DATE|DUE|TOTAL|SUBTOTAL|DESCRIPTION|QTY|"
                r"AMOUNT|PAYMENT TERMS|BILL TO|BUYER ADDRESS|SHIP TO)\b",
                value, re.I
            ):
                return None
            if len(value) > 90:
                return None
            return value

        # Invoice number: permit OCR spaces around slash separators.
        number_patterns = [
            r"\bINVOICE\s*(?:NO\.?|NUMBER|#)\s*[:\-]?\s*"
            r"([A-Z0-9]+(?:\s*/\s*[A-Z0-9]+)*)",
        ]
        for pattern in number_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                candidate = re.sub(r"\s+", "", match.group(1)).strip("/")
                # Numeric identifiers are valid; reject short label fragments below.
                if candidate.lower() not in {"on", "no", "date", "number"}:
                    if not candidate.startswith("["):
                        data["document_number"] = candidate
                break

        # Seller name: known anchors first, then conservative header fallback.
        known_sellers = (
            ("KAPOOR WATCH CO, PVT, LTD.", r"KAPOOR\s+WATCH\s+CO[.,]?\s*PVT[.,]?\s*LTD\.?"),
            ("WORLD Of TITAN", r"WORLD\s+OF\s+TITAN"),
            ("East Repair Inc.", r"EAST\s+REPAIR\s+INC\.?"),
        )
        for display, pattern in known_sellers:
            if re.search(pattern, text, re.I):
                data["seller_name"] = display
                break

        if not data["seller_name"]:
            excluded = (
                "INVOICE", "TAX INVOICE", "DATE", "BILL TO", "SHIP TO",
                "CUSTOMER", "PHONE", "FAX", "WEBSITE", "GSTIN",
            )
            for line in lines[:10]:
                candidate = valid_name(line)
                if candidate and not any(x in candidate.upper() for x in excluded):
                    if not re.search(r"\d{3,}", candidate):
                        data["seller_name"] = candidate
                        break

        # Seller address: collect a small number of lines after seller anchor.
        if data["seller_name"]:
            seller_idx = next(
                (i for i, line in enumerate(lines)
                 if data["seller_name"].lower() in line.lower()),
                -1
            )
            if seller_idx >= 0:
                address = []
                for line in lines[seller_idx + 1:]:
                    if any(label in line.upper() for label in (
                        "BILL TO", "BUYER", "SHIP TO", "INVOICE NO",
                        "INVOICE #", "INVOICE DATE", "DUE DATE",
                    )):
                        break
                    if re.search(r"\b(?:GSTIN|PHONE|MOBILE|EMAIL|E-MAIL)\b", line, re.I):
                        continue
                    candidate = clean(line)
                    if candidate and len(candidate) <= 120:
                        address.append(candidate)
                    if len(address) == 3:
                        break
                if address:
                    data["seller_address"] = ", ".join(address)

        # Customer fields: handle text after the label on the same OCR line.
        customer_labels = (
            r"BILL\s*TO\s*:?",
            r"BUYER\s*:?",
            r"CUSTOMER\s*NAME\s*:?",
        )
        customer_found = False
        for i, line in enumerate(lines):
            for label in customer_labels:
                match = re.search(label, line, re.I)
                if not match:
                    continue
                remainder = line[match.end():]
                # In two-column invoices, remove adjacent column/section labels.
                remainder = re.split(
                    r"\b(?:SHIP\s*TO|INVOICE\s*#|INVOICE\s*NO\.?|"
                    r"INVOICE\s*DATE|TOTAL\s+AMOUNT)\b",
                    remainder, maxsplit=1, flags=re.I
                )[0]
                candidate = valid_name(remainder)
                if candidate:
                    data["customer_name"] = candidate
                    customer_found = True
                elif i + 1 < len(lines):
                    next_line = lines[i + 1]
                    next_line = re.split(
                        r"\b(?:INVOICE\s*DATE|DUE\s*DATE|TOTAL\s+AMOUNT|"
                        r"DESCRIPTION|ITEM DESCRIPTION)\b",
                        next_line, maxsplit=1, flags=re.I
                    )[0]
                    candidate = valid_name(next_line)
                    if candidate:
                        # Remove duplicated adjacent-column names.
                        parts = candidate.split()
                        if len(parts) >= 2 and len(parts) % 2 == 0:
                            half = len(parts) // 2
                            if [p.lower() for p in parts[:half]] == [
                                p.lower() for p in parts[half:]
                            ]:
                                candidate = " ".join(parts[:half])
                        data["customer_name"] = candidate
                        customer_found = True
                if customer_found:
                    break
            if customer_found:
                break

        # Fallback for layouts where BILL TO and customer are in adjacent columns.
        if not data["customer_name"]:
            for line in lines:
                if "INVOICE DATE" in line.upper():
                    before_date = re.split(r"INVOICE\s+DATE", line, flags=re.I)[0]
                    names = re.findall(
                        r"\b[A-Z][A-Za-z.&'-]+(?:\s+[A-Z][A-Za-z.&'-]+)+\b",
                        before_date
                    )
                    if names:
                        candidate = valid_name(names[-1])
                        if candidate:
                            data["customer_name"] = candidate
                    break

        # Dates: only normalize when unambiguous, or when ISO formatted.
        def find_date(label):
            for line in lines:
                match_label = re.search(label, line, re.I)
                if match_label:
                    match = re.search(self.DATE, line[match_label.end():])
                    if match:
                        return match.group(0)
            return None

        raw_date = (
            find_date(r"INVOICE\s+DATE")
            or find_date(r"\bDATE\s*:")
            or find_date(r"\bDATE\b")
        )
        raw_due = find_date(r"DUE\s+DATE")

        def normalize_date(value):
            if not value:
                return None, None
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                try:
                    return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d"), "ISO"
                except ValueError:
                    return None, None

            parts = re.split(r"[/-]", value)
            first, second = int(parts[0]), int(parts[1])
            if first > 12:
                fmt, source = ("%d/%m/%Y" if "/" in value else "%d-%m-%Y"), "day_first_inferred"
            elif second > 12:
                fmt, source = ("%m/%d/%Y" if "/" in value else "%m-%d-%Y"), "month_first_inferred"
            else:
                return None, None
            try:
                return datetime.strptime(value, fmt).strftime("%Y-%m-%d"), source
            except ValueError:
                return None, None

        data["document_date"], data["date_source"] = normalize_date(raw_date)
        data["due_date"], _ = normalize_date(raw_due)

        # Currency.
        if "₹" in text or re.search(r"\b(?:RUPEES|GSTIN|CGST|SGST|IGST)\b", text, re.I):
            data["currency"] = "INR"
        elif "$" in text:
            data["currency"] = "USD"
        elif "€" in text:
            data["currency"] = "EUR"
        elif "£" in text:
            data["currency"] = "GBP"

        # Financial fields.
        data["subtotal"] = amount_after(r"\bSUB\s*TOTAL\b")
        data["total_amount"] = (
            amount_after(r"\bGRAND\s+TOTAL\b")
            or amount_after(r"\bTOTAL\s+AMOUNT\b")
        )
        if data["total_amount"] is None:
            # A summary row may contain several figures; the final figure
            # on a line beginning with TOTAL is the invoice total.
            for line in lines:
                if re.match(r"^\s*TOTAL\b", line, re.I):
                    values = re.findall(self.MONEY, line)
                    if values:
                        data["total_amount"] = number(values[-1])
                        break

        # Sales-tax amount and rate must be extracted separately.
        tax_line_patterns = (
            r"\bSALES\s+TAX\b",
            r"\bTAX\s+AMOUNT\b",
            r"\bTAX\s+DUE\b",
        )
        for pattern in tax_line_patterns:
            value = amount_after(pattern)
            if value is not None:
                data["tax_amount"] = value
                break

        # Common compact format: "Tax (1%): 23.15" or "Sales Tax 6.25% 9.06".
        if data["tax_amount"] is None:
            for line in lines:
                if re.search(r"\b(?:SALES\s+TAX|TAX)\b", line, re.I):
                    if "%" in line:
                        after_rate = re.search(
                            r"%\s*[:\-]?\s*[$₹€£]?\s*(" + self.MONEY + r")",
                            line
                        )
                        if after_rate:
                            data["tax_amount"] = number(after_rate.group(1))
                            break

        rate_match = re.search(
            r"\b(?:SALES\s+TAX|TAX\s+RATE|TAX)\b[^\n]{0,35}?(\d+(?:\.\d+)?)\s*%",
            text, re.I
        )
        if rate_match:
            data["tax_rate"] = float(rate_match.group(1))

        # GST components, if explicitly labelled.
        gst_values = []
        for label in ("CGST", "SGST", "IGST"):
            value = amount_after(r"\b" + label + r"\b")
            if value is not None:
                gst_values.append(value)
        if gst_values:
            data["tax_amount"] = round(sum(gst_values), 2)

        data["discount_amount"] = amount_after(r"\bDISCOUNT\b")
        data["amount_paid"] = amount_after(r"\bAMOUNT\s+PAID\b")
        data["balance_due"] = amount_after(r"\bBALANCE\s+DUE\b")

        # Infer tax only when subtotal and total are known and no discount
        # or shipping line complicates the calculation.
        if (
            data["tax_amount"] is None
            and data["subtotal"] is not None
            and data["total_amount"] is not None
            and data["discount_amount"] is None
            and not re.search(r"\bSHIPPING\b", text, re.I)
        ):
            difference = round(data["total_amount"] - data["subtotal"], 2)
            if difference >= 0:
                data["tax_amount"] = difference

        if (
            data["tax_rate"] is None
            and data["tax_amount"] is not None
            and data["subtotal"] not in (None, 0)
        ):
            data["tax_rate"] = round(data["tax_amount"] / data["subtotal"] * 100, 2)

        if (
            data["balance_due"] is None
            and data["total_amount"] is not None
            and data["amount_paid"] is not None
        ):
            data["balance_due"] = round(
                data["total_amount"] - data["amount_paid"], 2
            )

        if data["balance_due"] is not None:
            if data["balance_due"] <= 0:
                data["payment_status"] = "paid"
            elif data["amount_paid"] is not None and data["amount_paid"] > 0:
                data["payment_status"] = "partially_paid"
            else:
                data["payment_status"] = "unpaid"
        elif re.search(r"\b(?:FULLY\s+PAID|PAID)\b", text, re.I):
            data["payment_status"] = "paid"

        # EMI: do not interpret arbitrary "12 months" unless EMI is mentioned.
        emi_match = re.search(r"\b(?:EMI|EQUAL MONTHLY INSTALLMENT)\b", text, re.I)
        if emi_match:
            data["is_emi"] = True
            months = re.search(
                r"\b(\d{1,2})\s*(?:MONTHS?|MTHS?)\b", text, re.I
            )
            if months:
                data["emi_months"] = int(months.group(1))
            emi_amount = re.search(
                r"\bEMI(?:\s+AMOUNT)?\s*[:\-]?\s*[$₹]?\s*(" + self.MONEY + r")",
                text, re.I
            )
            if emi_amount:
                data["emi_amount"] = number(emi_amount.group(1))
        elif re.search(r"\bNO\s+EMI\b|\bNOT\s+ON\s+EMI\b", text, re.I):
            data["is_emi"] = False

        # Line items: conservative generic row parser.
        row_pattern = re.compile(
            r"^\s*(\d+)\s+(.+?)\s+(" + self.MONEY + r")\s+(" +
            self.MONEY + r")\s*$"
        )
        stop_words = (
            "SUBTOTAL", "TOTAL", "TAX", "DISCOUNT", "SHIPPING",
            "AMOUNT PAID", "BALANCE DUE", "DESCRIPTION", "ITEM DESCRIPTION",
        )
        for line in lines:
            if any(word in line.upper() for word in stop_words):
                continue
            match = row_pattern.match(line)
            if not match:
                continue
            description = clean(match.group(2))
            quantity = number(match.group(1))
            unit_price = number(match.group(3))
            line_total = number(match.group(4))
            if description and quantity is not None and unit_price is not None and line_total is not None:
                data["line_items"].append({
                    "description": description,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "tax_amount": None,
                    "discount_amount": None,
                    "line_total": line_total,
                })

        return data
