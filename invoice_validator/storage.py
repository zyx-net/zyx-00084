import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from .models import Batch, Invoice, ValidationIssue, FixAction, ValidationType, Severity


class StorageManager:
    def __init__(self, workspace: Optional[str] = None):
        self.workspace = Path(workspace or os.getcwd())
        self.data_dir = self.workspace / ".invoice_validator" / "data"
        self.batches_dir = self.data_dir / "batches"
        self.current_batch_file = self.data_dir / "current_batch.json"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.batches_dir.mkdir(parents=True, exist_ok=True)

    def create_batch(self, source_file: str, file_type: str) -> Batch:
        batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        batch = Batch(
            batch_id=batch_id,
            created_at=datetime.now().isoformat(),
            source_file=source_file,
            file_type=file_type,
        )
        self.save_batch(batch)
        self.set_current_batch(batch_id)
        return batch

    def save_batch(self, batch: Batch) -> None:
        batch_file = self.batches_dir / f"{batch.batch_id}.json"
        try:
            with open(batch_file, "w", encoding="utf-8") as f:
                json.dump(batch.to_dict(), f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise RuntimeError(f"Failed to save batch: {e}") from e

    def load_batch(self, batch_id: Optional[str] = None) -> Batch:
        if batch_id is None:
            batch_id = self.get_current_batch_id()
            if batch_id is None:
                raise RuntimeError("No active batch found. Import a batch first.")

        batch_file = self.batches_dir / f"{batch_id}.json"
        if not batch_file.exists():
            raise RuntimeError(f"Batch {batch_id} not found")

        try:
            with open(batch_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise RuntimeError(f"Failed to load batch: {e}") from e

        invoices = [
            Invoice.from_dict(inv)
            for inv in data.get("invoices", [])
        ]

        issues = [
            ValidationIssue(
                type=ValidationType(iss["type"]),
                severity=Severity(iss["severity"]),
                message=iss["message"],
                invoice_no=iss.get("invoice_no"),
                row_index=iss.get("row_index"),
                details=iss.get("details", {}),
            )
            for iss in data.get("issues", [])
        ]

        fixes = [
            FixAction(
                id=fix["id"],
                description=fix["description"],
                invoice_no=fix["invoice_no"],
                field=fix["field"],
                old_value=fix["old_value"],
                new_value=fix["new_value"],
                reason=fix["reason"],
                row_index=fix.get("row_index"),
                applied=fix.get("applied", False),
                applied_at=fix.get("applied_at"),
            )
            for fix in data.get("fixes", [])
        ]

        return Batch(
            batch_id=data["batch_id"],
            created_at=data["created_at"],
            source_file=data["source_file"],
            file_type=data["file_type"],
            invoices=invoices,
            issues=issues,
            fixes=fixes,
            last_undo=data.get("last_undo"),
            validated=data.get("validated", False),
            validated_at=data.get("validated_at"),
        )

    def set_current_batch(self, batch_id: str) -> None:
        try:
            with open(self.current_batch_file, "w", encoding="utf-8") as f:
                json.dump({"batch_id": batch_id}, f, indent=2)
        except IOError as e:
            raise RuntimeError(f"Failed to set current batch: {e}") from e

    def get_current_batch_id(self) -> Optional[str]:
        if not self.current_batch_file.exists():
            return None
        try:
            with open(self.current_batch_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("batch_id")
        except (json.JSONDecodeError, IOError):
            return None

    def list_batches(self) -> List[Dict[str, Any]]:
        batches = []
        for batch_file in sorted(self.batches_dir.glob("batch_*.json"), reverse=True):
            try:
                with open(batch_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                batches.append({
                    "batch_id": data["batch_id"],
                    "created_at": data["created_at"],
                    "source_file": data["source_file"],
                    "invoice_count": len(data.get("invoices", [])),
                    "issue_count": len(data.get("issues", [])),
                    "validated": data.get("validated", False),
                })
            except (json.JSONDecodeError, IOError):
                continue
        return batches

    def delete_batch(self, batch_id: str) -> None:
        batch_file = self.batches_dir / f"{batch_id}.json"
        if batch_file.exists():
            batch_file.unlink()
