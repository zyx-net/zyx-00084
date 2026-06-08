import os
import sys
import json
import csv
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List

import click

from .config import ConfigManager, ConfigError
from .storage import StorageManager
from .importer import InvoiceImporter
from .validator import InvoiceValidator
from .exporter import ReportExporter
from .models import ExitCode, Severity, Batch, FixAction
from . import __version__


_EMOJI_FALLBACK = {
    "✅": "[OK]",
    "❌": "[ERROR]",
    "⚠️": "[WARN]",
    "💡": "[TIP]",
    "📦": "[BATCH]",
    "📄": "[FILE]",
    "📊": "[REPORT]",
    "⏳": "[PENDING]",
    "🔴": "[ERROR]",
    "🟡": "[WARN]",
    "🔵": "[INFO]",
    "↩️": "[UNDO]",
    "📝": "[NOTE]",
}

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U00002600-\U000027BF"
    "\U0001F100-\U0001F1FF"
    "]+",
    flags=re.UNICODE,
)


def _replace_emoji(text: str) -> str:
    def replace(match: re.Match) -> str:
        emoji = match.group(0)
        return _EMOJI_FALLBACK.get(emoji, f"[{emoji.encode('unicode-escape').decode('ascii')}]")
    return _EMOJI_PATTERN.sub(replace, text)


def safe_echo(message: str, err: bool = False) -> None:
    try:
        click.echo(message, err=err)
    except UnicodeEncodeError:
        safe_msg = _replace_emoji(message)
        try:
            click.echo(safe_msg, err=err)
        except UnicodeEncodeError:
            click.echo(safe_msg.encode("ascii", errors="replace").decode("ascii"), err=err)


def _setup_encoding() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, IOError):
            pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8:replace")


_setup_encoding()


class CLIContext:
    def __init__(self, workspace: str):
        self.workspace = Path(workspace).resolve()
        self.config_mgr = ConfigManager(str(self.workspace))
        self.storage_mgr = StorageManager(str(self.workspace))


pass_ctx = click.make_pass_decorator(CLIContext)


@click.group()
@click.version_option(__version__, "-v", "--version")
@click.option("--workspace", "-w", default=".", help="工作目录，默认为当前目录")
@click.pass_context
def cli(ctx: click.Context, workspace: str) -> None:
    """离线发票包校验 CLI - 用于检查供应商 CSV/JSON 发票包"""
    try:
        ctx.obj = CLIContext(workspace)
        if ctx.invoked_subcommand != "init":
            ctx.obj.config_mgr.load()
    except ConfigError as e:
        safe_echo(f"❌ {str(e)}", err=True)
        sys.exit(e.exit_code.value)
    except RuntimeError as e:
        safe_echo(f"❌ 初始化失败: {str(e)}", err=True)
        sys.exit(ExitCode.STORAGE_ERROR.value)


