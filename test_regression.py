#!/usr/bin/env python3
"""发票校验 CLI 回归测试脚本

覆盖以下测试场景：
1. init 命令正常运行（含编码兼容性）
2. 正常导入、校验、修正、撤销、导出完整流程
3. Markdown 报告中文可读性检查
4. valid_tax_rates 非法值（负数、字符串）配置错误处理
5. JSON 导出、apply/undo、历史读取不退化
"""

import json
import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple, Dict


WORKSPACE = Path(__file__).parent.resolve()
TEST_DIR = WORKSPACE / "_test_workspace"
SAMPLES_DIR = WORKSPACE / "samples"
CLI = [sys.executable, "-m", "invoice_validator.cli"]


def run(cmd: List[str], check: bool = False, env: Dict = None) -> Tuple[int, str, str]:
    """运行命令并返回 (退出码, stdout, stderr)"""
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
        print(f"❌ 失败: {desc}")
        print(f"   期望退出码: {expected}, 实际: {code}")
        sys.exit(1)
    print(f"✅ 通过: {desc} (退出码={code})")


def assert_contains(text: str, keyword: str, desc: str) -> None:
    if keyword not in text:
        print(f"❌ 失败: {desc}")
        print(f"   期望包含: '{keyword}'")
        if len(text) > 500:
            text = text[:500] + "..."
        print(f"   实际输出: {text}")
        sys.exit(1)
    print(f"✅ 通过: {desc}")


def setup_test_workspace() -> None:
    """创建干净的测试工作区"""
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    TEST_DIR.mkdir(parents=True, exist_ok=True)

    for sample_file in SAMPLES_DIR.glob("*"):
        if sample_file.is_file():
            shutil.copy2(sample_file, TEST_DIR / sample_file.name)

    print(f"\n📁 测试工作区: {TEST_DIR}")


def test_1_init_encoding() -> None:
    """测试1: init 命令在 GBK/ASCII 编码环境下不崩溃"""
    print("\n" + "=" * 60)
    print("测试1: init 命令编码兼容性")
    print("=" * 60)

    code, out, err = run([*CLI, "init", "--force"], env={"PYTHONIOENCODING": "ascii:replace"})
    assert_exit(code, 0, "init 命令在 ASCII 编码下成功")
    assert_contains(out, "工作区初始化完成", "初始化成功消息")

    print("   💡 输出预览（ASCII 编码下 emoji 被替换）:")
    for line in out.strip().split("\n")[:3]:
        if line.strip():
            print(f"      {line}")


def test_2_full_workflow() -> None:
    """测试2: 完整工作流（导入→校验→修正→撤销→导出）"""
    print("\n" + "=" * 60)
    print("测试2: 完整工作流")
    print("=" * 60)

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
            import re
            match = re.search(r"\[fix_([a-f0-9]+)\]", line)
            if match:
                fix_id = f"fix_{match.group(1)}"
                break
    assert fix_id, f"未找到修正 ID，输出: {out}"
    print(f"   🔧 待应用修正 ID: {fix_id}")

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
    print("\n" + "=" * 60)
    print("测试3: Markdown 报告中文可读性")
    print("=" * 60)

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
        "## 二、校验问题详情",
        "重复发票号",
        "非法税率",
        "金额不一致",
        "问题级别",
        "问题描述",
        "## 三、修正记录",
    ]

    for kw in expected_keywords:
        assert_contains(content, kw, f"报告包含 '{kw}'")

    print("   📄 报告内容预览（前20行）:")
    for i, line in enumerate(content.split("\n")[:20], 1):
        if line.strip():
            print(f"      {i:2d}. {line}")


def test_4_invalid_tax_rates_config() -> None:
    """测试4: valid_tax_rates 非法值配置错误处理"""
    print("\n" + "=" * 60)
    print("测试4: valid_tax_rates 非法值配置错误处理")
    print("=" * 60)

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
    print(f"   ⚙️  写入非法配置: valid_tax_rates = {bad_config['valid_tax_rates']}")

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

    print(f"   📝 错误消息: {err.strip()}")

    good_config = bad_config.copy()
    good_config["valid_tax_rates"] = [0.0, 0.06, 0.09, 0.13]
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(good_config, f, indent=2, ensure_ascii=False)

    code, out, err = run([*CLI, "validate"])
    assert_exit(code, 3, "修正配置后校验正常（非法税率退出码=3）")
    print("   ✅ 修正配置后恢复正常")


def test_5_json_export_and_history() -> None:
    """测试5: JSON 导出、历史读取不退化"""
    print("\n" + "=" * 60)
    print("测试5: JSON 导出、历史读取不退化")
    print("=" * 60)

    code, out, err = run([*CLI, "import", "invoices_sample.json"])
    assert_exit(code, 0, "导入 JSON 成功")
    batch_id_1 = None
    for line in out.split("\n"):
        if "批次 ID:" in line:
            batch_id_1 = line.split("批次 ID:")[1].strip()
            break
    assert batch_id_1, f"未找到批次 ID，输出: {out}"

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
    print(f"   📊 JSON 报告摘要: {data['summary']}")

    code, out, err = run([*CLI, "import", "invoices_sample.csv"])
    assert_exit(code, 0, "再次导入创建新批次")

    code, out, err = run([*CLI, "list"])
    assert_exit(code, 0, "列出所有批次成功")
    assert "共找到 4 个批次" in out, "列出4个批次"

    code, out, err = run([*CLI, "show", "-b", batch_id_1])
    assert_exit(code, 0, "读取历史批次成功")
    assert_contains(out, batch_id_1, "历史批次 ID 正确")
    assert_contains(out, "发票数: 6", "历史批次发票数量正确")

    print(f"   📜 历史批次可正常读取: {batch_id_1}")


def test_6_error_scenarios() -> None:
    """测试6: 其他错误场景（缺少必填列、损坏JSON）"""
    print("\n" + "=" * 60)
    print("测试6: 缺少必填列、损坏JSON错误场景")
    print("=" * 60)

    code, out, err = run([*CLI, "import", "invoices_missing_cols.csv"])
    assert_exit(code, 1, "缺少必填列退出码=1")
    combined = out + err
    assert_contains(combined, "Missing required columns", "缺少必填列错误消息可读")
    print(f"   📝 缺少必填列错误: {(out + err).strip()[:100]}...")

    code, out, err = run([*CLI, "import", "invoices_corrupted.json"])
    assert_exit(code, 2, "损坏JSON退出码=2")
    combined = out + err
    assert_contains(combined, "Corrupted JSON", "损坏JSON错误消息可读")
    print(f"   📝 损坏JSON错误: {(out + err).strip()[:100]}...")


def main() -> None:
    print("🚀 发票校验 CLI 回归测试开始")
    print(f"   Python 版本: {sys.version}")
    print(f"   工作目录: {WORKSPACE}")

    setup_test_workspace()

    try:
        test_1_init_encoding()
        test_2_full_workflow()
        test_3_markdown_chinese_readability()
        test_4_invalid_tax_rates_config()
        test_5_json_export_and_history()
        test_6_error_scenarios()
    finally:
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR)
            print(f"\n🧹 清理测试工作区: {TEST_DIR}")

    print("\n" + "=" * 60)
    print("🎉 所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()
