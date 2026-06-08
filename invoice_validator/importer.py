import csv
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from .models import Invoice, ValidationIssue, ValidationType, Severity, Config, ExitCode


class ImportResult:
    def __init__(
        self,
        invoices: List[Invoice],
        issues: List[ValidationIssue],
        exit_code: ExitCode = ExitCode.SUCCESS,
    ):
        self.invoices = invoices
        self.issues = issues
        self.exit_code = exit_code


class InvoiceImporter:
    def __init__(self, config: Config):
        self.config = config

    def import_file(self, file_path: str) -> ImportResult:
        path = Path(file_path)
        if not path.exists():
            issue = ValidationIssue(
                type=ValidationType.INVALID_JSON,
                severity=Severity.ERROR,
                message=f"File not found: {file_path}",
            )
            return ImportResult([], [issue], ExitCode.FILE_NOT_FOUND)

        ext = path.suffix.lower()
        if ext == ".csv":
            return self._import_csv(path)
        elif ext == ".json":
            return self._import_json(path)
        else:
            issue = ValidationIssue(
                type=ValidationType.INVALID_JSON,
                severity=Severity.ERROR,
                message=f"Unsupported file type: {ext}. Use .csv or .json",
            )
            return ImportResult([], [issue], ExitCode.INVALID_ARGUMENT)

    def _import_csv(self, path: Path) -> ImportResult:
        invoices: List[Invoice] = []
        issues: List[ValidationIssue] = []
        mapping = self.config.field_mapping
        required_internal = self.config.required_fields
        required_csv = [mapping[f] for f in required_internal]

        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []

                missing_cols = [col for col in required_csv if col not in headers]
                if missing_cols:
                    issues.append(ValidationIssue(
                        type=ValidationType.MISSING_REQUIRED_FIELD,
                        severity=Severity.ERROR,
                        message=f"Missing required columns: {', '.join(missing_cols)}. Available columns: {', '.join(headers)}",
                        details={"missing": missing_cols, "available": headers},
                    ))
                    return ImportResult([], issues, ExitCode.MISSING_REQUIRED_COLUMNS)

                for row_idx, row in enumerate(reader, start=2):
                    try:
                        invoice = self._parse_row(row, mapping, row_idx)
                        invoices.append(invoice)
                    except ValueError as e:
                        issues.append(ValidationIssue(
                            type=ValidationType.MISSING_REQUIRED_FIELD,
                            severity=Severity.ERROR,
                            message=f"Row {row_idx}: {str(e)}",
                            row_index=row_idx,
                        ))
        except (csv.Error, IOError) as e:
            issues.append(ValidationIssue(
                type=ValidationType.INVALID_JSON,
                severity=Severity.ERROR,
                message=f"Failed to read CSV: {str(e)}",
            ))
            return ImportResult([], issues, ExitCode.CORRUPTED_JSON)

        return ImportResult(invoices, issues, ExitCode.SUCCESS)

    def _parse_row(
        self, row: Dict[str, str], mapping: Dict[str, str], row_idx: int
    ) -> Invoice:
        def get_val(field: str) -> str:
            csv_col = mapping[field]
            val = row.get(csv_col, "").strip()
            if not val and field in self.config.required_fields:
                raise ValueError(f"Missing value for required field '{csv_col}'")
            return val

        def get_float(field: str) -> float:
            val = get_val(field)
            try:
                return float(val)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid numeric value for '{mapping[field]}': {val}")

        invoice_no = get_val("invoice_no")
        amount = get_float("amount")
        tax_rate = get_float("tax_rate")
        try:
            tax_amount = get_float("tax_amount")
        except ValueError:
            tax_amount = round(amount * tax_rate, 2)
        total_amount = get_float("total_amount")
        date = get_val("date")
        supplier = get_val("supplier")
        buyer = get_val("buyer")

        raw_data = {k: v for k, v in row.items()}

        return Invoice(
            invoice_no=invoice_no,
            amount=amount,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total_amount=total_amount,
            date=date,
            supplier=supplier,
            buyer=buyer,
            raw_data=raw_data,
            row_index=row_idx,
        )

    def _import_json(self, path: Path) -> ImportResult:
        invoices: List[Invoice] = []
        issues: List[ValidationIssue] = []
        mapping = self.config.field_mapping
        required_internal = self.config.required_fields

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            issues.append(ValidationIssue(
                type=ValidationType.INVALID_JSON,
                severity=Severity.ERROR,
                message=f"Corrupted JSON: {str(e)}",
                details={"error": str(e), "position": e.pos},
            ))
            return ImportResult([], issues, ExitCode.CORRUPTED_JSON)
        except IOError as e:
            issues.append(ValidationIssue(
                type=ValidationType.INVALID_JSON,
                severity=Severity.ERROR,
                message=f"Failed to read file: {str(e)}",
            ))
            return ImportResult([], issues, ExitCode.CORRUPTED_JSON)

        if not isinstance(data, list):
            data = [data]

        for row_idx, row in enumerate(data, start=1):
            if not isinstance(row, dict):
                issues.append(ValidationIssue(
                    type=ValidationType.INVALID_JSON,
                    severity=Severity.ERROR,
                    message=f"Item {row_idx}: Expected object, got {type(row).__name__}",
                    row_index=row_idx,
                ))
                continue

            available_keys = list(row.keys())
            missing = []
            for field in required_internal:
                json_key = mapping[field]
                if json_key not in row or row[json_key] is None or (isinstance(row[json_key], str) and not row[json_key].strip()):
                    missing.append(json_key)

            if missing:
                issues.append(ValidationIssue(
                    type=ValidationType.MISSING_REQUIRED_FIELD,
                    severity=Severity.ERROR,
                    message=f"Item {row_idx}: Missing required fields: {', '.join(missing)}. Available: {', '.join(available_keys)}",
                    row_index=row_idx,
                    details={"missing": missing, "available": available_keys},
                ))
                continue

            try:
                invoice = self._parse_json_item(row, mapping, row_idx)
                invoices.append(invoice)
            except ValueError as e:
                issues.append(ValidationIssue(
                    type=ValidationType.MISSING_REQUIRED_FIELD,
                    severity=Severity.ERROR,
                    message=f"Item {row_idx}: {str(e)}",
                    row_index=row_idx,
                ))

        if any(iss.type == ValidationType.MISSING_REQUIRED_FIELD and iss.severity == Severity.ERROR for iss in issues):
            return ImportResult(invoices, issues, ExitCode.MISSING_REQUIRED_COLUMNS)

        return ImportResult(invoices, issues, ExitCode.SUCCESS)

    def _parse_json_item(
        self, row: Dict[str, Any], mapping: Dict[str, str], row_idx: int
    ) -> Invoice:
        def get_val(field: str) -> Any:
            json_key = mapping[field]
            return row.get(json_key)

        def get_str(field: str) -> str:
            val = get_val(field)
            if val is None:
                return ""
            return str(val).strip()

        def get_float(field: str) -> float:
            val = get_val(field)
            if val is None:
                raise ValueError(f"Missing value for '{mapping[field]}'")
            try:
                return float(val)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid numeric value for '{mapping[field]}': {val}")

        invoice_no = get_str("invoice_no")
        amount = get_float("amount")
        tax_rate = get_float("tax_rate")
        try:
            tax_amount = get_float("tax_amount")
        except ValueError:
            tax_amount = round(amount * tax_rate, 2)
        total_amount = get_float("total_amount")
        date = get_str("date")
        supplier = get_str("supplier")
        buyer = get_str("buyer")

        return Invoice(
            invoice_no=invoice_no,
            amount=amount,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total_amount=total_amount,
            date=date,
            supplier=supplier,
            buyer=buyer,
            raw_data=row,
            row_index=row_idx,
        )
