from typing import List, Tuple, Dict, Any, Optional
from collections import defaultdict
from .models import (
    Invoice, ValidationIssue, ValidationType, Severity,
    Config, FixAction, ExitCode, EffectiveConfigInfo, SupplierRule,
)
from datetime import datetime
import uuid


class ValidationResult:
    def __init__(
        self,
        issues: List[ValidationIssue],
        fixes: List[FixAction],
        exit_code: ExitCode = ExitCode.SUCCESS,
        rule_sources: Optional[Dict[str, EffectiveConfigInfo]] = None,
        conflicts: Optional[List[Dict[str, Any]]] = None,
    ):
        self.issues = issues
        self.fixes = fixes
        self.exit_code = exit_code
        self.rule_sources = rule_sources or {}
        self.conflicts = conflicts or []


class InvoiceValidator:
    def __init__(self, config: Config):
        self.config = config

    def _get_effective_config(self, invoice: Invoice) -> Tuple[Config, Optional[SupplierRule]]:
        """获取发票的有效配置（供应商规则优先）"""
        return self.config.get_effective_config(invoice.supplier)

    def _build_rule_source_info(self, supplier: str, rule: Optional[SupplierRule]) -> EffectiveConfigInfo:
        """构建规则来源信息"""
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

    def validate(self, invoices: List[Invoice]) -> ValidationResult:
        issues: List[ValidationIssue] = []
        fixes: List[FixAction] = []
        rule_sources: Dict[str, EffectiveConfigInfo] = {}
        conflicts: List[Dict[str, Any]] = []

        for inv in invoices:
            _, rule = self._get_effective_config(inv)
            rule_source = self._build_rule_source_info(inv.supplier, rule)
            if not inv.rule_source:
                inv.rule_source = rule_source
            rule_sources[inv.invoice_no] = rule_source

            if rule and rule_source.conflicts:
                conflicts.append({
                    "invoice_no": inv.invoice_no,
                    "supplier": inv.supplier,
                    "conflicts": rule_source.conflicts,
                })

        issues.extend(self._check_duplicate_invoice_nos(invoices))
        issues.extend(self._check_valid_tax_rates(invoices, rule_sources))
        amt_issues, amt_fixes = self._check_amount_consistency(invoices, rule_sources)
        issues.extend(amt_issues)
        fixes.extend(amt_fixes)

        has_errors = any(iss.severity == Severity.ERROR for iss in issues)
        exit_code = ExitCode.VALIDATION_ERRORS if has_errors else ExitCode.SUCCESS

        if any(iss.type == ValidationType.INVALID_TAX_RATE and iss.severity == Severity.ERROR for iss in issues):
            exit_code = ExitCode.INVALID_TAX_RATE

        return ValidationResult(issues, fixes, exit_code, rule_sources, conflicts)

    def _check_duplicate_invoice_nos(self, invoices: List[Invoice]) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        invoice_map = defaultdict(list)

        for inv in invoices:
            invoice_map[inv.invoice_no].append(inv)

        for inv_no, inv_list in invoice_map.items():
            if len(inv_list) > 1:
                rows = [inv.row_index for inv in inv_list]
                for inv in inv_list:
                    rule_src = inv.rule_source.rule_source if inv.rule_source else "global"
                    issues.append(ValidationIssue(
                        type=ValidationType.DUPLICATE_INVOICE_NO,
                        severity=Severity.ERROR,
                        message=f"Duplicate invoice number '{inv_no}' found in rows {rows}",
                        invoice_no=inv_no,
                        row_index=inv.row_index,
                        details={
                            "duplicate_rows": rows,
                            "count": len(inv_list),
                            "supplier": inv.supplier,
                            "rule_source": rule_src,
                        },
                    ))

        return issues

    def _check_valid_tax_rates(self, invoices: List[Invoice], rule_sources: Dict[str, EffectiveConfigInfo]) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []

        for inv in invoices:
            effective_cfg, rule = self._get_effective_config(inv)
            valid_rates = set(effective_cfg.valid_tax_rates)
            rule_src = "supplier" if rule else "global"

            if inv.tax_rate not in valid_rates:
                details = {
                    "invalid_rate": inv.tax_rate,
                    "valid_rates": sorted(valid_rates),
                    "supplier": inv.supplier,
                    "rule_source": rule_src,
                }
                if rule:
                    details["global_valid_rates"] = sorted(self.config.valid_tax_rates)
                    details["supplier_rule_tax_rates"] = sorted(rule.valid_tax_rates) if rule.valid_tax_rates else None
                    details["overridden"] = rule.valid_tax_rates is not None and len(rule.valid_tax_rates) > 0

                issues.append(ValidationIssue(
                    type=ValidationType.INVALID_TAX_RATE,
                    severity=Severity.ERROR,
                    message=f"Invalid tax rate {inv.tax_rate} for invoice '{inv.invoice_no}' (supplier: {inv.supplier}, rule_source: {rule_src}). "
                            f"Valid rates: {sorted(valid_rates)}",
                    invoice_no=inv.invoice_no,
                    row_index=inv.row_index,
                    details=details,
                ))

        return issues

    def _check_amount_consistency(
        self, invoices: List[Invoice], rule_sources: Dict[str, EffectiveConfigInfo]
    ) -> Tuple[List[ValidationIssue], List[FixAction]]:
        issues: List[ValidationIssue] = []
        fixes: List[FixAction] = []

        for inv in invoices:
            effective_cfg, rule = self._get_effective_config(inv)
            tolerance = effective_cfg.amount_tolerance
            rule_src = "supplier" if rule else "global"

            expected_total = round(inv.amount + inv.tax_amount, 2)
            diff = abs(inv.total_amount - expected_total)

            if diff > tolerance:
                details = {
                    "amount": inv.amount,
                    "tax_amount": inv.tax_amount,
                    "computed_total": expected_total,
                    "stated_total": inv.total_amount,
                    "difference": diff,
                    "tolerance": tolerance,
                    "supplier": inv.supplier,
                    "rule_source": rule_src,
                }
                if rule:
                    details["global_tolerance"] = self.config.amount_tolerance
                    details["supplier_tolerance"] = rule.amount_tolerance
                    details["overridden"] = rule.amount_tolerance is not None

                issues.append(ValidationIssue(
                    type=ValidationType.AMOUNT_MISMATCH,
                    severity=Severity.WARNING,
                    message=f"Amount mismatch for invoice '{inv.invoice_no}' (supplier: {inv.supplier}, rule_source: {rule_src}): "
                            f"amount + tax_amount = {inv.amount} + {inv.tax_amount} = {expected_total}, "
                            f"but total_amount = {inv.total_amount} (diff: {diff:.4f}, tolerance: {tolerance})",
                    invoice_no=inv.invoice_no,
                    row_index=inv.row_index,
                    details=details,
                ))

                fix_id = f"fix_{uuid.uuid4().hex[:8]}"
                fixes.append(FixAction(
                    id=fix_id,
                    description=f"修正发票 {inv.invoice_no} 的合计金额",
                    invoice_no=inv.invoice_no,
                    field="total_amount",
                    old_value=inv.total_amount,
                    new_value=expected_total,
                    reason=f"金额 + 税额 = {inv.amount} + {inv.tax_amount} = {expected_total}，与票面合计 {inv.total_amount} 不符",
                    row_index=inv.row_index,
                ))

            expected_tax = round(inv.amount * inv.tax_rate, 2)
            tax_diff = abs(inv.tax_amount - expected_tax)
            if tax_diff > tolerance:
                details = {
                    "amount": inv.amount,
                    "tax_rate": inv.tax_rate,
                    "computed_tax": expected_tax,
                    "stated_tax": inv.tax_amount,
                    "difference": tax_diff,
                    "tolerance": tolerance,
                    "supplier": inv.supplier,
                    "rule_source": rule_src,
                }
                if rule:
                    details["global_tolerance"] = self.config.amount_tolerance
                    details["supplier_tolerance"] = rule.amount_tolerance
                    details["overridden"] = rule.amount_tolerance is not None

                issues.append(ValidationIssue(
                    type=ValidationType.AMOUNT_TOLERANCE,
                    severity=Severity.WARNING,
                    message=f"Tax amount tolerance exceeded for invoice '{inv.invoice_no}' (supplier: {inv.supplier}, rule_source: {rule_src}): "
                            f"amount * tax_rate = {inv.amount} * {inv.tax_rate} = {expected_tax}, "
                            f"but tax_amount = {inv.tax_amount} (diff: {tax_diff:.4f}, tolerance: {tolerance})",
                    invoice_no=inv.invoice_no,
                    row_index=inv.row_index,
                    details=details,
                ))

                fix_id = f"fix_{uuid.uuid4().hex[:8]}"
                fixes.append(FixAction(
                    id=fix_id,
                    description=f"修正发票 {inv.invoice_no} 的税额",
                    invoice_no=inv.invoice_no,
                    field="tax_amount",
                    old_value=inv.tax_amount,
                    new_value=expected_tax,
                    reason=f"金额 × 税率 = {inv.amount} × {inv.tax_rate} = {expected_tax}，与票面税额 {inv.tax_amount} 不符",
                    row_index=inv.row_index,
                ))

        return issues, fixes
