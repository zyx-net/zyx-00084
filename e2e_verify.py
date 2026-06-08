#!/usr/bin/env python3
"""端到端真实命令验证脚本

注意：本脚本内置编码保护，可在 GBK/ASCII 终端下稳定运行。
"""

import json
import os
import re
import sys
import subprocess
import shutil
from pathlib import Path


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
TEST_DIR = WORKSPACE / "_e2e_test"
CLI = ["invoice-validator"]


def run(cmd, env=None, cwd=None):
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    full_env["PYTHONIOENCODING"] = "utf-8:replace"

    result = subprocess.run(
        cmd,
        cwd=str(cwd or TEST_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=full_env,
    )
    return result.returncode, result.stdout, result.stderr


def header(text):
    safe_print(f"\n{'='*60}")
    safe_print(f"=== {text} ===")
    safe_print(f"{'='*60}")


def main():
    safe_print("[START] 发票校验 CLI 端到端真实命令验证")

    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    TEST_DIR.mkdir()

    try:
        header("1. init 命令（ASCII 编码环境，模拟 GBK）")
        code, out, err = run([*CLI, "init", "--force"], env={"PYTHONIOENCODING": "ascii:replace"})
        safe_print(f"退出码: {code} {'[OK]' if code == 0 else '[FAIL]'}")
        safe_print(f"输出: {_replace_emoji(out.strip()[:200])}")
        assert code == 0, f"init 失败: {err}"

        header("2. import 发票")
        code, out, err = run([*CLI, "import", "samples/invoices_sample.csv"])
        safe_print(f"退出码: {code} {'[OK]' if code == 0 else '[FAIL]'}")
        safe_print(f"输出: {_replace_emoji(out.strip()[:150])}")
        assert code == 0, f"import 失败: {err}"

        header("3. validate 校验")
        code, out, err = run([*CLI, "validate"])
        safe_print(f"退出码: {code} {'[OK]' if code == 3 else '[FAIL]'} (期望 3)")
        for line in out.strip().split("\n")[:10]:
            safe_print(f"  {_replace_emoji(line)}")
        assert code == 3, f"validate 退出码错误: {code}"
        exit_normal = code

        header("4. fix-plan 查看修正")
        code, out, err = run([*CLI, "fix-plan"])
        safe_print(f"退出码: {code} {'[OK]' if code == 0 else '[FAIL]'}")
        match = re.search(r"\[fix_([a-f0-9]+)\]", out)
        assert match, f"未找到修正 ID: {_replace_emoji(out)}"
        fix_id = f"fix_{match.group(1)}"
        safe_print(f"修正 ID: {fix_id}")

        header("5. apply 应用修正")
        code, out, err = run([*CLI, "apply", fix_id])
        safe_print(f"退出码: {code} {'[OK]' if code == 0 else '[FAIL]'}")
        safe_print(f"输出: {_replace_emoji(out.strip())}")
        assert code == 0, f"apply 失败: {err}"

        header("6. undo 撤销修正")
        code, out, err = run([*CLI, "undo"])
        safe_print(f"退出码: {code} {'[OK]' if code == 0 else '[FAIL]'}")
        safe_print(f"输出: {_replace_emoji(out.strip())}")
        assert code == 0, f"undo 失败: {err}"

        header("7. 再次 undo（无修正可撤，期望退出码 4）")
        code, out, err = run([*CLI, "undo"])
        safe_print(f"退出码: {code} {'[OK]' if code == 4 else '[FAIL]'} (期望 4)")
        safe_print(f"错误: {_replace_emoji(err.strip())}")
        assert code == 4, f"undo 退出码错误: {code}"
        exit_undo = code

        header("8. export Markdown 报告")
        report_md = TEST_DIR / "audit_report.md"
        code, out, err = run([*CLI, "export", "-o", str(report_md.with_suffix("")), "-f", "markdown"])
        safe_print(f"退出码: {code} {'[OK]' if code == 0 else '[FAIL]'}")
        safe_print(f"输出: {_replace_emoji(out.strip())}")
        assert code == 0, f"export md 失败: {err}"

        header("9. Markdown 报告中文验证")
        content = report_md.read_text(encoding="utf-8")
        cn_keywords = [
            "# 发票校验审计报告",
            "## 一、汇总信息",
            "发票总张数",
            "不含税金额合计",
            "价税合计",
            "## 二、校验问题详情",
            "重复发票号",
            "非法税率",
            "金额不一致",
            "问题级别",
            "## 三、修正记录",
            "## 四、最近撤销记录",
        ]
        all_ok = True
        for kw in cn_keywords:
            found = kw in content
            all_ok = all_ok and found
            safe_print(f"  {'[OK]' if found else '[FAIL]'} 包含 '{kw}': {found}")
        assert all_ok, "Markdown 报告中文不完整"
        safe_print("\n报告前20行预览:")
        for i, line in enumerate(content.split("\n")[:20], 1):
            if line.strip():
                safe_print(f"  {i:2d}. {line}")

        header("10. export JSON 报告")
        report_json = TEST_DIR / "audit_report.json"
        code, out, err = run([*CLI, "export", "-o", str(report_json.with_suffix("")), "-f", "json"])
        safe_print(f"退出码: {code} {'[OK]' if code == 0 else '[FAIL]'}")
        assert code == 0, f"export json 失败: {err}"

        header("11. JSON 格式验证")
        data = json.loads(report_json.read_text(encoding="utf-8"))
        safe_print(f"  批次ID: {data['batch_id']}")
        safe_print(f"  发票数: {data['summary']['invoice_count']} (期望 6) {'[OK]' if data['summary']['invoice_count'] == 6 else '[FAIL]'}")
        safe_print(f"  问题数: {data['summary']['issue_count']} (期望 5) {'[OK]' if data['summary']['issue_count'] == 5 else '[FAIL]'}")
        safe_print(f"  价税合计: {data['summary']['grand_total']} (期望 9965.0) {'[OK]' if data['summary']['grand_total'] == 9965.0 else '[FAIL]'}")
        safe_print(f"  撤销记录: {data['summary']['has_undo']} (期望 True) {'[OK]' if data['summary']['has_undo'] else '[FAIL]'}")
        safe_print(f"  问题类型分布: {data['summary']['issue_by_type']}")
        assert data["summary"]["invoice_count"] == 6
        assert data["summary"]["issue_count"] == 5
        assert data["summary"]["grand_total"] == 9965.0
        assert data["summary"]["has_undo"] == True

        header("12. 写入非法税率配置（负数、字符串）")
        config_file = TEST_DIR / ".invoice_validator" / "config.json"
        config = json.loads(config_file.read_text(encoding="utf-8"))
        config["valid_tax_rates"] = [0.0, 0.06, -0.13, "0.09", 0.13]
        config_file.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        safe_print(f"valid_tax_rates = {config['valid_tax_rates']}")

        header("13. validate 非法配置错误（期望退出码 11）")
        code, out, err = run([*CLI, "validate"])
        safe_print(f"退出码: {code} {'[OK]' if code == 11 else '[FAIL]'} (期望 11)")
        safe_print(f"错误消息: {_replace_emoji(err.strip())}")
        assert code == 11, f"非法配置退出码错误: {code}"
        assert "配置错误" in err, "错误消息不包含'配置错误'"
        assert "负数" in err, "错误消息不包含'负数'"
        assert "字符串" in err, "错误消息不包含'字符串'"
        exit_bad_config = code

        header("14. 修正配置后重试")
        config["valid_tax_rates"] = [0.0, 0.06, 0.09, 0.13]
        config_file.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        code, out, err = run([*CLI, "validate"])
        safe_print(f"退出码: {code} {'[OK]' if code == 3 else '[FAIL]'} (期望 3)")
        assert code == 3, f"修正配置后校验失败: {code}"

        header("15. list 查看历史批次")
        run([*CLI, "import", "samples/invoices_sample.json"])
        code, out, err = run([*CLI, "list"])
        safe_print(f"退出码: {code} {'[OK]' if code == 0 else '[FAIL]'}")
        safe_print(_replace_emoji(out.strip()))
        assert code == 0, f"list 失败: {err}"
        assert "共找到 2 个批次" in out, "批次数量错误"

        header("16. show 读取历史批次")
        match = re.search(r"batch_\S+", out)
        assert match, f"未找到批次 ID: {_replace_emoji(out)}"
        batch_id = match.group(0)
        code, out, err = run([*CLI, "show", "-b", batch_id, "--issues"])
        safe_print(f"退出码: {code} {'[OK]' if code == 0 else '[FAIL]'}")
        for line in out.strip().split("\n")[:10]:
            safe_print(f"  {_replace_emoji(line)}")
        assert code == 0, f"show 失败: {err}"
        assert batch_id in out, "批次 ID 不匹配"

        header("17. 退出码汇总")
        safe_print(f"  正常校验: {exit_normal} (期望3) {'[OK]' if exit_normal == 3 else '[FAIL]'}")
        safe_print(f"  无修正撤销: {exit_undo} (期望4) {'[OK]' if exit_undo == 4 else '[FAIL]'}")
        safe_print(f"  非法配置: {exit_bad_config} (期望11) {'[OK]' if exit_bad_config == 11 else '[FAIL]'}")

        safe_print("\n" + "="*60)
        safe_print("[DONE] 所有端到端验证通过！")
        safe_print("="*60)
        safe_print("\n验证总结:")
        safe_print("  [OK] init 在 ASCII/GBK 编码下不崩溃（UnicodeEncodeError 已修复）")
        safe_print("  [OK] Markdown 报告包含完整中文标题、字段名、汇总正文")
        safe_print("  [OK] 非法税率配置输出明确错误和稳定退出码 11（TypeError 已修复）")
        safe_print("  [OK] JSON 导出格式正确，包含所有摘要信息")
        safe_print("  [OK] apply/undo 功能正常，撤销记录正确")
        safe_print("  [OK] 历史批次读取不退化")
        safe_print("  [OK] 退出码正确：3=非法税率, 4=无修正可撤, 11=配置错误")

    finally:
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR)
            safe_print(f"\n[BROOM] 清理测试目录: {TEST_DIR}")


if __name__ == "__main__":
    main()
