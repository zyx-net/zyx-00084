import json
from pathlib import Path
from typing import Dict, Any
from collections import Counter
from .models import Batch, Severity, ValidationType, ExitCode


_VALIDATION_TYPE_CN = {
    "duplicate_invoice_no": "重复发票号",
    "missing_required_field": "缺少必填字段",
    "invalid_tax_rate": "非法税率",
    "amount_mismatch": "金额不一致",
    "invalid_json": "JSON 格式错误",
    "amount_tolerance": "税额容差超限",
}

_SEVERITY_CN = {
    "error": "错误",
    "warning": "警告",
    "info": "提示",
}

_FIELD_CN = {
    "invoice_no": "发票号",
    "amount": "金额",
    "tax_rate": "税率",
    "tax_amount": "税额",
    "total_amount": "价税合计",
    "date": "开票日期",
    "supplier": "销售方",
    "buyer": "购买方",
    "row_index": "行号",
}


def _cn(text: str, mapping: Dict[str, str]) -> str:
    return mapping.get(text, text)


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
        lines.append(f"- **批次编号**: `{batch.batch_id}`")
        lines.append(f"- **创建时间**: {batch.created_at}")
        lines.append(f"- **源文件**: {batch.source_file}")
        lines.append(f"- **文件类型**: {batch.file_type.upper()}")
        lines.append(f"- **校验状态**: {'✓ 已校验' if batch.validated else '○ 未校验'}")
        if batch.validated_at:
            lines.append(f"- **校验时间**: {batch.validated_at}")
        lines.append("")

        lines.append("## 一、汇总信息")
        lines.append("")
        lines.append("| 指标项 | 数值 |")
        lines.append("|--------|------|")
        lines.append(f"| 发票总张数 | {summary['invoice_count']} |")
        lines.append(f"| 问题总数量 | {summary['issue_count']} |")
        lines.append(f"| &nbsp;&nbsp;其中：错误 | {summary['error_count']} |")
        lines.append(f"| &nbsp;&nbsp;其中：警告 | {summary['warning_count']} |")
        lines.append(f"| 修正建议数 | {summary['fix_count']} |")
        lines.append(f"| &nbsp;&nbsp;其中：已应用 | {summary['applied_fix_count']} |")
        lines.append(f"| &nbsp;&nbsp;其中：待应用 | {summary['unapplied_fix_count']} |")
        lines.append(f"| 不含税金额合计 | ¥{summary['total_amount']:,.2f} |")
        lines.append(f"| 税额合计 | ¥{summary['total_tax']:,.2f} |")
        lines.append(f"| 价税合计 | ¥{summary['grand_total']:,.2f} |")
        lines.append(f"| 撤销记录 | {'有' if summary['has_undo'] else '无'} |")
        lines.append("")

        if summary["issue_by_type"]:
            lines.append("### 问题类型分布")
            lines.append("")
            lines.append("| 问题类型 | 数量 |")
            lines.append("|----------|------|")
            for type_name, count in sorted(summary["issue_by_type"].items()):
                lines.append(f"| {_cn(type_name, _VALIDATION_TYPE_CN)} | {count} |")
            lines.append("")

        if batch.issues:
            lines.append("## 二、校验问题详情")
            lines.append("")
            for i, issue in enumerate(batch.issues, 1):
                severity_icon = "🔴" if issue.severity == Severity.ERROR else "🟡" if issue.severity == Severity.WARNING else "🔵"
                type_cn = _cn(issue.type.value, _VALIDATION_TYPE_CN)
                lines.append(f"### {i}. {severity_icon} {type_cn}")
                lines.append("")
                lines.append(f"- **问题级别**: {_cn(issue.severity.value, _SEVERITY_CN)}")
                if issue.invoice_no:
                    lines.append(f"- **{_cn('invoice_no', _FIELD_CN)}**: {issue.invoice_no}")
                if issue.row_index is not None:
                    lines.append(f"- **{_cn('row_index', _FIELD_CN)}**: 第 {issue.row_index} 行")
                lines.append(f"- **问题描述**: {issue.message}")
                if issue.details:
                    lines.append("- **详细信息**:")
                    for k, v in issue.details.items():
                        k_cn = _cn(k, _FIELD_CN)
                        if k_cn == k:
                            k_cn = _cn(k, {
                                "duplicate_rows": "重复行号",
                                "count": "重复次数",
                                "invalid_rate": "无效税率",
                                "valid_rates": "合法税率",
                                "computed_total": "计算合计",
                                "stated_total": "票面合计",
                                "difference": "差额",
                                "tolerance": "容差",
                                "computed_tax": "计算税额",
                                "stated_tax": "票面税额",
                                "error": "错误信息",
                                "position": "错误位置",
                                "missing": "缺失字段",
                                "available": "可用字段",
                            })
                        lines.append(f"  - {k_cn}: `{v}`")
                lines.append("")

        if batch.fixes:
            lines.append("## 三、修正记录")
            lines.append("")
            for i, fix in enumerate(batch.fixes, 1):
                status = "✅ 已应用" if fix.applied else "⏳ 待应用"
                lines.append(f"### {i}. {status} {fix.description}")
                lines.append("")
                lines.append(f"- **修正编号**: `{fix.id}`")
                lines.append(f"- **{_cn('invoice_no', _FIELD_CN)}**: {fix.invoice_no}")
                lines.append(f"- **修正字段**: `{_cn(fix.field, _FIELD_CN)}`")
                lines.append(f"- **修正前值**: `{fix.old_value}`")
                lines.append(f"- **修正后值**: `{fix.new_value}`")
                lines.append(f"- **修正原因**: {fix.reason}")
                if fix.applied_at:
                    lines.append(f"- **应用时间**: {fix.applied_at}")
                lines.append("")

        if batch.last_undo:
            lines.append("## 四、最近撤销记录")
            lines.append("")
            undo = batch.last_undo
            undone_at = undo.get("undone_at")
            if undone_at:
                lines.append(f"- **状态**: ✅ 已撤销")
                lines.append(f"- **撤销时间**: {undone_at}")
            else:
                lines.append(f"- **状态**: ⏳ 可撤销")
            lines.append(f"- **修正编号**: `{undo.get('fix_id', 'N/A')}`")
            lines.append(f"- **{_cn('invoice_no', _FIELD_CN)}**: {undo.get('invoice_no', 'N/A')}")
            lines.append(f"- **字段**: `{_cn(undo.get('field', ''), _FIELD_CN)}`")
            lines.append(f"- **恢复值**: `{undo.get('restored_value', 'N/A')}`")
            prev_val = undo.get("previous_value")
            if prev_val is not None:
                lines.append(f"- **撤销前值**: `{prev_val}`")
            lines.append("")

        lines.append("---")
        lines.append("*本报告由发票校验工具（invoice-validator）自动生成*")

        return "\n".join(lines)
