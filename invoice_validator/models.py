from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
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

    def to_dict(self) -> Dict[str, Any]:
        return {
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_mapping": self.field_mapping,
            "valid_tax_rates": self.valid_tax_rates,
            "amount_tolerance": self.amount_tolerance,
            "required_fields": self.required_fields,
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
