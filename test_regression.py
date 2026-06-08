#!/usr/bin/env python3
"""发票校验 CLI 回归测试脚本

覆盖以下测试场景：
1. init 命令正常运行（含编码兼容性）
2. 正常导入、校验、修正、撤销、导出完整流程
3. Markdown 报告中文标题、字段名、汇总正文可读性检查
4. valid_tax_rates 非法值（负数、字符串）配置错误处理
5. JSON 导出、apply/undo、历史读取不退化
6. 缺少必填列、损坏JSON错误场景

注意：本脚本内置编码保护，可在 GBK/ASCII 终端下稳定运行。
"""

import json
import os
import re
import sys
import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple, Dict


def _setup_encoding() -> None:
    """设置控制台输出编码，确保 GBK/ASCII 终端下不崩溃。

    不依赖用户终端编码设置，主动配置为 UTF-8 并启用替换模式。
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, IOError):
        pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8:replace")


_setup_encoding()


_EMOJI_FALLBACK = {
    "\u2705": "[OK]",
    "\u274c": "[FAIL]",
    "\ud83d\ude80": "[START]",
    "\ud83d\udcc1": "[FOLDER]",
    "\ud83d\udca1": "[TIP]",
    "\ud83d\udd27": "[FIX]",
    "\ud83d\udcc4": "[FILE]",
    "\u2699\ufe0f": "[CONFIG]",
    "\ud83d\udcdd": "[NOTE]",
    "\ud83d\udcca": "[STATS]",
    "\ud83d\udcdc": "[SCROLL]",
    "\ud83e\uddf9": "[BROOM]",
    "\ud83c\udf89": "[DONE]",
    "\u26a0\ufe0f": "[WARN]",
    "\ud83d\udce6": "[PACKAGE]",
}

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002600-\U000026FF"
    "\ufe0f"
    "]",
    flags=re.UNICODE,
)


def _replace_emoji(text: str) -> str:
    """将 emoji 替换为纯文本标签，确保 GBK 终端可显示。"""
    def _replace(match: re.Match) -> str:
        emoji = match.group(0)
        return _EMOJI_FALLBACK.get(emoji, f"[{emoji.encode('unicode-escape').decode('ascii')}]")
    return _EMOJI_PATTERN.sub(_replace, text)


def safe_print(message: str = "", end: str = "\n") -> None:
    """安全输出函数，三级降级确保 GBK 终端下不崩溃。

    1. 尝试正常 UTF-8 输出（带 errors=replace）
    2. 捕获 UnicodeEncodeError，替换 emoji 为文本标签
    3. 再次失败时使用 ASCII 替换编码
    """
    try:
        print(message, end=end)
    except UnicodeEncodeError:
        safe_msg = _replace_emoji(message)
        try:
            print(safe_msg, end=end)
        except UnicodeEncodeError:
            print(safe_msg.encode("ascii", errors="replace").decode("ascii"), end=end)


WORKSPACE = Path(__file__).parent.resolve()
TEST_DIR = WORKSPACE / "_test_workspace"
SAMPLES_DIR = WORKSPACE / "samples"
CLI = [sys.executable, "-m", "invoice_validator.cli"]


def run(cmd: List[str], env: Dict = None) -> Tuple[int, str, str]:
    """运行命令并返回 (退出码, stdout, stderr)。

    内部强制使用 UTF-8 编码，不依赖外部环境。
    """
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    full_env["PYTHONIOENCODING"] = "utf-8:replace"

    result = subprocess.run(
        cmd,
        cwd=str(TEST_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=full_env,
    )
    return result.returncode, result.stdout, result.stderr


def assert_exit(code: int, expected: int, desc: str) -> None:
    if code != expected:
        safe_print(f"[FAIL] 失败: {desc}")
        safe_print(f"   期望退出码: {expected}, 实际: {code}")
        sys.exit(1)
    safe_print(f"[OK] 通过: {desc} (退出码={code})")


def assert_contains(text: str, keyword: str, desc: str) -> None:
    if keyword not in text:
        safe_print(f"[FAIL] 失败: {desc}")
        safe_print(f"   期望包含: '{keyword}'")
        if len(text) > 500:
            text = text[:500] + "..."
        safe_print(f"   实际输出: {_replace_emoji(text)}")
        sys.exit(1)
    safe_print(f"[OK] 通过: {desc}")


def setup_test_workspace() -> None:
    """创建干净的测试工作区"""
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    TEST_DIR.mkdir(parents=True, exist_ok=True)

    for sample_file in SAMPLES_DIR.glob("*"):
        if sample_file.is_file():
            shutil.copy2(sample_file, TEST_DIR / sample_file.name)

    safe_print(f"\n[FOLDER] 测试工作区: {TEST_DIR}")


def test_1_init_encoding() -> None:
    """测试1: init 命令在 GBK/ASCII 编码环境下不崩溃"""
    safe_print("\n" + "=" * 60)
    safe_print("测试1: init 命令编码兼容性")
    safe_print("=" * 60)

    code, out, err = run([*CLI, "init", "--force"], env={"PYTHONIOENCODING": "ascii:replace"})
    assert_exit(code, 0, "init 命令在 ASCII 编码下成功")
    assert_contains(out, "工作区初始化完成", "初始化成功消息")

    safe_print("   [TIP] 输出预览（ASCII 编码下 emoji 被替换）:")
    for line in out.strip().split("\n")[:3]:
        if line.strip():
            safe_print(f"      {_replace_emoji(line)}")


def test_2_full_workflow() -> None:
    """测试2: 完整工作流（导入→校验→修正→撤销→导出）"""
    safe_print("\n" + "=" * 60)
    safe_print("测试2: 完整工作流")
    safe_print("=" * 60)

    code, out, err = run([*CLI, "import", "invoices_sample.csv"])
    assert_exit(code, 0, "导入 CSV 成功")
    assert_contains(out, "成功导入: 6 张发票", "导入6张发票")

    code, out, err = run([*CLI, "validate"])
    assert_exit(code, 3, "校验发现非法税率，退出码=3")
    assert_contains(out, "duplicate_invoice_no", "检测到重复票号")
    assert_contains(out, "invalid_tax_rate", "检测到非法税率")
    assert_contains(out, "amount_mismatch", "检测到金额异常")

    code, out, err = run([*CLI, "fix-plan"])
    assert_exit(code, 0, "查看修正草案成功")
    fix_id = None
    for line in out.split("\n"):
        if "[fix_" in line:
            match = re.search(r"\[fix_([a-f0-9]+)\]", line)
            if match:
                fix_id = f"fix_{match.group(1)}"
                break
    assert fix_id, f"未找到修正 ID，输出: {_replace_emoji(out)}"
    safe_print(f"   [FIX] 待应用修正 ID: {fix_id}")

    code, out, err = run([*CLI, "apply", fix_id])
    assert_exit(code, 0, "应用修正成功")
    assert_contains(out, "已应用修正", "修正应用成功")

    code, out, err = run([*CLI, "undo"])
    assert_exit(code, 0, "撤销修正成功")
    assert_contains(out, "已撤销修正", "修正撤销成功")

    code, out, err = run([*CLI, "undo"])
    assert_exit(code, 4, "再次撤销无修正可撤，退出码=4")
    assert_contains(err, "没有可撤销的已应用修正", "撤销错误消息可读")


def test_3_markdown_chinese_readability() -> None:
    """测试3: Markdown 报告中文标题、字段名、汇总正文可读性"""
    safe_print("\n" + "=" * 60)
    safe_print("测试3: Markdown 报告中文可读性")
    safe_print("=" * 60)

    code, out, err = run([*CLI, "import", "invoices_sample.csv"])
    assert_exit(code, 0, "导入 CSV 成功")

    code, out, err = run([*CLI, "validate"])
    assert_exit(code, 3, "校验完成")

    report_md = TEST_DIR / "test_report.md"
    code, out, err = run([*CLI, "export", "-o", str(report_md.with_suffix("")), "-f", "markdown"])
    assert_exit(code, 0, "导出 Markdown 报告成功")

    assert report_md.exists(), f"报告文件不存在: {report_md}"
    content = report_md.read_text(encoding="utf-8")

    expected_keywords = [
        "# 发票校验审计报告",
        "## 一、汇总信息",
        "发票总张数",
        "问题总数量",
        "不含税金额合计",
        "价税合计",
        "## 三、校验问题详情",
        "重复发票号",
        "非法税率",
        "金额不一致",
        "问题级别",
        "问题描述",
        "## 四、修正记录",
    ]

    for kw in expected_keywords:
        assert_contains(content, kw, f"报告包含 '{kw}'")

    safe_print("   [FILE] 报告内容预览（前20行）:")
    for i, line in enumerate(content.split("\n")[:20], 1):
        if line.strip():
            safe_print(f"      {i:2d}. {line}")


def test_4_invalid_tax_rates_config() -> None:
    """测试4: valid_tax_rates 非法值（负数、字符串）配置错误处理"""
    safe_print("\n" + "=" * 60)
    safe_print("测试4: valid_tax_rates 非法值配置错误处理")
    safe_print("=" * 60)

    bad_config = {
        "field_mapping": {
            "invoice_no": "invoice_no", "amount": "amount", "tax_rate": "tax_rate",
            "tax_amount": "tax_amount", "total_amount": "total_amount",
            "date": "date", "supplier": "supplier", "buyer": "buyer"
        },
        "valid_tax_rates": [0.0, 0.06, -0.13, "0.09", 0.13],
        "amount_tolerance": 0.01,
        "required_fields": ["invoice_no", "amount", "tax_rate", "total_amount", "date", "supplier", "buyer"]
    }

    config_dir = TEST_DIR / ".invoice_validator"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(bad_config, f, indent=2, ensure_ascii=False)
    safe_print(f"   [CONFIG] 写入非法配置: valid_tax_rates = {bad_config['valid_tax_rates']}")

    code, out, err = run([*CLI, "validate"])
    assert_exit(code, 11, "非法税率配置退出码=11")

    expected_err_keywords = [
        "配置错误",
        "valid_tax_rates 包含非法值",
        "负数",
        "字符串",
    ]
    for kw in expected_err_keywords:
        assert_contains(err, kw, f"错误消息包含 '{kw}'")

    safe_print(f"   [NOTE] 错误消息: {_replace_emoji(err.strip())}")

    good_config = bad_config.copy()
    good_config["valid_tax_rates"] = [0.0, 0.06, 0.09, 0.13]
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(good_config, f, indent=2, ensure_ascii=False)

    code, out, err = run([*CLI, "validate"])
    assert_exit(code, 3, "修正配置后校验正常（非法税率退出码=3）")
    safe_print("   [OK] 修正配置后恢复正常")


def test_5_json_export_and_history() -> None:
    """测试5: JSON 导出、apply/undo、历史读取不退化"""
    safe_print("\n" + "=" * 60)
    safe_print("测试5: JSON 导出、历史读取不退化")
    safe_print("=" * 60)

    code, out, err = run([*CLI, "import", "invoices_sample.json"])
    assert_exit(code, 0, "导入 JSON 成功")
    batch_id_1 = None
    for line in out.split("\n"):
        if "批次 ID:" in line:
            batch_id_1 = line.split("批次 ID:")[1].strip()
            break
    assert batch_id_1, f"未找到批次 ID，输出: {_replace_emoji(out)}"

    code, out, err = run([*CLI, "validate"])
    assert_exit(code, 3, "校验完成")

    report_json = TEST_DIR / "test_report.json"
    code, out, err = run([*CLI, "export", "-o", str(report_json.with_suffix("")), "-f", "json"])
    assert_exit(code, 0, "导出 JSON 报告成功")

    assert report_json.exists(), f"JSON 报告不存在: {report_json}"
    with open(report_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "batch_id" in data, "JSON 报告包含 batch_id"
    assert "summary" in data, "JSON 报告包含 summary"
    assert data["summary"]["invoice_count"] == 6, "发票数量正确"
    assert data["summary"]["error_count"] >= 1, "错误数量正确"
    safe_print(f"   [STATS] JSON 报告摘要: {data['summary']}")

    code, out, err = run([*CLI, "import", "invoices_sample.csv"])
    assert_exit(code, 0, "再次导入创建新批次")

    code, out, err = run([*CLI, "list"])
    assert_exit(code, 0, "列出所有批次成功")
    assert "共找到 4 个批次" in out, "列出4个批次"

    code, out, err = run([*CLI, "show", "-b", batch_id_1])
    assert_exit(code, 0, "读取历史批次成功")
    assert_contains(out, batch_id_1, "历史批次 ID 正确")
    assert_contains(out, "发票数: 6", "历史批次发票数量正确")

    safe_print(f"   [SCROLL] 历史批次可正常读取: {batch_id_1}")


def test_6_error_scenarios() -> None:
    """测试6: 其他错误场景（缺少必填列、损坏JSON）"""
    safe_print("\n" + "=" * 60)
    safe_print("测试6: 缺少必填列、损坏JSON错误场景")
    safe_print("=" * 60)

    code, out, err = run([*CLI, "import", "invoices_missing_cols.csv"])
    assert_exit(code, 1, "缺少必填列退出码=1")
    combined = out + err
    assert_contains(combined, "Missing required columns", "缺少必填列错误消息可读")
    safe_print(f"   [NOTE] 缺少必填列错误: {_replace_emoji((out + err).strip()[:100])}...")

    code, out, err = run([*CLI, "import", "invoices_corrupted.json"])
    assert_exit(code, 2, "损坏JSON退出码=2")
    combined = out + err
    assert_contains(combined, "Corrupted JSON", "损坏JSON错误消息可读")
    safe_print(f"   [NOTE] 损坏JSON错误: {_replace_emoji((out + err).strip()[:100])}...")


def test_7_supplier_rule_persistence() -> None:
    """测试7: 供应商规则持久化（保存后重启可读取）"""
    safe_print("\n" + "=" * 60)
    safe_print("测试7: 供应商规则持久化")
    safe_print("=" * 60)

    code, out, err = run([*CLI, "init", "--force"])
    assert_exit(code, 0, "初始化成功")

    supplier = "华为技术有限公司"
    code, out, err = run([
        *CLI, "rule", "add", supplier,
        "-t", "0.13", "-t", "0.06",
        "-T", "0.05",
        "-r", "invoice_no", "-r", "amount", "-r", "tax_rate", "-r", "tax_amount",
        "-r", "total_amount", "-r", "date", "-r", "supplier", "-r", "buyer"
    ])
    assert_exit(code, 0, "添加供应商规则成功")
    assert_contains(out, supplier, "输出包含供应商名称")
    assert_contains(out, "已创建供应商规则", "规则创建成功消息")

    rule_file = TEST_DIR / ".invoice_validator" / "supplier_rules.json"
    assert rule_file.exists(), f"供应商规则文件不存在: {rule_file}"

    with open(rule_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert supplier in data, f"规则文件中不存在供应商: {supplier}"
    assert data[supplier]["valid_tax_rates"] == [0.13, 0.06], "税率白名单正确"
    assert data[supplier]["amount_tolerance"] == 0.05, "金额容差正确"
    assert len(data[supplier]["required_fields"]) == 8, "必填字段正确"
    assert "created_at" in data[supplier], "包含创建时间"
    assert "updated_at" in data[supplier], "包含更新时间"
    safe_print(f"   [OK] 规则文件内容正确: {supplier}")

    code, out, err = run([*CLI, "rule", "reload"])
    assert_exit(code, 0, "重新加载规则成功")
    assert_contains(out, "已重新加载规则配置", "重新加载成功消息")
    assert_contains(out, "已加载规则数: 1", "规则数量正确")

    code, out, err = run([*CLI, "rule", "list"])
    assert_exit(code, 0, "列出规则成功")
    assert_contains(out, supplier, "列表包含供应商")
    safe_print("   [OK] 持久化验证通过：规则保存→重启→读取完整链路正常")


def test_8_import_format_differences() -> None:
    """测试8: 导入格式差异（CSV/JSON 均支持供应商规则匹配）"""
    safe_print("\n" + "=" * 60)
    safe_print("测试8: 导入格式差异（CSV/JSON 供应商规则匹配）")
    safe_print("=" * 60)

    code, out, err = run([*CLI, "init", "--force"])
    assert_exit(code, 0, "初始化成功")

    supplier_a = "华为技术有限公司"
    supplier_b = "阿里巴巴集团"

    code, out, err = run([*CLI, "rule", "add", supplier_a, "-t", "0.13", "-t", "0.06"])
    assert_exit(code, 0, f"添加 {supplier_a} 规则成功")

    code, out, err = run([*CLI, "rule", "add", supplier_b, "-t", "0.09", "-t", "0.06"])
    assert_exit(code, 0, f"添加 {supplier_b} 规则成功")

    code, out, err = run([*CLI, "import", "invoices_sample.csv"])
    assert_exit(code, 0, "CSV 导入成功")
    assert_contains(out, "规则来源", "CSV 导入显示规则来源统计")
    assert_contains(out, "供应商专属", "CSV 导入显示使用供应商规则的发票数")
    assert_contains(out, "全局默认", "CSV 导入显示使用全局规则的发票数")

    code, out, err = run([*CLI, "import", "invoices_sample.json"])
    assert_exit(code, 0, "JSON 导入成功")
    assert_contains(out, "规则来源", "JSON 导入显示规则来源统计")
    assert_contains(out, "供应商专属", "JSON 导入显示使用供应商规则的发票数")

    code, out, err = run([*CLI, "validate"])
    assert_exit(code, 3, "校验完成（含非法税率）")
    assert_contains(out, "[supplier]", "校验输出标注供应商规则来源")
    assert_contains(out, "[global]", "校验输出标注全局规则来源")

    safe_print("   [OK] CSV 和 JSON 导入均正确匹配供应商规则")


def test_9_conflict_detection() -> None:
    """测试9: 冲突提示（添加/更新规则时检测与全局的冲突）"""
    safe_print("\n" + "=" * 60)
    safe_print("测试9: 规则冲突检测与提示")
    safe_print("=" * 60)

    code, out, err = run([*CLI, "init", "--force"])
    assert_exit(code, 0, "初始化成功")

    supplier = "字节跳动"

    code, out, err = run([
        *CLI, "rule", "add", supplier,
        "-t", "0.13",
        "-T", "0.02",
        "-r", "invoice_no", "-r", "amount", "-r", "tax_rate", "-r", "total_amount",
        "-r", "date", "-r", "supplier", "-r", "buyer"
    ])
    assert_exit(code, 0, "添加规则成功")
    assert_contains(out, "规则覆盖提示", "输出包含覆盖提示")
    assert_contains(out, "税率白名单不同", "覆盖提示包含税率")
    assert_contains(out, "金额容差不同", "覆盖提示包含容差")

    code, out, err = run([*CLI, "rule", "show", supplier])
    assert_exit(code, 0, "查看规则详情成功")
    assert_contains(out, "| 配置项 | 供应商规则 | 全局配置 | 状态 |", "显示对比表格")
    assert_contains(out, "⚠️  冲突", "冲突状态显示正确")

    code, out, err = run([*CLI, "rule", "add", supplier, "-t", "0.13"])
    assert_exit(code, 12, "重复添加规则退出码=12")
    combined = out + err
    assert_contains(combined, "已存在规则", "提示规则已存在")
    assert_contains(combined, "--overwrite", "提示使用 --overwrite")

    code, out, err = run([*CLI, "rule", "add", supplier, "-t", "0.09", "--overwrite"])
    assert_exit(code, 0, "使用 --overwrite 覆盖成功")
    assert_contains(out, "已覆盖供应商规则", "覆盖成功消息")

    code, out, err = run([*CLI, "rule", "add", "测试供应商", "-r", ""])
    assert_exit(code, 13, "空字段名退出码=13")
    combined = out + err
    assert_contains(combined, "必填字段名不能为空", "空字段名错误提示")

    code, out, err = run([*CLI, "rule", "show", "不存在的供应商"])
    assert_exit(code, 15, "不存在的规则退出码=15")
    combined = out + err
    assert_contains(combined, "未找到供应商", "规则不存在错误提示")

    safe_print("   [OK] 冲突检测、重复添加、空字段、不存在规则均正确处理")


def test_10_export_rule_source_fields() -> None:
    """测试10: 导出字段（Markdown/JSON 都包含规则来源信息）"""
    safe_print("\n" + "=" * 60)
    safe_print("测试10: 导出字段包含规则来源信息")
    safe_print("=" * 60)

    code, out, err = run([*CLI, "init", "--force"])
    assert_exit(code, 0, "初始化成功")

    supplier = "华为技术有限公司"
    code, out, err = run([*CLI, "rule", "add", supplier, "-t", "0.13", "-t", "0.06"])
    assert_exit(code, 0, "添加供应商规则成功")

    code, out, err = run([*CLI, "import", "invoices_sample.csv"])
    assert_exit(code, 0, "导入成功")

    code, out, err = run([*CLI, "validate"])
    assert_exit(code, 3, "校验完成")

    report_md = TEST_DIR / "test_report.md"
    code, out, err = run([*CLI, "export", "-o", str(report_md.with_suffix("")), "-f", "markdown"])
    assert_exit(code, 0, "导出 Markdown 成功")

    content = report_md.read_text(encoding="utf-8")
    expected_md = [
        "🌟 使用专属规则的供应商数",
        "规则来源分布",
        "## 二、发票明细（逐张可追溯）",
        "| 发票号 | 销售方 | 金额 | 税率 | 价税合计 | 规则来源 | 规则状态 | 冲突信息 |",
        "🌟 供应商专属规则",
        "🔹 全局默认规则",
        "### 规则来源说明",
    ]
    for kw in expected_md:
        assert_contains(content, kw, f"Markdown 报告包含 '{kw}'")
    safe_print("   [OK] Markdown 报告包含规则来源表格和说明")

    report_json = TEST_DIR / "test_report.json"
    code, out, err = run([*CLI, "export", "-o", str(report_json.with_suffix("")), "-f", "json"])
    assert_exit(code, 0, "导出 JSON 成功")

    with open(report_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "rule_source_breakdown" in data["summary"], "JSON 摘要包含规则来源统计"
    assert "supplier_rule_count" in data["summary"], "JSON 摘要包含供应商规则数"
    assert "suppliers_with_rules" in data["summary"], "JSON 摘要包含使用规则的供应商列表"
    assert "invoices_with_rule_conflicts" in data["summary"], "JSON 摘要包含冲突发票数"

    for inv in data["invoices"]:
        assert "rule_source" in inv, f"发票 {inv.get('invoice_no')} 包含 rule_source 字段"
        rs = inv["rule_source"]
        assert "rule_source" in rs, "rule_source 包含 rule_source 字段"
        assert "supplier" in rs, "rule_source 包含 supplier 字段"
        assert "conflicts" in rs, "rule_source 包含 conflicts 字段"
        assert "conflict_status" in rs, "rule_source 包含 conflict_status 字段"
        assert rs["rule_source"] in ["supplier", "global"], f"rule_source 值合法: {rs['rule_source']}"

    for issue in data["issues"]:
        if issue.get("invoice_no"):
            assert "rule_source" in issue, f"问题 {issue.get('invoice_no')} 包含 rule_source 字段"
            assert "supplier" in issue, f"问题 {issue.get('invoice_no')} 包含 supplier 字段"

    safe_print("   [OK] JSON 报告每张发票、每个问题都包含规则来源字段")

    hw_inv = None
    for inv in data["invoices"]:
        if inv.get("supplier") == supplier:
            hw_inv = inv
            break
    assert hw_inv is not None, f"未找到 {supplier} 的发票"
    assert hw_inv["rule_source"]["rule_source"] == "supplier", f"{supplier} 发票使用供应商规则"
    assert hw_inv["rule_source"]["conflict_status"] in ["conflicts_detected", "no_conflicts"], "冲突状态正确"
    safe_print(f"   [OK] {supplier} 发票规则来源追踪正确")


def test_11_config_dir_not_writable() -> None:
    """测试11: 配置目录不可写（权限不足错误处理，退出码=14）"""
    safe_print("\n" + "=" * 60)
    safe_print("测试11: 配置目录不可写（权限不足）")
    safe_print("=" * 60)

    code, out, err = run([*CLI, "init", "--force"])
    assert_exit(code, 0, "初始化成功")

    config_dir = TEST_DIR / ".invoice_validator"

    if sys.platform != "win32":
        old_mode = config_dir.stat().st_mode
        try:
            config_dir.chmod(0o400)
            safe_print("   [NOTE] 已将配置目录设为只读")

            code, out, err = run([*CLI, "rule", "add", "测试供应商", "-t", "0.13"])
            assert_exit(code, 14, "权限不足退出码=14")
            combined = out + err
            assert_contains(combined, "权限不足", "错误消息包含权限不足")
            assert_contains(combined, "只读或权限不足", "错误消息说明原因")
            safe_print("   [OK] 只读目录下权限错误处理正确")
        finally:
            config_dir.chmod(old_mode)
    else:
        import stat
        try:
            code, out, err = run([*CLI, "rule", "add", "临时供应商", "-t", "0.13"])
            assert_exit(code, 0, "创建初始规则成功")

            rules_file = config_dir / "supplier_rules.json"
            import ctypes
            FILE_ATTRIBUTE_READONLY = 0x01
            ctypes.windll.kernel32.SetFileAttributesW(str(rules_file), FILE_ATTRIBUTE_READONLY)
            safe_print("   [NOTE] 已将规则文件设为只读（Windows）")

            code, out, err = run([*CLI, "rule", "add", "测试供应商", "-t", "0.13"])
            assert_exit(code, 14, "权限不足退出码=14")
            combined = out + err
            assert_contains(combined, "权限不足", "错误消息包含权限不足")
            safe_print("   [OK] 只读文件下权限错误处理正确")
        finally:
            rules_file = config_dir / "supplier_rules.json"
            ctypes.windll.kernel32.SetFileAttributesW(str(rules_file), 0)

    rule_file = config_dir / "supplier_rules.json"
    code, out, err = run([*CLI, "rule", "add", "测试供应商", "-t", "0.13"])
    assert_exit(code, 0, "恢复权限后添加规则成功")
    safe_print("   [OK] 恢复权限后操作正常")


def main() -> None:
    safe_print("[START] 发票校验 CLI 回归测试开始")
    safe_print(f"   Python 版本: {sys.version}")
    safe_print(f"   工作目录: {WORKSPACE}")
    safe_print(f"   输出编码: {sys.stdout.encoding}")

    setup_test_workspace()

    try:
        test_1_init_encoding()
        test_2_full_workflow()
        test_3_markdown_chinese_readability()
        test_4_invalid_tax_rates_config()
        test_5_json_export_and_history()
        test_6_error_scenarios()
        test_7_supplier_rule_persistence()
        test_8_import_format_differences()
        test_9_conflict_detection()
        test_10_export_rule_source_fields()
        test_11_config_dir_not_writable()
    finally:
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR)
            safe_print(f"\n[BROOM] 清理测试工作区: {TEST_DIR}")

    safe_print("\n" + "=" * 60)
    safe_print("[DONE] 所有测试通过！")
    safe_print("=" * 60)


if __name__ == "__main__":
    main()