@cli.command("init")
@click.option("--force", "-f", is_flag=True, help="覆盖现有配置和样例数据")
@pass_ctx
def init_cmd(ctx: CLIContext, force: bool) -> None:
    """初始化工作区，创建配置和样例数据"""
    config_dir = ctx.workspace / ".invoice_validator"
    samples_dir = ctx.workspace / "samples"

    if config_dir.exists() and not force:
        safe_echo(f"错误: 工作区已初始化。使用 --force 覆盖现有数据。", err=True)
        sys.exit(ExitCode.STORAGE_ERROR.value)

    if force and config_dir.exists():
        import shutil
        shutil.rmtree(config_dir)

    try:
        config = ctx.config_mgr.load()
    except ConfigError as e:
        safe_echo(f"❌ {str(e)}", err=True)
        sys.exit(e.exit_code.value)
    ctx.config_mgr.save(config)

    samples_dir.mkdir(exist_ok=True)

    csv_sample = samples_dir / "invoices_sample.csv"
    with open(csv_sample, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "invoice_no", "amount", "tax_rate", "tax_amount",
            "total_amount", "date", "supplier", "buyer"
        ])
        writer.writerow(["INV001", 1000.00, 0.13, 130.00, 1130.00, "2024-01-15", "供应商A有限公司", "采购方公司"])
        writer.writerow(["INV002", 2000.00, 0.09, 180.00, 2180.00, "2024-01-16", "供应商B有限公司", "采购方公司"])
        writer.writerow(["INV002", 500.00, 0.06, 30.00, 530.00, "2024-01-17", "供应商C有限公司", "采购方公司"])
        writer.writerow(["INV003", 3000.00, 0.13, 390.00, 3400.00, "2024-01-18", "供应商A有限公司", "采购方公司"])
        writer.writerow(["INV004", 1500.00, 0.25, 375.00, 1875.00, "2024-01-19", "供应商D有限公司", "采购方公司"])
        writer.writerow(["INV005", 800.00, 0.06, 48.00, 850.00, "2024-01-20", "供应商E有限公司", "采购方公司"])

    json_sample = samples_dir / "invoices_sample.json"
    json_data = [
        {"invoice_no": "INV001", "amount": 1000.00, "tax_rate": 0.13, "tax_amount": 130.00, "total_amount": 1130.00, "date": "2024-01-15", "supplier": "供应商A有限公司", "buyer": "采购方公司"},
        {"invoice_no": "INV002", "amount": 2000.00, "tax_rate": 0.09, "tax_amount": 180.00, "total_amount": 2180.00, "date": "2024-01-16", "supplier": "供应商B有限公司", "buyer": "采购方公司"},
        {"invoice_no": "INV002", "amount": 500.00, "tax_rate": 0.06, "tax_amount": 30.00, "total_amount": 530.00, "date": "2024-01-17", "supplier": "供应商C有限公司", "buyer": "采购方公司"},
        {"invoice_no": "INV003", "amount": 3000.00, "tax_rate": 0.13, "tax_amount": 390.00, "total_amount": 3400.00, "date": "2024-01-18", "supplier": "供应商A有限公司", "buyer": "采购方公司"},
        {"invoice_no": "INV004", "amount": 1500.00, "tax_rate": 0.25, "tax_amount": 375.00, "total_amount": 1875.00, "date": "2024-01-19", "supplier": "供应商D有限公司", "buyer": "采购方公司"},
        {"invoice_no": "INV005", "amount": 800.00, "tax_rate": 0.06, "tax_amount": 48.00, "total_amount": 850.00, "date": "2024-01-20", "supplier": "供应商E有限公司", "buyer": "采购方公司"},
    ]
    with open(json_sample, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    corrupted_sample = samples_dir / "invoices_corrupted.json"
    with open(corrupted_sample, "w", encoding="utf-8") as f:
        f.write('[{"invoice_no": "INV001", "amount": 1000, this is invalid json}]')

    bad_csv_sample = samples_dir / "invoices_missing_cols.csv"
    with open(bad_csv_sample, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["invoice_no", "amount", "date", "supplier"])
        writer.writerow(["INV001", 1000.00, "2024-01-15", "供应商A有限公司"])

    readme = samples_dir / "README.txt"
    readme.write_text(
        "样例数据说明：\n"
        "- invoices_sample.csv: 包含重复票号(INV002)、金额异常(INV003)、非法税率(INV004)、税额容差(INV005)\n"
        "- invoices_sample.json: 同上，JSON 格式\n"
        "- invoices_corrupted.json: 损坏的 JSON 文件，用于测试错误处理\n"
        "- invoices_missing_cols.csv: 缺少必填列的 CSV 文件\n",
        encoding="utf-8"
    )

    safe_echo("✅ 工作区初始化完成")
    safe_echo(f"   配置文件: {ctx.workspace / '.invoice_validator' / 'config.json'}")
    safe_echo(f"   样例目录: {samples_dir}")
    sys.exit(ExitCode.SUCCESS.value)


@cli.command("import")
@click.argument("file_path", type=click.Path(exists=True, dir_okay=False))
@pass_ctx
def import_cmd(ctx: CLIContext, file_path: str) -> None:
    """导入一批发票数据（CSV 或 JSON）"""
    try:
        config = ctx.config_mgr.load()
    except ConfigError as e:
        safe_echo(f"❌ {str(e)}", err=True)
        sys.exit(e.exit_code.value)
    importer = InvoiceImporter(config)

    try:
        result = importer.import_file(file_path)
    except Exception as e:
        safe_echo(f"❌ 导入失败: {str(e)}", err=True)
        sys.exit(ExitCode.STORAGE_ERROR.value)

    file_type = Path(file_path).suffix.lower().lstrip(".")
    batch = ctx.storage_mgr.create_batch(file_path, file_type)
    batch.invoices = result.invoices
    batch.issues.extend(result.issues)
    ctx.storage_mgr.save_batch(batch)

    safe_echo(f"📦 批次 ID: {batch.batch_id}")
    safe_echo(f"📄 源文件: {file_path}")
    safe_echo(f"✅ 成功导入: {len(result.invoices)} 张发票")

    if result.issues:
        errors = [i for i in result.issues if i.severity == Severity.ERROR]
        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        safe_echo(f"⚠️  导入问题: {len(errors)} 错误, {len(warnings)} 警告")
        for issue in result.issues:
            icon = "🔴" if issue.severity == Severity.ERROR else "🟡"
            safe_echo(f"   {icon} {issue.message}")

    sys.exit(result.exit_code.value)


@cli.command("validate")
@click.option("--batch-id", "-b", default=None, help="批次 ID，默认为当前活动批次")
@pass_ctx
def validate_cmd(ctx: CLIContext, batch_id: Optional[str]) -> None:
    """校验发票数据：重复票号、非法税率、金额异常等"""
    try:
        batch = ctx.storage_mgr.load_batch(batch_id)
    except RuntimeError as e:
        safe_echo(f"❌ {str(e)}", err=True)
        sys.exit(ExitCode.BATCH_NOT_FOUND.value)

    if not batch.invoices:
        safe_echo("⚠️  批次中没有发票数据")
        sys.exit(ExitCode.SUCCESS.value)

    try:
        config = ctx.config_mgr.load()
    except ConfigError as e:
        safe_echo(f"❌ {str(e)}", err=True)
        sys.exit(e.exit_code.value)
    validator = InvoiceValidator(config)
    result = validator.validate(batch.invoices)

    batch.issues = [iss for iss in batch.issues if not any(
        iss.type == t for t in [
            "duplicate_invoice_no", "invalid_tax_rate",
            "amount_mismatch", "amount_tolerance"
        ]
    )]
    batch.issues.extend(result.issues)
    batch.fixes = result.fixes
    batch.validated = True
    batch.validated_at = datetime.now().isoformat()
    ctx.storage_mgr.save_batch(batch)

    safe_echo(f"📦 批次: {batch.batch_id}")
    safe_echo(f"✅ 校验完成: {len(batch.invoices)} 张发票")

    if result.issues:
        errors = [i for i in result.issues if i.severity == Severity.ERROR]
        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        safe_echo(f"⚠️  发现问题: {len(errors)} 错误, {len(warnings)} 警告")
        safe_echo(f"💡 建议修正: {len(result.fixes)} 条")
        safe_echo("")
        for i, issue in enumerate(result.issues, 1):
            icon = "🔴" if issue.severity == Severity.ERROR else "🟡"
            loc = f"[发票:{issue.invoice_no}]" if issue.invoice_no else (f"[行:{issue.row_index}]" if issue.row_index else "")
            safe_echo(f"{i:2d}. {icon} {issue.type.value:25s} {loc} {issue.message}")
    else:
        safe_echo("✅ 全部校验通过！")

    sys.exit(result.exit_code.value)


@cli.command("fix-plan")
@click.option("--batch-id", "-b", default=None, help="批次 ID")
@pass_ctx
def fix_plan_cmd(ctx: CLIContext, batch_id: Optional[str]) -> None:
    """查看当前待应用的修正草案"""
    try:
        batch = ctx.storage_mgr.load_batch(batch_id)
    except RuntimeError as e:
        safe_echo(f"❌ {str(e)}", err=True)
        sys.exit(ExitCode.BATCH_NOT_FOUND.value)

    pending_fixes = [f for f in batch.fixes if not f.applied]
    applied_fixes = [f for f in batch.fixes if f.applied]

    safe_echo(f"📦 批次: {batch.batch_id}")
    safe_echo(f"💡 修正草案汇总: 待应用 {len(pending_fixes)} 条, 已应用 {len(applied_fixes)} 条")
    safe_echo("")

    if not batch.fixes:
        safe_echo("⚠️  没有可用的修正草案，请先运行 validate 命令")
        sys.exit(ExitCode.NO_FIXES_TO_APPLY.value)

    if pending_fixes:
        safe_echo("⏳ 待应用的修正:")
        safe_echo("")
        for i, fix in enumerate(pending_fixes, 1):
            safe_echo(f"  {i:2d}. [{fix.id}] {fix.description}")
            safe_echo(f"       发票: {fix.invoice_no}, 字段: {fix.field}")
            safe_echo(f"       原值: {fix.old_value} → 新值: {fix.new_value}")
            safe_echo(f"       原因: {fix.reason}")
            safe_echo("")

    if applied_fixes:
        safe_echo("✅ 已应用的修正:")
        safe_echo("")
        for i, fix in enumerate(applied_fixes, 1):
            safe_echo(f"  {i:2d}. [{fix.id}] {fix.description} (应用于 {fix.applied_at})")

    sys.exit(ExitCode.SUCCESS.value)


@cli.command("apply")
@click.argument("fix_id")
@click.option("--batch-id", "-b", default=None, help="批次 ID")
@pass_ctx
def apply_cmd(ctx: CLIContext, fix_id: str, batch_id: Optional[str]) -> None:
    """应用一条修正草案"""
    try:
        batch = ctx.storage_mgr.load_batch(batch_id)
    except RuntimeError as e:
        safe_echo(f"❌ {str(e)}", err=True)
        sys.exit(ExitCode.BATCH_NOT_FOUND.value)

    fix = next((f for f in batch.fixes if f.id == fix_id), None)
    if not fix:
        safe_echo(f"❌ 未找到修正 ID: {fix_id}", err=True)
        sys.exit(ExitCode.INVALID_ARGUMENT.value)

    if fix.applied:
        safe_echo(f"⚠️  修正 {fix_id} 已经应用过了")
        sys.exit(ExitCode.SUCCESS.value)

    invoice = next((inv for inv in batch.invoices if inv.invoice_no == fix.invoice_no), None)
    if not invoice:
        safe_echo(f"❌ 未找到发票: {fix.invoice_no}", err=True)
        sys.exit(ExitCode.INVALID_ARGUMENT.value)

    old_value = getattr(invoice, fix.field)
    setattr(invoice, fix.field, fix.new_value)

    fix.applied = True
    fix.applied_at = datetime.now().isoformat()

    batch.last_undo = {
        "fix_id": fix.id,
        "invoice_no": fix.invoice_no,
        "field": fix.field,
        "restored_value": fix.old_value,
        "previous_value": old_value,
        "undone_at": None,
    }

    ctx.storage_mgr.save_batch(batch)

    safe_echo(f"✅ 已应用修正: {fix_id}")
    safe_echo(f"   发票: {fix.invoice_no}")
    safe_echo(f"   字段: {fix.field}")
    safe_echo(f"   原值: {old_value} → 新值: {fix.new_value}")
    safe_echo("")
    safe_echo("💡 可使用 undo 命令撤销此修正")

    sys.exit(ExitCode.SUCCESS.value)


@cli.command("undo")
@click.option("--batch-id", "-b", default=None, help="批次 ID")
@pass_ctx
def undo_cmd(ctx: CLIContext, batch_id: Optional[str]) -> None:
    """撤销最近一次应用的修正"""
    try:
        batch = ctx.storage_mgr.load_batch(batch_id)
    except RuntimeError as e:
        safe_echo(f"❌ {str(e)}", err=True)
        sys.exit(ExitCode.BATCH_NOT_FOUND.value)

    if not batch.last_undo or batch.last_undo.get("undone_at") is not None:
        safe_echo("❌ 没有可撤销的已应用修正。请先应用至少一条修正。", err=True)
        sys.exit(ExitCode.NO_APPLIED_FIX_TO_UNDO.value)

    undo_info = batch.last_undo
    fix_id = undo_info["fix_id"]
    invoice_no = undo_info["invoice_no"]
    field = undo_info["field"]
    restore_value = undo_info["restored_value"]

    invoice = next((inv for inv in batch.invoices if inv.invoice_no == invoice_no), None)
    if not invoice:
        safe_echo(f"❌ 未找到发票: {invoice_no}", err=True)
        sys.exit(ExitCode.INVALID_ARGUMENT.value)

    current_value = getattr(invoice, field)
    setattr(invoice, field, restore_value)

    fix = next((f for f in batch.fixes if f.id == fix_id), None)
    if fix:
        fix.applied = False
        fix.applied_at = None

    undo_info["undone_at"] = datetime.now().isoformat()
    undo_info["previous_value"] = current_value

    ctx.storage_mgr.save_batch(batch)

    safe_echo(f"↩️  已撤销修正: {fix_id}")
    safe_echo(f"   发票: {invoice_no}")
    safe_echo(f"   字段: {field}")
    safe_echo(f"   当前值: {current_value} → 恢复为: {restore_value}")

    sys.exit(ExitCode.SUCCESS.value)


@cli.command("export")
@click.option("--output", "-o", default="audit_report", help="输出文件名（不含扩展名）")
@click.option("--format", "-f", "fmt", default="markdown", type=click.Choice(["markdown", "json"]), help="输出格式")
@click.option("--batch-id", "-b", default=None, help="批次 ID")
@pass_ctx
def export_cmd(ctx: CLIContext, output: str, fmt: str, batch_id: Optional[str]) -> None:
    """导出审计报告（Markdown 或 JSON 格式）"""
    try:
        batch = ctx.storage_mgr.load_batch(batch_id)
    except RuntimeError as e:
        safe_echo(f"❌ {str(e)}", err=True)
        sys.exit(ExitCode.BATCH_NOT_FOUND.value)

    ext = ".md" if fmt == "markdown" else ".json"
    output_path = str(Path(output).with_suffix(ext))

    exporter = ReportExporter()
    try:
        result = exporter.export(batch, output_path, fmt)
    except ValueError as e:
        safe_echo(f"❌ {str(e)}", err=True)
        sys.exit(ExitCode.INVALID_ARGUMENT.value)
    except Exception as e:
        safe_echo(f"❌ 导出失败: {str(e)}", err=True)
        sys.exit(ExitCode.STORAGE_ERROR.value)

    summary = exporter._build_summary(batch)
    safe_echo(f"📦 批次: {batch.batch_id}")
    safe_echo(f"📊 报告汇总:")
    safe_echo(f"   发票数: {summary['invoice_count']}")
    safe_echo(f"   问题数: {summary['issue_count']} (错误:{summary['error_count']}, 警告:{summary['warning_count']})")
    safe_echo(f"   修正数: {summary['fix_count']} (已应用:{summary['applied_fix_count']})")
    safe_echo(f"   价税合计: ¥{summary['grand_total']:,.2f}")
    safe_echo("")
    safe_echo(f"✅ 报告已导出: {result.output_path}")

    sys.exit(ExitCode.SUCCESS.value)


@cli.command("list")
@pass_ctx
def list_cmd(ctx: CLIContext) -> None:
    """列出所有历史批次"""
    batches = ctx.storage_mgr.list_batches()

    if not batches:
        safe_echo("⚠️  没有找到历史批次，请先使用 import 命令导入发票")
        sys.exit(ExitCode.SUCCESS.value)

    current_id = ctx.storage_mgr.get_current_batch_id()

    safe_echo(f"共找到 {len(batches)} 个批次:")
    safe_echo("")
    for i, b in enumerate(batches, 1):
        marker = " ← 当前" if b["batch_id"] == current_id else ""
        status = "✓" if b["validated"] else "○"
        safe_echo(f"{i:2d}. {status} {b['batch_id']}{marker}")
        safe_echo(f"     创建: {b['created_at']}")
        safe_echo(f"     文件: {b['source_file']}")
        safe_echo(f"     发票: {b['invoice_count']} 张, 问题: {b['issue_count']} 个")
        safe_echo("")

    sys.exit(ExitCode.SUCCESS.value)


@cli.command("show")
@click.option("--batch-id", "-b", default=None, help="批次 ID")
@click.option("--issues", is_flag=True, help="只显示问题")
@click.option("--fixes", is_flag=True, help="只显示修正")
@pass_ctx
def show_cmd(ctx: CLIContext, batch_id: Optional[str], issues: bool, fixes: bool) -> None:
    """显示批次详情"""
    try:
        batch = ctx.storage_mgr.load_batch(batch_id)
    except RuntimeError as e:
        safe_echo(f"❌ {str(e)}", err=True)
        sys.exit(ExitCode.BATCH_NOT_FOUND.value)

    safe_echo(f"📦 批次: {batch.batch_id}")
    safe_echo(f"   创建时间: {batch.created_at}")
    safe_echo(f"   源文件: {batch.source_file}")
    safe_echo(f"   校验状态: {'✓ 已校验' if batch.validated else '○ 未校验'}")
    safe_echo(f"   发票数: {len(batch.invoices)}")
    safe_echo(f"   问题数: {len(batch.issues)}")
    safe_echo(f"   修正数: {len(batch.fixes)}")
    safe_echo("")

    if not fixes:
        if batch.invoices and not issues:
            safe_echo("📄 发票列表:")
            safe_echo("")
            for i, inv in enumerate(batch.invoices, 1):
                safe_echo(f"  {i:2d}. 发票号: {inv.invoice_no} | 金额: ¥{inv.amount:,.2f} | 税率: {inv.tax_rate*100:.0f}% | 合计: ¥{inv.total_amount:,.2f} | 日期: {inv.date}")
            safe_echo("")

        if batch.issues:
            safe_echo("⚠️  问题列表:")
            safe_echo("")
            for i, issue in enumerate(batch.issues, 1):
                icon = "🔴" if issue.severity == Severity.ERROR else "🟡" if issue.severity == Severity.WARNING else "🔵"
                safe_echo(f"  {i:2d}. {icon} {issue.type.value} | 发票: {issue.invoice_no or 'N/A'} | {issue.message}")
            safe_echo("")

    if not issues and batch.fixes:
        safe_echo("🔧 修正列表:")
        safe_echo("")
        for i, fix in enumerate(batch.fixes, 1):
            status = "✅" if fix.applied else "⏳"
            safe_echo(f"  {i:2d}. {status} [{fix.id}] {fix.description}")
            safe_echo(f"       发票: {fix.invoice_no} | 字段: {fix.field} | {fix.old_value} → {fix.new_value}")
        safe_echo("")

    if batch.last_undo:
        undo = batch.last_undo
        if undo.get("undone_at"):
            safe_echo(f"↩️  最近撤销: 修正 {undo.get('fix_id')} 于 {undo.get('undone_at')}")
        else:
            safe_echo(f"↩️  可撤销: 修正 {undo.get('fix_id')} (发票: {undo.get('invoice_no')})")

    sys.exit(ExitCode.SUCCESS.value)


if __name__ == "__main__":
    cli()
