# 离线发票包校验 CLI (invoice-validator)

供财务人员在本地检查供应商发来的 CSV/JSON 发票包的多命令 CLI 工具。

## ✨ 功能特性

- **多命令架构**: `init`、`import`、`validate`、`fix-plan`、`apply`、`undo`、`export`、`rule`
- **支持格式**: CSV 和 JSON 发票数据
- **灵活配置**: 字段映射、合法税率、金额容差可自定义
- **🌟 供应商专属规则**: 支持为特定供应商配置独立的税率白名单、金额容差、必填字段
- **规则优先级**: 供应商专属规则优先于全局配置，冲突自动检测与提示
- **完整校验**:
  - 重复票号检测
  - 非法税率校验（支持供应商特定税率）
  - 金额一致性检查（金额 + 税额 = 合计）
  - 税额容差校验（金额 × 税率 = 税额，支持供应商特定容差）
  - 必填列/字段检查（支持供应商特定必填字段）
- **修正管理**: 生成修正草案、应用修正、撤销最近一次修正
- **审计报告**: 导出 Markdown 或 JSON 格式的审计报告，**逐张发票可追溯规则来源**
- **数据持久化**: 批次历史、校验结果、修正草案、撤销记录、供应商规则完整保存
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
- 全局配置: `.invoice_validator/config.json`
- 供应商规则: `.invoice_validator/supplier_rules.json`
- 样例数据: `samples/` 目录，包含：
  - `invoices_sample.csv` - 包含各种问题的 CSV 样例
  - `invoices_sample.json` - 同上，JSON 格式
  - `invoices_corrupted.json` - 损坏的 JSON，用于测试错误处理
  - `invoices_missing_cols.csv` - 缺少必填列的 CSV

### 2. 管理供应商专属规则

#### 2.1 添加供应商规则

```bash
# 为华为技术有限公司配置专属规则：
# 税率白名单：0.13、0.06
# 金额容差：0.05（严格于全局的 0.01）
# 必填字段：增加 tax_amount
invoice-validator rule add "华为技术有限公司" \
  -t 0.13 -t 0.06 \
  -T 0.05 \
  -r invoice_no -r amount -r tax_rate -r tax_amount -r total_amount -r date -r supplier -r buyer
```

输出会显示规则配置及与全局配置的冲突提示。

#### 2.2 查看所有供应商规则

```bash
invoice-validator rule list
```

#### 2.3 查看指定供应商规则详情（含与全局的差异对比）

```bash
invoice-validator rule show "华为技术有限公司"
```

#### 2.4 更新供应商规则

```bash
# 更新华为的税率白名单，增加 0.09
invoice-validator rule update "华为技术有限公司" -t 0.13 -t 0.06 -t 0.09

# 清除华为的容差配置，恢复使用全局
invoice-validator rule update "华为技术有限公司" --clear-tolerance
```

#### 2.5 删除供应商规则

```bash
# 需要输入供应商名称确认删除
invoice-validator rule delete "华为技术有限公司"

# 强制删除，跳过确认
invoice-validator rule delete "华为技术有限公司" --force
```

#### 2.6 重新加载规则（验证重启后读取效果）

```bash
invoice-validator rule reload
```

### 3. 导入发票数据

```bash
# 导入 CSV
invoice-validator import samples/invoices_sample.csv

# 导入 JSON
invoice-validator import samples/invoices_sample.json
```

导入时会自动根据供应商匹配规则，并在输出中显示：
- 🌟 使用供应商专属规则的发票数量
- 🔹 使用全局默认规则的发票数量
- ⚠️ 供应商规则与全局配置的冲突信息

### 4. 校验发票数据

```bash
invoice-validator validate
```

校验内容：
- 🔴 重复票号（错误）
- 🔴 非法税率（错误，使用该供应商的专属税率白名单）
- 🟡 金额不一致（警告，使用该供应商的专属容差）
- 🟡 税额容差超范围（警告，使用该供应商的专属容差）

校验输出中每条问题都会标注 `[supplier]` 或 `[global]` 标识使用的规则来源。

### 5. 查看修正草案

```bash
invoice-validator fix-plan
```

### 6. 应用修正

```bash
invoice-validator apply <fix_id>
```

### 7. 撤销修正

```bash
invoice-validator undo
```

仅可撤销最近一次应用的修正。

### 8. 导出审计报告（逐张发票可追溯规则来源）

```bash
# Markdown 格式（包含规则来源表格、冲突信息）
invoice-validator export -o audit_report -f markdown

# JSON 格式（每条发票、每个问题都包含 rule_source 字段）
invoice-validator export -o audit_report -f json
```

报告包含：
- 规则来源分布统计（🌟 供应商专属 vs 🔹 全局默认）
- **发票明细表格**：逐张显示规则来源、规则状态、冲突信息
- 每个问题详情中包含规则来源标识
- 规则来源说明附录

### 9. 查看批次历史和详情

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

### 8.1 全局配置文件

位置：`.invoice_validator/config.json`

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

### 8.2 供应商规则配置文件

位置：`.invoice_validator/supplier_rules.json`

