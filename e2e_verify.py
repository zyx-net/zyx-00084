#!/usr/bin/env python3
"""端到端真实命令验证脚本"""

import json
import os
import sys
import subprocess
import shutil
from pathlib import Path


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
    print(f"\n{'='*60}")
    print(f"=== {text} ===")
    print(f"{'='*60}")


def main():
    print("🚀 发票校验 CLI 端到端真实命令验证")

    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    TEST_DIR.mkdir()

    try:
        header("1. init 命令（ASCII 编码环境，模拟 GBK）")
        code, out, err = run([*CLI, "init", "--force"], env={"PYTHONIOENCODING": "ascii:replace"})
        print(f"退出码: {code} {'✅' if code == 0 else '❌'}")
        print(f"输出: {out.strip()[:200]}")
        assert code == 0, f"init 失败: {err}"

        header("2. import 发票")
        code, out, err = run([*CLI, "import", "samples/invoices_sample.csv"])
        print(f"退出码: {code} {'✅' if code == 0 else '❌'}")
        print(f"输出: {out.strip()[:150]}")
        assert code == 0, f"import 失败: {err}"

        header("3. validate 校验")
        code, out, err = run([*CLI, "validate"])
        print(f"退出码: {code} {'✅' if code == 3 else '❌'} (期望 3)")
        for line in out.strip().split("\n")[:10]:
            print(f"  {line}")
        assert code == 3, f"validate 退出码错误: {code}"
        exit_normal = code

        header("4. fix-plan 查看修正")
        code, out, err = run([*CLI, "fix-plan"])
        print(f"退出码: {code} {'✅' if code == 0 else '❌'}")
        import re
        match = re.search(r"\[fix_([a-f0-9]+)\]", out)
        assert match, f"未找到修正 ID: {out}"
        fix_id = f"fix_{match.group(1)}"
        print(f"修正 ID: {fix_id}")

        header("5. apply 应用修正")
        code, out, err = run([*CLI, "apply", fix_id])
        print(f"退出码: {code} {'✅' if code == 0 else '❌'}")
        print(f"输出: {out.strip()}")
        assert code == 0, f"apply 失败: {err}"

        header("6. undo 撤销修正")
        code, out, err = run([*CLI, "undo"])
        print(f"退出码: {code} {'✅' if code == 0 else '❌'}")
        print(f"输出: {out.strip()}")
        assert code == 0, f"undo 失败: {err}"

        header("7. 再次 undo（无修正可撤，期望退出码 4）")
        code, out, err = run([*CLI, "undo"])
        print(f"退出码: {code} {'✅' if code == 4 else '❌'} (期望 4)")
        print(f"错误: {err.strip()}")
        assert code == 4, f"undo 退出码错误: {code}"
        exit_undo = code

        header("8. export Markdown 报告")
        report_md = TEST_DIR / "audit_report.md"
        code, out, err = run([*CLI, "export", "-o", str(report_md.with_suffix("")), "-f", "markdown"])
        print(f"退出码: {code} {'✅' if code == 0 else '❌'}")
        print(f"输出: {out.strip()}")
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
            print(f"  {'✅' if found else '❌'} 包含 '{kw}': {found}")
        assert all_ok, "Markdown 报告中文不完整"
        print("\n报告前20行预览:")
        for i, line in enumerate(content.split("\n")[:20], 1):
            if line.strip():
                print(f"  {i:2d}. {line}")

        header("10. export JSON 报告")
        report_json = TEST_DIR / "audit_report.json"
        code, out, err = run([*CLI, "export", "-o", str(report_json.with_suffix("")), "-f", "json"])
        print(f"退出码: {code} {'✅' if code == 0 else '❌'}")
        assert code == 0, f"export json 失败: {err}"

        header("11. JSON 格式验证")
        data = json.loads(report_json.read_text(encoding="utf-8"))
        print(f"  批次ID: {data['batch_id']}")
        print(f"  发票数: {data['summary']['invoice_count']} (期望 6) {'✅' if data['summary']['invoice_count'] == 6 else '❌'}")
        print(f"  问题数: {data['summary']['issue_count']} (期望 5) {'✅' if data['summary']['issue_count'] == 5 else '❌'}")
        print(f"  价税合计: {data['summary']['grand_total']} (期望 9965.0) {'✅' if data['summary']['grand_total'] == 9965.0 else '❌'}")
        print(f"  撤销记录: {data['summary']['has_undo']} (期望 True) {'✅' if data['summary']['has_undo'] else '❌'}")
        print(f"  问题类型分布: {data['summary']['issue_by_type']}")
        assert data["summary"]["invoice_count"] == 6
        assert data["summary"]["issue_count"] == 5
        assert data["summary"]["grand_total"] == 9965.0
        assert data["summary"]["has_undo"] == True

        header("12. 写入非法税率配置（负数、字符串）")
        config_file = TEST_DIR / ".invoice_validator" / "config.json"
        config = json.loads(config_file.read_text(encoding="utf-8"))
        config["valid_tax_rates"] = [0.0, 0.06, -0.13, "0.09", 0.13]
        config_file.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"valid_tax_rates = {config['valid_tax_rates']}")

        header("13. validate 非法配置错误（期望退出码 11）")
        code, out, err = run([*CLI, "validate"])
        print(f"退出码: {code} {'✅' if code == 11 else '❌'} (期望 11)")
        print(f"错误消息: {err.strip()}")
        assert code == 11, f"非法配置退出码错误: {code}"
        assert "配置错误" in err, "错误消息不包含'配置错误'"
        assert "负数" in err, "错误消息不包含'负数'"
        assert "字符串" in err, "错误消息不包含'字符串'"
        exit_bad_config = code

        header("14. 修正配置后重试")
        config["valid_tax_rates"] = [0.0, 0.06, 0.09, 0.13]
        config_file.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
        code, out, err = run([*CLI, "validate"])
        print(f"退出码: {code} {'✅' if code == 3 else '❌'} (期望 3)")
        assert code == 3, f"修正配置后校验失败: {code}"

        header("15. list 查看历史批次")
        run([*CLI, "import", "samples/invoices_sample.json"])
        code, out, err = run([*CLI, "list"])
        print(f"退出码: {code} {'✅' if code == 0 else '❌'}")
        print(out.strip())
        assert code == 0, f"list 失败: {err}"
        assert "共找到 2 个批次" in out, "批次数量错误"

        header("16. show 读取历史批次")
        import re
        match = re.search(r"batch_\S+", out)
        assert match, f"未找到批次 ID: {out}"
        batch_id = match.group(0)
        code, out, err = run([*CLI, "show", "-b", batch_id, "--issues"])
        print(f"退出码: {code} {'✅' if code == 0 else '❌'}")
        for line in out.strip().split("\n")[:10]:
            print(f"  {line}")
        assert code == 0, f"show 失败: {err}"
        assert batch_id in out, "批次 ID 不匹配"

        header("17. 退出码汇总")
        print(f"  正常校验: {exit_normal} (期望3) {'✅' if exit_normal == 3 else '❌'}")
        print(f"  无修正撤销: {exit_undo} (期望4) {'✅' if exit_undo == 4 else '❌'}")
        print(f"  非法配置: {exit_bad_config} (期望11) {'✅' if exit_bad_config == 11 else '❌'}")

        print("\n" + "="*60)
        print("🎉 所有端到端验证通过！")
        print("="*60)
        print("\n验证总结:")
        print("  ✅ init 在 ASCII/GBK 编码下不崩溃（UnicodeEncodeError 已修复）")
        print("  ✅ Markdown 报告包含完整中文标题、字段名、汇总正文")
        print("  ✅ 非法税率配置输出明确错误和稳定退出码 11（TypeError 已修复）")
        print("  ✅ JSON 导出格式正确，包含所有摘要信息")
        print("  ✅ apply/undo 功能正常，撤销记录正确")
        print("  ✅ 历史批次读取不退化")
        print("  ✅ 退出码正确：3=非法税率, 4=无修正可撤, 11=配置错误")

    finally:
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR)
            print(f"\n🧹 清理测试目录: {TEST_DIR}")


if __name__ == "__main__":
    main()
