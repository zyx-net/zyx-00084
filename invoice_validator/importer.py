import csv
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from .models import (
    Invoice, ValidationIssue, ValidationType, Severity, Config, ExitCode,
    EffectiveConfigInfo, SupplierRule,
)


class ImportResult:
    def __init__(
        self,
        invoices: List[Invoice],
        issues: List[ValidationIssue],
        exit_code: ExitCode = ExitCode.SUCCESS,
        rule_sources: Optional[Dict[str, EffectiveConfigInfo]] = None,
        conflicts: Optional[List[Dict[str, Any]]] = None,
    ):
        self.invoices = invoices
        self.issues = issues
        self.exit_code = exit_code
        self.rule_sources = rule_sources or {}
        self.conflicts = conflicts or []


class InvoiceImporter:
    def __init__(self, config: Config):
        self.config = config

    def _get_effective_required_fields(self, supplier: str) -> List[str]:
        """获取指定供应商的有效必填字段"""
        if not supplier:
            return self.config.required_fields
        effective_cfg, _ = self.config.get_effective_config(supplier)
        return effective_cfg.required_fields

    def _build_rule_source_info(self, supplier: str, rule: Optional[SupplierRule]) -> EffectiveConfigInfo:
        """构建规则来源信息，包含冲突检测"""
        if rule:
            conflicts = self.config.detect_conflicts(rule)
            return EffectiveConfigInfo(
                rule_source="supplier",
                supplier=supplier,
                conflicts=conflicts,
            )
        else:
            return EffectiveConfigInfo(
                rule_source="global",
                supplier=supplier,
                conflicts={},
            )

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
        rule_sources: Dict[str, EffectiveConfigInfo] = {}
        conflicts: List[Dict[str, Any]] = []
        mapping = self.config.field_mapping

        all_suppliers: List[str] = []
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []

                for row in reader:
                    supplier_col = mapping.get("supplier", "supplier")
                    supplier = row.get(supplier_col, "").strip()
                    if supplier:
                        all_suppliers.append(supplier)
        except (csv.Error, IOError):
            pass

        all_required_internal = set(self.config.required_fields)
        for supplier in set(all_suppliers):
            effective_cfg, _ = self.config.get_effective_config(supplier)
            all_required_internal.update(effective_cfg.required_fields)

        all_required_csv = [mapping[f] for f in all_required_internal]

        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []

                missing_cols = [col for col in all_required_csv if col not in headers]
                if missing_cols:
                    issues.append(ValidationIssue(
                        type=ValidationType.MISSING_REQUIRED_FIELD,
                        severity=Severity.ERROR,
                        message=f"Missing required columns: {', '.join(missing_cols)}. Available columns: {', '.join(headers)}",
                        details={"missing": missing_cols, "available": headers},
                    ))
                    return ImportResult([], issues, ExitCode.MISSING_REQUIRED_COLUMNS, rule_sources, conflicts)

                for row_idx, row in enumerate(reader, start=2):
                    try:
                        invoice = self._parse_row(row, mapping, row_idx)
                        _, rule = self.config.get_effective_config(invoice.supplier)
                        rule_source = self._build_rule_source_info(invoice.supplier, rule)
                        invoice.rule_source = rule_source
                        rule_sources[invoice.invoice_no] = rule_source

                        if rule and rule_source.conflicts:
                            conflicts.append({
                                "invoice_no": invoice.invoice_no,
                                "supplier": invoice.supplier,
                                "conflicts": rule_source.conflicts,
                            })

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
            return ImportResult([], issues, ExitCode.CORRUPTED_JSON, rule_sources, conflicts)

        return ImportResult(invoices, issues, ExitCode.SUCCESS, rule_sources, conflicts)

    def _parse_row(
        self, row: Dict[str, str], mapping: Dict[str, str], row_idx: int
    ) -> Invoice:
        def get_val(field: str, required_fields: List[str]) -> str:
            csv_col = mapping[field]
            val = row.get(csv_col, "").strip()
            if not val and field in required_fields:
                raise ValueError(f"Missing value for required field '{csv_col}'")
            return val

        def get_float(field: str, required_fields: List[str]) -> float:
            val = get_val(field, required_fields)
            try:
                return float(val)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid numeric value for '{mapping[field]}': {val}")

        supplier_col = mapping.get("supplier", "supplier")
        supplier_raw = row.get(supplier_col, "").strip()
        effective_required = self._get_effective_required_fields(supplier_raw)

        invoice_no = get_val("invoice_no", effective_required)
        amount = get_float("amount", effective_required)
        tax_rate = get_float("tax_rate", effective_required)
        if "tax_amount" in effective_required:
            tax_amount = get_float("tax_amount", effective_required)
        else:
            try:
                tax_amount = get_float("tax_amount", effective_required)
            except ValueError:
                tax_amount = round(amount * tax_rate, 2)
        total_amount = get_float("total_amount", effective_required)
        date = get_val("date", effective_required)
        supplier = get_val("supplier", effective_required)
        buyer = get_val("buyer", effective_required)

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
        rule_sources: Dict[str, EffectiveConfigInfo] = {}
        conflicts: List[Dict[str, Any]] = []
        mapping = self.config.field_mapping
        global_required_internal = self.config.required_fields

        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            issues.append(ValidationIssue(
                type=ValidationType.INVALID_JSON,
                severity=Severity.ERROR,
                message=f"Corrupted JSON: {str(e)}",
                details={"error": str(e), "position": e.pos},
            ))
            return ImportResult([], issues, ExitCode.CORRUPTED_JSON, rule_sources, conflicts)
        except IOError as e:
            issues.append(ValidationIssue(
                type=ValidationType.INVALID_JSON,
                severity=Severity.ERROR,
                message=f"Failed to read file: {str(e)}",
            ))
            return ImportResult([], issues, ExitCode.CORRUPTED_JSON, rule_sources, conflicts)

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

            supplier_key = mapping.get("supplier", "supplier")
            supplier = ""
            supplier_val = row.get(supplier_key)
            if supplier_val is not None:
                supplier = str(supplier_val).strip()

            effective_required = self._get_effective_required_fields(supplier) if supplier else global_required_internal

            available_keys = list(row.keys())
            missing = []
            for field in effective_required:
                json_key = mapping[field]
                if json_key not in row or row[json_key] is None or (isinstance(row[json_key], str) and not row[json_key].strip()):
                    missing.append(json_key)

            if missing:
                issues.append(ValidationIssue(
                    type=ValidationType.MISSING_REQUIRED_FIELD,
                    severity=Severity.ERROR,
                    message=f"Item {row_idx}: Missing required fields: {', '.join(missing)}. Available: {', '.join(available_keys)}",
                    row_index=row_idx,
                    details={
                        "missing": missing,
                        "available": available_keys,
                        "supplier": supplier,
                        "rule_source": "supplier" if supplier and supplier in self.config.supplier_rules else "global",
                    },
                ))
                continue

            try:
                invoice = self._parse_json_item(row, mapping, row_idx)
                _, rule = self.config.get_effective_config(invoice.supplier)
                rule_source = self._build_rule_source_info(invoice.supplier, rule)
                invoice.rule_source = rule_source
                rule_sources[invoice.invoice_no] = rule_source

                if rule and rule_source.conflicts:
                    conflicts.append({
                        "invoice_no": invoice.invoice_no,
                        "supplier": invoice.supplier,
                        "conflicts": rule_source.conflicts,
                    })

                invoices.append(invoice)
            except ValueError as e:
                issues.append(ValidationIssue(
                    type=ValidationType.MISSING_REQUIRED_FIELD,
                    severity=Severity.ERROR,
                    message=f"Item {row_idx}: {str(e)}",
                    row_index=row_idx,
                ))

        if any(iss.type == ValidationType.MISSING_REQUIRED_FIELD and iss.severity == Severity.ERROR for iss in issues):
            return ImportResult(invoices, issues, ExitCode.MISSING_REQUIRED_COLUMNS, rule_sources, conflicts)

        return ImportResult(invoices, issues, ExitCode.SUCCESS, rule_sources, conflicts)

    def _parse_json_item(
        self, row: Dict[str, Any], mapping: Dict[str, str], row_idx: int
    ) -> Invoice:
        supplier_key = mapping.get("supplier", "supplier")
        supplier_val = row.get(supplier_key)
        supplier_raw = str(supplier_val).strip() if supplier_val is not None else ""
        effective_required = self._get_effective_required_fields(supplier_raw)

        def get_val(field: str) -> Any:
            json_key = mapping[field]
            return row.get(json_key)

        def get_str(field: str) -> str:
            val = get_val(field)
            if val is None:
                if field in effective_required:
                    raise ValueError(f"Missing value for required field '{mapping[field]}'")
                return ""
            return str(val).strip()

        def get_float(field: str) -> float:
            val = get_val(field)
            if val is None:
                if field in effective_required:
                    raise ValueError(f"Missing value for required field '{mapping[field]}'")
                return 0.0
            try:
                return float(val)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid numeric value for '{mapping[field]}': {val}")

        invoice_no = get_str("invoice_no")
        amount = get_float("amount")
        tax_rate = get_float("tax_rate")
        if "tax_amount" in effective_required:
            tax_amount = get_float("tax_amount")
        else:
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