```json
{
  "华为技术有限公司": {
    "supplier": "华为技术有限公司",
    "valid_tax_rates": [0.06, 0.13],
    "amount_tolerance": 0.05,
    "required_fields": [
      "invoice_no", "amount", "tax_rate", "tax_amount",
      "total_amount", "date", "supplier", "buyer"
    ],
    "created_at": "2025-01-01T12:00:00.000000",
    "updated_at": "2025-01-01T12:00:00.000000"
  }
}
```

**修改规则时，请始终使用 `invoice-validator rule` 子命令，不要手动编辑此文件。**

### 8.3 字段说明

| 配置项 | 说明 |
|--------|------|
| `field_mapping` | 内部字段名到 CSV 列名 / JSON 键名的映射。如果供应商文件的列名不同，可在此配置 |
| `valid_tax_rates` | 合法的税率列表（小数形式，如 0.13 表示 13%） |
| `amount_tolerance` | 金额比较时的容差（默认 0.01 元） |
| `required_fields` | 必填字段列表 |

## 🌟 规则优先级与冲突处理

### 9.1 优先级规则

1. **供应商专属规则 > 全局默认规则**
2. 如果某供应商配置了 `valid_tax_rates`，则使用该列表；否则继承全局
3. 如果某供应商配置了 `amount_tolerance`，则使用该值；否则继承全局
4. 如果某供应商配置了 `required_fields`，则使用该列表；否则继承全局

### 9.2 冲突检测

添加或更新供应商规则时，自动检测与全局配置的差异：

```
⚠️  规则冲突提示（与全局配置的差异）:
   - valid_tax_rates: 全局=[0.0, 0.06, 0.09, 0.13] → 供应商=[0.06, 0.13] [overridden]
   - amount_tolerance: 全局=0.01 → 供应商=0.05 [overridden]
```

### 9.3 规则覆盖查看位置

1. **导入/校验输出**：显示规则来源统计和冲突发票列表
2. **`rule show <供应商>` 命令**：表格形式对比供应商规则与全局配置
3. **审计报告**：
   - Markdown：发票明细表格的「规则来源」「规则状态」「冲突信息」列
   - JSON：每张发票的 `rule_source` 对象，包含 `conflict_status` 字段

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
| 12 | 供应商规则已存在（未使用 --overwrite） | `DUPLICATE_SUPPLIER_RULE` |
| 13 | 必填字段名不能为空 | `EMPTY_FIELD_NAME` |
| 14 | 配置目录权限不足，无法写入 | `PERMISSION_DENIED` |
| 15 | 供应商规则不存在 | `SUPPLIER_RULE_NOT_FOUND` |

## 📁 数据存储结构

所有数据存储在 `.invoice_validator/` 目录：

```
.invoice_validator/
├── config.json              # 全局配置文件
├── supplier_rules.json      # 🌟 供应商专属规则（独立持久化）
└── data/
    ├── current_batch.json   # 当前活动批次 ID
    └── batches/             # 所有批次历史
        ├── batch_<timestamp>_<id>.json
        └── ...
```

每个批次文件包含完整的发票数据、校验结果、修正记录、撤销记录和**每张发票的规则来源信息**，支持重新打开 CLI 后继续处理。

## 🔄 完整工作流示例

