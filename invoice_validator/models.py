from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from enum import Enum


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationType(str, Enum):
    DUPLICATE_INVOICE_NO = "duplicate_invoice_no"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_TAX_RATE = "invalid_tax_rate"
    AMOUNT_MISMATCH = "amount_mismatch"
    INVALID_JSON = "invalid_json"
    AMOUNT_TOLERANCE = "amount_tolerance"


@dataclass
class EffectiveConfigInfo:
    """每张发票实际使用的配置信息，用于追溯规则来源"""
    rule_source: str
    supplier: str
    conflicts: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_source": self.rule_source,
            "supplier": self.supplier,
            "conflicts": self.conflicts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EffectiveConfigInfo":
        return cls(
            rule_source=data["rule_source"],
            supplier=data["supplier"],
            conflicts=data.get("conflicts", {}),
        )


@dataclass
class SupplierRule:
    """供应商专属校验规则"""
    supplier: str
    valid_tax_rates: List[float] = field(default_factory=list)
    amount_tolerance: Optional[float] = None
    required_fields: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "supplier": self.supplier,
            "valid_tax_rates": self.valid_tax_rates,
            "amount_tolerance": self.amount_tolerance,
            "required_fields": self.required_fields,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SupplierRule":
        return cls(
            supplier=data["supplier"],
            valid_tax_rates=data.get("valid_tax_rates", []),
            amount_tolerance=data.get("amount_tolerance"),
            required_fields=data.get("required_fields", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )


@dataclass
class Invoice:
    invoice_no: str
    amount: float
    tax_rate: float
    tax_amount: float
    total_amount: float
    date: str
    supplier: str
    buyer: str
    raw_data: Dict[str, Any] = field(default_factory=dict)
    row_index: Optional[int] = None
    rule_source: Optional[EffectiveConfigInfo] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "invoice_no": self.invoice_no,
            "amount": self.amount,
            "tax_rate": self.tax_rate,
            "tax_amount": self.tax_amount,
            "total_amount": self.total_amount,
            "date": self.date,
            "supplier": self.supplier,
            "buyer": self.buyer,
            "row_index": self.row_index,
        }
        if self.rule_source:
            data["rule_source"] = self.rule_source.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Invoice":
        rule_source = None
        if "rule_source" in data and data["rule_source"]:
            rule_source = EffectiveConfigInfo.from_dict(data["rule_source"])
        return cls(
            invoice_no=data["invoice_no"],
            amount=data["amount"],
            tax_rate=data["tax_rate"],
            tax_amount=data["tax_amount"],
            total_amount=data["total_amount"],
            date=data["date"],
            supplier=data["supplier"],
            buyer=data["buyer"],
            raw_data=data.get("raw_data", {}),
            row_index=data.get("row_index"),
            rule_source=rule_source,
        )


@dataclass
class ValidationIssue:
    type: ValidationType
    severity: Severity
    message: str
    invoice_no: Optional[str] = None
    row_index: Optional[int] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "severity": self.severity.value,
            "message": self.message,
            "invoice_no": self.invoice_no,
            "row_index": self.row_index,
            "details": self.details,
        }


