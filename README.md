# 离线发票包校验 CLI (invoice-validator)

供财务人员在本地检查供应商发来的 CSV/JSON 发票包的多命令 CLI 工具。

## ✨ 功能特性

- **多命令架构**: `init`、`import`、`validate`、`fix-plan`、`apply`、`undo`、`export`
- **支持格式**: CSV 和 JSON 发票数据
- **灵活配置**: 字段映射、合法税率、金额容差可自定义
- **完整校验**:
  - 重复票号检测
  - 非法税率校验
  - 金额一致性检查（金额 + 税额 = 合计）
  - 税额容差校验（金额 × 税率 = 税额）
  - 必填列/字段检查
- **修正管理**: 生成修正草案、应用修正、撤销最近一次修正
- **审计报告**: 导出 Markdown 或 JSON 格式的审计报告
- **数据持久化**: 批次历史、校验结果、修正草案、撤销记录完整保存
- **清晰的退出码**: 便于脚本集成和自动化流程

## 📦 安装

```bash
# 从源码安装（开发模式）
pip install -e .
```

依赖：`click >= 8.1.0`（Python 标准库已包含 CSV 和 JSON 支持）

## 🚀 快速开始

### 1. 初始化工作区

```bash
invoice-validator init
```

生成配置文件和样例数据：
- 配置文件: `.invoice_validator/config.json`
- 样例数据: `samples/` 目录，包含：
  - `invoices_sample.csv` - 包含各种问题的 CSV 样例
  - `invoices_sample.json` - 同上，JSON 格式
  - `invoices_corrupted.json` - 损坏的 JSON，用于测试错误处理
  - `invoices_missing_cols.csv` - 缺少必填列的 CSV

### 2. 导入发票数据

```bash
# 导入 CSV
invoice-validator import samples/invoices_sample.csv

# 导入 JSON
invoice-validator import samples/invoices_sample.json
```

### 3. 校验发票数据

```bash
invoice-validator validate
```

校验内容：
- 🔴 重复票号（错误）
- 🔴 非法税率（错误）
- 🟡 金额不一致（警告）：`金额 + 税额 ≠ 合计`
- 🟡 税额容差超范围（警告）：`金额 × 税率 ≠ 税额`

### 4. 查看修正草案

```bash
invoice-validator fix-plan
```

### 5. 应用修正

```bash
invoice-validator apply <fix_id>
```

### 6. 撤销修正

```bash
invoice-validator undo
```

仅可撤销最近一次应用的修正。

### 7. 导出审计报告

```bash
# Markdown 格式
invoice-validator export -o audit_report -f markdown

# JSON 格式
invoice-validator export -o audit_report -f json
```

### 8. 查看批次历史和详情

```bash
# 列出所有历史批次
invoice-validator list

# 显示当前批次详情
invoice-validator show

# 显示指定批次详情
invoice-validator show -b <batch_id>

# 只显示问题
invoice-validator show --issues

# 只显示修正
invoice-validator show --fixes
```

## ⚙️ 配置文件

配置文件位于 `.invoice_validator/config.json`：

```json
{
  "field_mapping": {
    "invoice_no": "invoice_no",
    "amount": "amount",
    "tax_rate": "tax_rate",
    "tax_amount": "tax_amount",
    "total_amount": "total_amount",
    "date": "date",
    "supplier": "supplier",
    "buyer": "buyer"
  },
  "valid_tax_rates": [0.0, 0.06, 0.09, 0.13],
  "amount_tolerance": 0.01,
  "required_fields": [
    "invoice_no", "amount", "tax_rate", "total_amount", "date", "supplier", "buyer"
  ]
}
```

### 字段说明

| 配置项 | 说明 |
|--------|------|
| `field_mapping` | 内部字段名到 CSV 列名 / JSON 键名的映射。如果供应商文件的列名不同，可在此配置 |
| `valid_tax_rates` | 合法的税率列表（小数形式，如 0.13 表示 13%） |
| `amount_tolerance` | 金额比较时的容差（默认 0.01 元） |
| `required_fields` | 必填字段列表 |

## ❌ 退出码