```bash
# 1. 初始化工作区
invoice-validator init --force
# 退出码: 0
# 输出: 配置文件、样例数据已创建

# 2. 查看当前规则配置（预期为空）
invoice-validator rule list
# 退出码: 0
# 输出: 没有配置任何供应商规则

# 3. 添加第一条供应商规则（华为技术有限公司）
invoice-validator rule add "华为技术有限公司" \
  -t 0.13 -t 0.06 \
  -T 0.05 \
  -r invoice_no -r amount -r tax_rate -r tax_amount -r total_amount -r date -r supplier -r buyer
# 退出码: 0
# 输出: 规则创建成功，显示冲突提示（税率、容差、必填字段均覆盖全局）

# 4. 再次添加同一供应商（预期：失败，退出码 12）
invoice-validator rule add "华为技术有限公司" -t 0.13
# 退出码: 12 (DUPLICATE_SUPPLIER_RULE)
# 输出: 供应商已存在，使用 --overwrite 覆盖

# 5. 查看华为规则详情
invoice-validator rule show "华为技术有限公司"
# 退出码: 0
# 输出: 表格形式对比供应商规则与全局配置

# 6. 添加第二条规则（阿里巴巴集团）
invoice-validator rule add "阿里巴巴集团" -t 0.09 -t 0.06
# 退出码: 0
# 输出: 规则创建成功，仅税率白名单覆盖全局

# 7. 查看所有规则
invoice-validator rule list
# 退出码: 0
# 输出: 2 条规则的列表

# 8. 测试空字段名（预期：失败，退出码 13）
invoice-validator rule add "测试供应商" -r ""
# 退出码: 13 (EMPTY_FIELD_NAME)
# 输出: 字段名不能为空

# 9. 导入 CSV 发票
invoice-validator import samples/invoices_sample.csv
# 退出码: 0
# 输出: 导入 6 张发票
#       规则来源: 🌟 供应商专属=2张（华为）, 🔹 全局默认=4张
#       ⚠️  规则冲突: 2 张发票涉及冲突

# 10. 校验（预期：发现问题，退出码 3）
invoice-validator validate
# 退出码: 3 (INVALID_TAX_RATE)
# 输出: 每条问题标注 [supplier] 或 [global]

# 11. 重新加载规则（验证重启后读取效果）
invoice-validator rule reload
# 退出码: 0
# 输出: 已重新加载 2 条规则

# 12. 导出 Markdown 报告（逐张发票追溯规则来源）
invoice-validator export -o audit_report -f markdown
# 退出码: 0
# 输出: 报告已导出，包含规则来源分布、发票明细表格

# 13. 导出 JSON 报告（每条发票包含 rule_source 字段）
invoice-validator export -o audit_report -f json
# 退出码: 0
# 输出: 报告已导出

# 14. 查看报告内容（确认规则来源字段）
# audit_report.json 中每张发票包含:
# "rule_source": {
#   "rule_source": "supplier",
#   "supplier": "华为技术有限公司",
#   "conflicts": {...},
#   "conflict_status": "conflicts_detected"
# }

# 15. 更新华为规则，清除容差配置
invoice-validator rule update "华为技术有限公司" --clear-tolerance
# 退出码: 0

# 16. 再次校验（华为的容差恢复为全局 0.01）
invoice-validator validate

# 17. 删除华为规则（需要确认）
echo "华为技术有限公司" | invoice-validator rule delete "华为技术有限公司"
# 退出码: 0

# 18. 查看不存在的规则（预期：失败，退出码 15）
invoice-validator rule show "不存在的供应商"
# 退出码: 15 (SUPPLIER_RULE_NOT_FOUND)

# 19. 测试只读目录权限（退出码 14）
# （手动将 .invoice_validator 设为只读，然后执行 rule add）
# invoice-validator rule add "测试" -t 0.13
# 退出码: 14 (PERMISSION_DENIED)

# 20. 查看所有历史批次
invoice-validator list
```

## 🛠️ 项目结构

```
invoice_validator/
├── __init__.py      # 版本信息
├── models.py        # 数据模型（Invoice, Batch, ValidationIssue, FixAction, Config, ExitCode, SupplierRule, EffectiveConfigInfo）
├── config.py        # 配置管理（含供应商规则 CRUD、权限检查）
├── storage.py       # 数据持久化
├── importer.py      # CSV/JSON 导入（含供应商规则匹配、规则来源跟踪）
├── validator.py     # 校验逻辑（含供应商规则优先级匹配）
├── exporter.py      # 报告导出（含规则来源追溯）
└── cli.py           # CLI 入口（所有命令定义，含 rule 子命令组）
```

## 📝 代码参考

核心模块和关键函数：

- 数据模型: [models.py](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/models.py)
  - [ExitCode](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/models.py#L152-L172) - 退出码枚举（含 12-15 供应商规则相关）
  - [ValidationType](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/models.py#L13-L19) - 校验类型枚举
  - [SupplierRule](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/models.py#L59-L89) - 供应商规则数据类
  - [EffectiveConfigInfo](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/models.py#L38-L55) - 规则来源信息
  - [Config.get_effective_config()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/models.py#L232-L262) - 获取供应商有效配置
  - [Config.detect_conflicts()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/models.py#L264-L301) - 检测规则冲突

- 配置管理: [config.py](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/config.py)
  - [SupplierRuleError](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/config.py#L12-L16) - 供应商规则异常
  - [_check_write_permission()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/config.py#L44-L53) - 权限检查
  - [add_supplier_rule()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/config.py#L100-L171) - 添加供应商规则
  - [update_supplier_rule()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/config.py#L173-L226) - 更新供应商规则
  - [delete_supplier_rule()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/config.py#L228-L251) - 删除供应商规则

- 存储管理: [storage.py](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/storage.py)
  - [StorageManager.load_batch()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/storage.py#L41-L112) - 加载批次（含 rule_source 反序列化）

- 导入器: [importer.py](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/importer.py)
  - [InvoiceImporter.import_file()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/importer.py#L55-L77) - 导入文件入口
  - [_get_effective_required_fields()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/importer.py#L32-L37) - 获取供应商必填字段

- 校验器: [validator.py](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/validator.py)
  - [InvoiceValidator.validate()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/validator.py#L51-L83) - 校验入口
  - [_get_effective_config()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/validator.py#L31-L33) - 获取供应商有效配置

- 导出器: [exporter.py](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/exporter.py)
  - [ReportExporter._generate_markdown()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/exporter.py#L179-L352) - Markdown 报告（含规则来源表格）
  - [ReportExporter._generate_json()](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/exporter.py#L95-L136) - JSON 报告（含 rule_source 字段）

- CLI 命令: [cli.py](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/cli.py)
  - [rule_cmd](file:///d:/workSpace/AI__SPACE/zyx-00084/invoice_validator/cli.py#L545-L817) - rule 子命令组

## 📜 许可证

内部工具
