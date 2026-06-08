import json
from pathlib import Path
from typing import Dict, Any
from collections import Counter
from .models import Batch, Severity, ValidationType, ExitCode


class ExportResult:
    def __init__(self, output_path: str, exit_code: ExitCode = ExitCode.SUCCESS):
        self.output_path = output_path
        self.exit_code = exit_code


class ReportExporter:
    def export(self, batch: Batch, output_path: str, format: str = "markdown") -> ExportResult:
        format = format.lower()
        if format in ["md", "markdown"]:
            content = self._generate_markdown(batch)
        elif format in ["json"]:
            content = self._generate_json(batch)
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'markdown' or 'json'")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return ExportResult(str(path), ExitCode.SUCCESS)

    def _generate_json(self, batch: Batch) -> str:
        summary = self._build_summary(batch)
        data = {
            "batch_id": batch.batch_id,
            "created_at": batch.created_at,
            "source_file": batch.source_file,
            "file_type": batch.file_type,
            "validated": batch.validated,
            "validated_at": batch.validated_at,
            "summary": summary,
            "invoices": [inv.to_dict() for inv in batch.invoices],
            "issues": [iss.to_dict() for iss in batch.issues],
            "fixes": [fix.to_dict() for fix in batch.fixes],
            "last_undo": batch.last_undo,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def _build_summary(self, batch: Batch) -> Dict[str, Any]:
        severity_counts = Counter(iss.severity.value for iss in batch.issues)
        type_counts = Counter(iss.type.value for iss in batch.issues)
        applied_fixes = [f for f in batch.fixes if f.applied]
        unapplied_fixes = [f for f in batch.fixes if not f.applied]

        total_amount = sum(inv.amount for inv in batch.invoices)
        total_tax = sum(inv.tax_amount for inv in batch.invoices)
        grand_total = sum(inv.total_amount for inv in batch.invoices)

        return {
            "invoice_count": len(batch.invoices),
            "issue_count": len(batch.issues),
            "error_count": severity_counts.get("error", 0),
            "warning_count": severity_counts.get("warning", 0),
            "info_count": severity_counts.get("info", 0),
            "issue_by_type": dict(type_counts),
            "fix_count": len(batch.fixes),
            "applied_fix_count": len(applied_fixes),
            "unapplied_fix_count": len(unapplied_fixes),
            "total_amount": round(total_amount, 2),
            "total_tax": round(total_tax, 2),
            "grand_total": round(grand_total, 2),
            "has_undo": batch.last_undo is not None,
        }

    def _generate_markdown(self, batch: Batch) -> str:
        summary = self._build_summary(batch)
        lines = []

        lines.append(f"# 发票校验审计报告")
        lines.append("")
        lines.append(f"- **批次 ID**: `{batch.batch_id}`")
        lines.append(f"- **创建时间**: {batch.created_at}")
        lines.append(f"- **源文件**: {batch.source_file}")
        lines.append(f"- **文件类型**: {batch.file_type.upper()}")
        lines.append(f"- **校验状态**: {'✓ 已校验' if batch.validated else '○ 未校验'}")
        if batch.validated_at:
            lines.append(f"- **校验时间**: {batch.validated_at}")
        lines.append("")

        lines.append("## 汇总")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 发票总数 | {summary['invoice_count']} |")
        lines.append(f"| 问题总数 | {summary['issue_count']} |")
        lines.append(f"| - 错误 | {summary['error_count']} |")
        lines.append(f"| - 警告 | {summary['warning_count']} |")
        lines.append(f"| 修正草案 | {summary['fix_count']} |")
        lines.append(f"| - 已应用 | {summary['applied_fix_count']} |")
        lines.append(f"| - 待应用 | {summary['unapplied_fix_count']} |")
        lines.append(f"| 金额合计 | ¥{summary['total_amount']:,.2f} |")
        lines.append(f"| 税额合计 | ¥{summary['total_tax']:,.2f} |")
        lines.append(f"| 价税合计 | ¥{summary['grand_total']:,.2f} |")
        lines.append(f"| 撤销记录 | {'有' if summary['has_undo'] else '无'} |")
        lines.append("")

        if summary["issue_by_type"]:
            lines.append("### 问题类型分布")
            lines.append("")
            lines.append("| 类型 | 数量 |")
            lines.append("|------|------|")
            for type_name, count in sorted(summary["issue_by_type"].items()):
                lines.append(f"| {type_name} | {count} |")
            lines.append("")

        if batch.issues:
            lines.append("## 校验问题详情")
            lines.append("")
            for i, issue in enumerate(batch.issues, 1):
                severity_icon = "🔴" if issue.severity == Severity.ERROR else "🟡" if issue.severity == Severity.WARNING else "🔵"
                lines.append(f"### {i}. {severity_icon} {issue.type.value}")
                lines.append("")
                lines.append(f"- **严重程度**: {issue.severity.value}")
                if issue.invoice_no:
                    lines.append(f"- **发票号**: {issue.invoice_no}")
                if issue.row_index is not None:
                    lines.append(f"- **行号**: {issue.row_index}")
                lines.append(f"- **描述**: {issue.message}")
                if issue.details:
                    lines.append("- **详情**:")
                    for k, v in issue.details.items():
                        lines.append(f"  - {k}: `{v}`")
                lines.append("")

        if batch.fixes:
            lines.append("## 修正记录")
            lines.append("")
            for i, fix in enumerate(batch.fixes, 1):
                status = "✅ 已应用" if fix.applied else "⏳ 待应用"
                lines.append(f"### {i}. {status} {fix.description}")
                lines.append("")
                lines.append(f"- **修正 ID**: `{fix.id}`")
                lines.append(f"- **发票号**: {fix.invoice_no}")
                lines.append(f"- **字段**: `{fix.field}`")
                lines.append(f"- **原值**: `{fix.old_value}`")
                lines.append(f"- **新值**: `{fix.new_value}`")
                lines.append(f"- **原因**: {fix.reason}")
                if fix.applied_at:
                    lines.append(f"- **应用时间**: {fix.applied_at}")
                lines.append("")

        if batch.last_undo:
            lines.append("## 最近撤销记录")
            lines.append("")
            undo = batch.last_undo
            undone_at = undo.get("undone_at")
            if undone_at:
                lines.append(f"- **状态**: ✅ 已撤销")
                lines.append(f"- **撤销时间**: {undone_at}")
            else:
                lines.append(f"- **状态**: ⏳ 可撤销")
            lines.append(f"- **修正 ID**: `{undo.get('fix_id', 'N/A')}`")
            lines.append(f"- **发票号**: {undo.get('invoice_no', 'N/A')}")
            lines.append(f"- **字段**: `{undo.get('field', 'N/A')}`")
            lines.append(f"- **恢复值**: `{undo.get('restored_value', 'N/A')}`")
            prev_val = undo.get("previous_value")
            if prev_val is not None:
                lines.append(f"- **撤销前值**: `{prev_val}`")
            lines.append("")

        lines.append("---")
        lines.append("*报告由 invoice-validator 自动生成*")

        return "\n".join(lines)
