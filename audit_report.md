# 发票校验审计报告

- **批次 ID**: `batch_20260608_095202_7a78e98b`
- **创建时间**: 2026-06-08T09:52:02.844453
- **源文件**: samples/invoices_sample.csv
- **文件类型**: CSV
- **校验状态**: ✓ 已校验
- **校验时间**: 2026-06-08T09:52:15.939387

## 汇总

| 指标 | 数值 |
|------|------|
| 发票总数 | 6 |
| 问题总数 | 5 |
| - 错误 | 3 |
| - 警告 | 2 |
| 修正草案 | 2 |
| - 已应用 | 1 |
| - 待应用 | 1 |
| 金额合计 | ¥8,800.00 |
| 税额合计 | ¥1,153.00 |
| 价税合计 | ¥9,955.00 |
| 撤销记录 | 有 |

### 问题类型分布

| 类型 | 数量 |
|------|------|
| amount_mismatch | 2 |
| duplicate_invoice_no | 2 |
| invalid_tax_rate | 1 |

## 校验问题详情

### 1. 🔴 duplicate_invoice_no

- **严重程度**: error
- **发票号**: INV002
- **行号**: 3
- **描述**: Duplicate invoice number 'INV002' found in rows [3, 4]
- **详情**:
  - duplicate_rows: `[3, 4]`
  - count: `2`

### 2. 🔴 duplicate_invoice_no

- **严重程度**: error
- **发票号**: INV002
- **行号**: 4
- **描述**: Duplicate invoice number 'INV002' found in rows [3, 4]
- **详情**:
  - duplicate_rows: `[3, 4]`
  - count: `2`

### 3. 🔴 invalid_tax_rate

- **严重程度**: error
- **发票号**: INV004
- **行号**: 6
- **描述**: Invalid tax rate 0.25 for invoice 'INV004'. Valid rates: [0.0, 0.06, 0.09, 0.13]
- **详情**:
  - invalid_rate: `0.25`
  - valid_rates: `[0.0, 0.06, 0.09, 0.13]`

### 4. 🟡 amount_mismatch

- **严重程度**: warning
- **发票号**: INV003
- **行号**: 5
- **描述**: Amount mismatch for invoice 'INV003': amount + tax_amount = 3000.0 + 390.0 = 3390.0, but total_amount = 3400.0 (diff: 10.0000)
- **详情**:
  - amount: `3000.0`
  - tax_amount: `390.0`
  - computed_total: `3390.0`
  - stated_total: `3400.0`
  - difference: `10.0`
  - tolerance: `0.01`

### 5. 🟡 amount_mismatch

- **严重程度**: warning
- **发票号**: INV005
- **行号**: 7
- **描述**: Amount mismatch for invoice 'INV005': amount + tax_amount = 800.0 + 48.0 = 848.0, but total_amount = 850.0 (diff: 2.0000)
- **详情**:
  - amount: `800.0`
  - tax_amount: `48.0`
  - computed_total: `848.0`
  - stated_total: `850.0`
  - difference: `2.0`
  - tolerance: `0.01`

## 修正记录

### 1. ✅ 已应用 修正发票 INV003 的合计金额

- **修正 ID**: `fix_fe0ca4c2`
- **发票号**: INV003
- **字段**: `total_amount`
- **原值**: `3400.0`
- **新值**: `3390.0`
- **原因**: 金额 + 税额 = 3000.0 + 390.0 = 3390.0，与票面合计 3400.0 不符
- **应用时间**: 2026-06-08T09:53:07.631418

### 2. ⏳ 待应用 修正发票 INV005 的合计金额

- **修正 ID**: `fix_9a66e39c`
- **发票号**: INV005
- **字段**: `total_amount`
- **原值**: `850.0`
- **新值**: `848.0`
- **原因**: 金额 + 税额 = 800.0 + 48.0 = 848.0，与票面合计 850.0 不符

## 最近撤销记录

- **撤销时间**: None
- **修正 ID**: `fix_fe0ca4c2`
- **发票号**: INV003
- **字段**: `total_amount`
- **恢复值**: `3400.0`
- **原值**: `3400.0`

---
*报告由 invoice-validator 自动生成*