@dataclass
class Config:
    field_mapping: Dict[str, str] = field(default_factory=lambda: {
        "invoice_no": "invoice_no",
        "amount": "amount",
        "tax_rate": "tax_rate",
        "tax_amount": "tax_amount",
        "total_amount": "total_amount",
        "date": "date",
        "supplier": "supplier",
        "buyer": "buyer",
    })
    valid_tax_rates: List[float] = field(default_factory=lambda: [0.0, 0.06, 0.09, 0.13])
    amount_tolerance: float = 0.01
    required_fields: List[str] = field(default_factory=lambda: [
        "invoice_no", "amount", "tax_rate", "total_amount", "date", "supplier", "buyer"
    ])
    supplier_rules: Dict[str, SupplierRule] = field(default_factory=dict)

    def get_effective_config(self, supplier: str) -> Tuple["Config", Optional[SupplierRule]]:
        """
        获取指定供应商的有效配置。
        优先匹配供应商规则，匹配不到则返回全局配置。
        返回 (有效配置, 匹配到的供应商规则或None)
        """
        rule = self.supplier_rules.get(supplier)
        if not rule:
            return self, None

        effective = Config(
            field_mapping=dict(self.field_mapping),
            valid_tax_rates=rule.valid_tax_rates if rule.valid_tax_rates else list(self.valid_tax_rates),
            amount_tolerance=rule.amount_tolerance if rule.amount_tolerance is not None else self.amount_tolerance,
            required_fields=rule.required_fields if rule.required_fields else list(self.required_fields),
            supplier_rules=dict(self.supplier_rules),
        )
        return effective, rule

    def detect_conflicts(self, rule: SupplierRule) -> Dict[str, Dict[str, Any]]:
        """检测供应商规则与全局配置的冲突"""
        conflicts = {}
        if rule.valid_tax_rates and set(rule.valid_tax_rates) != set(self.valid_tax_rates):
            conflicts["valid_tax_rates"] = {
                "global_value": sorted(list(self.valid_tax_rates)),
                "supplier_value": sorted(list(rule.valid_tax_rates)),
                "status": "overridden",
                "message": f"税率白名单不同，全局 {sorted(self.valid_tax_rates)}，供应商 {sorted(rule.valid_tax_rates)}",
            }
        if rule.amount_tolerance is not None and rule.amount_tolerance != self.amount_tolerance:
            conflicts["amount_tolerance"] = {
                "global_value": self.amount_tolerance,
                "supplier_value": rule.amount_tolerance,
                "status": "overridden",
                "message": f"金额容差不同，全局 {self.amount_tolerance}，供应商 {rule.amount_tolerance}",
            }
        if rule.required_fields and set(rule.required_fields) != set(self.required_fields):
            conflicts["required_fields"] = {
                "global_value": sorted(list(self.required_fields)),
                "supplier_value": sorted(list(rule.required_fields)),
                "status": "overridden",
                "message": f"必填字段不同，全局 {sorted(self.required_fields)}，供应商 {sorted(rule.required_fields)}",
            }
        return conflicts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_mapping": self.field_mapping,
            "valid_tax_rates": self.valid_tax_rates,
            "amount_tolerance": self.amount_tolerance,
            "required_fields": self.required_fields,
        }


@dataclass
class FixAction:
    id: str
    description: str
    invoice_no: str
    field: str
    old_value: Any
    new_value: Any
    reason: str
    row_index: Optional[int] = None
    applied: bool = False
    applied_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "invoice_no": self.invoice_no,
            "field": self.field,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "row_index": self.row_index,
            "applied": self.applied,
            "applied_at": self.applied_at,
        }


@dataclass
class Batch:
    batch_id: str
    created_at: str
    source_file: str
    file_type: str
    invoices: List[Invoice] = field(default_factory=list)
    issues: List[ValidationIssue] = field(default_factory=list)
    fixes: List[FixAction] = field(default_factory=list)
    last_undo: Optional[Dict[str, Any]] = None
    validated: bool = False
    validated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "created_at": self.created_at,
            "source_file": self.source_file,
            "file_type": self.file_type,
            "invoices": [inv.to_dict() for inv in self.invoices],
            "issues": [iss.to_dict() for iss in self.issues],
            "fixes": [fix.to_dict() for fix in self.fixes],
            "last_undo": self.last_undo,
            "validated": self.validated,
            "validated_at": self.validated_at,
        }


class ExitCode(int, Enum):
    SUCCESS = 0
    MISSING_REQUIRED_COLUMNS = 1
    CORRUPTED_JSON = 2
    INVALID_TAX_RATE = 3
    NO_APPLIED_FIX_TO_UNDO = 4
    BATCH_NOT_FOUND = 5
    VALIDATION_ERRORS = 6
    INVALID_ARGUMENT = 7
    FILE_NOT_FOUND = 8
    STORAGE_ERROR = 9
    NO_FIXES_TO_APPLY = 10
    INVALID_CONFIG = 11
    DUPLICATE_SUPPLIER_RULE = 12
    EMPTY_FIELD_NAME = 13
    PERMISSION_DENIED = 14
    SUPPLIER_RULE_NOT_FOUND = 15