| 退出码 | 含义 | 对应枚举 |
|--------|------|---------|
| 0 | 成功 | `SUCCESS` |
| 1 | 缺少必填列 | `MISSING_REQUIRED_COLUMNS` |
| 2 | 损坏的 JSON 文件 | `CORRUPTED_JSON` |
| 3 | 非法税率 | `INVALID_TAX_RATE` |
| 4 | 无可撤销的已应用修正 | `NO_APPLIED_FIX_TO_UNDO` |
| 5 | 批次不存在 | `BATCH_NOT_FOUND` |
| 6 | 校验发现错误 | `VALIDATION_ERRORS` |
| 7 | 无效参数 | `INVALID_ARGUMENT` |
| 8 | 文件不存在 | `FILE_NOT_FOUND` |
| 9 | 存储错误 | `STORAGE_ERROR` |
| 10 | 无可用修正草案 | `NO_FIXES_TO_APPLY` |

## 📁 数据存储结构

所有数据存储在 `.invoice_validator/` 目录：

```
.invoice_validator/
├── config.json          # 配置文件
└── data/
    ├── current_batch.json   # 当前活动批次 ID
    └── batches/             # 所有批次历史
        ├── batch_<timestamp>_<id>.json
        └── ...
```

每个批次文件包含完整的发票数据、校验结果、修正记录和撤销记录，支持重新打开 CLI 后继续处理。

## 🔄 完整工作流示例

```bash
# 1. 初始化
invoice-validator init --force

# 2. 导入发票
invoice-validator import samples/invoices_sample.csv
# 退出码: 0

# 3. 校验（预期：发现重复票号、非法税率、金额异常）
invoice-validator validate
# 退出码: 3 (非法税率)

# 4. 查看修正草案
invoice-validator fix-plan

# 5. 应用一条修正
invoice-validator apply fix_xxxxxxxx
# 退出码: 0

# 6. 导出审计报告
invoice-validator export -o audit_report -f markdown
# 退出码: 0

# 7. 撤销修正
invoice-validator undo
# 退出码: 0

# 8. 再次撤销（预期：错误，无可撤销修正）
invoice-validator undo
# 退出码: 4

# 9. 测试错误场景：缺少必填列
invoice-validator import samples/invoices_missing_cols.csv
# 退出码: 1

# 10. 测试错误场景：损坏 JSON
invoice-validator import samples/invoices_corrupted.json
# 退出码: 2

# 11. 查看所有历史批次
invoice-validator list
```

## 🛠️ 项目结构

```
invoice_validator/
├── __init__.py      # 版本信息
├── models.py        # 数据模型（Invoice, Batch, ValidationIssue, FixAction, Config, ExitCode）
├── config.py        # 配置管理
├── storage.py       # 数据持久化
├── importer.py      # CSV/JSON 导入
├── validator.py     # 校验逻辑
├── exporter.py      # 报告导出
└── cli.py           # CLI 入口（所有命令定义）
```

## 📝 代码参考

核心模块和关键函数：

- 数据模型: [models.py](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/models.py)
  - [ExitCode](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/models.py#L152-L163) - 退出码枚举
  - [ValidationType](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/models.py#L13-L19) - 校验类型枚举

- 配置管理: [config.py](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/config.py)
  - [ConfigManager.load()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/config.py#L14-L27) - 加载配置
  - [ConfigManager.save()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/config.py#L29-L35) - 保存配置

- 存储管理: [storage.py](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/storage.py)
  - [StorageManager.create_batch()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/storage.py#L21-L31) - 创建批次
  - [StorageManager.load_batch()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/storage.py#L41-L112) - 加载批次
  - [StorageManager.save_batch()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/storage.py#L33-L39) - 保存批次

- 导入器: [importer.py](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/importer.py)
  - [InvoiceImporter.import_file()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/importer.py#L25-L46) - 导入文件入口

- 校验器: [validator.py](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/validator.py)
  - [InvoiceValidator.validate()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/validator.py#L27-L43) - 校验入口
  - [_check_duplicate_invoice_nos()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/validator.py#L45-L65) - 重复票号检查
  - [_check_valid_tax_rates()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/validator.py#L67-L86) - 税率校验
  - [_check_amount_consistency()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/validator.py#L88-L163) - 金额一致性检查

- 导出器: [exporter.py](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/exporter.py)
  - [ReportExporter.export()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/exporter.py#L15-L30) - 导出入口
  - [_generate_markdown()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/exporter.py#L75-L172) - Markdown 报告生成
  - [_generate_json()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/exporter.py#L32-L47) - JSON 报告生成

- CLI 命令: [cli.py](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/cli.py)

## 📜 许可证

内部工具
