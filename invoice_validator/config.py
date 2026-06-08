import json
import os
import stat
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from datetime import datetime
from .models import Config, ExitCode, SupplierRule


class ConfigError(Exception):
    def __init__(self, message: str, exit_code: ExitCode = ExitCode.INVALID_CONFIG):
        super().__init__(message)
        self.exit_code = exit_code


class SupplierRuleError(ConfigError):
    pass


class ConfigManager:
    def __init__(self, workspace: Optional[str] = None):
        self.workspace = Path(workspace or os.getcwd())
        self.config_dir = self.workspace / ".invoice_validator"
        self.config_file = self.config_dir / "config.json"
        self.rules_file = self.config_dir / "supplier_rules.json"
        self.supplier_rules_file = self.rules_file
        self.config: Optional[Config] = None

    def _check_write_permission(self, path: Path) -> None:
        """检查写入权限，防止静默失败"""
        try:
            if path.exists():
                if not os.access(path, os.W_OK):
                    raise SupplierRuleError(
                        f"权限不足: 无法写入 '{path}'，目录为只读或权限不足。",
                        ExitCode.PERMISSION_DENIED,
                    )
            else:
                parent = path.parent
                if not parent.exists():
                    parent.mkdir(parents=True, exist_ok=True)
                if not os.access(parent, os.W_OK):
                    raise SupplierRuleError(
                        f"权限不足: 无法写入目录 '{parent}'，目录为只读或权限不足。",
                        ExitCode.PERMISSION_DENIED,
                    )
        except PermissionError as e:
            raise SupplierRuleError(
                f"权限不足: {str(e)}。请检查配置目录权限。",
                ExitCode.PERMISSION_DENIED,
            ) from e

    def _validate_required_fields(self, fields: List[str]) -> None:
        """验证必填字段名，不允许空字符串"""
        for f in fields:
            if not f or not str(f).strip():
                raise SupplierRuleError(
                    "必填字段名不能为空。请提供有效的字段名称。",
                    ExitCode.EMPTY_FIELD_NAME,
                )

    def _validate_tax_rates(self, rates: List) -> Tuple[List[float], List[str]]:
        cleaned: List[float] = []
        errors: List[str] = []

        for i, rate in enumerate(rates):
            if isinstance(rate, bool):
                errors.append(f"索引 {i}: 布尔值 {rate} 不是有效税率")
                continue
            if isinstance(rate, str):
                errors.append(f"索引 {i}: 字符串 '{rate}' 不是有效税率（请改用数字 {rate}）")
                continue
            if not isinstance(rate, (int, float)):
                errors.append(f"索引 {i}: {type(rate).__name__} 类型 '{rate}' 不是有效税率")
                continue
            if rate < 0:
                errors.append(f"索引 {i}: 负数 {rate} 不是有效税率（税率不能为负）")
                continue
            if rate > 1:
                errors.append(f"索引 {i}: {rate} 超过最大值 1（税率应为小数形式，如 13% 请写 0.13）")
                continue
            cleaned.append(float(rate))

        return cleaned, errors

    def load(self) -> Config:
        config = self._load_config()
        config.supplier_rules = self._load_supplier_rules()
        self.config = config
        return config

    def _load_config(self) -> Config:
        if not self.config_file.exists():
            return Config()
        try:
            with open(self.config_file, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise RuntimeError(f"Failed to load config: {e}") from e

        valid_tax_rates_raw = data.get("valid_tax_rates", Config().valid_tax_rates)
        valid_tax_rates, errors = self._validate_tax_rates(valid_tax_rates_raw)
        if errors:
            raise ConfigError(
                f"配置错误: valid_tax_rates 包含非法值: {'; '.join(errors)}。"
                f"请确保所有税率为 0 到 1 之间的数字（如 0.13 表示 13%），不允许字符串或负数。"
            )

        return Config(
            field_mapping=data.get("field_mapping", Config().field_mapping),
            valid_tax_rates=valid_tax_rates,
            amount_tolerance=data.get("amount_tolerance", Config().amount_tolerance),
            required_fields=data.get("required_fields", Config().required_fields),
        )

    def _load_supplier_rules(self) -> Dict[str, SupplierRule]:
        if not self.rules_file.exists():
            return {}
        try:
            with open(self.rules_file, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise RuntimeError(f"Failed to load supplier rules: {e}") from e

        rules = {}
        for supplier, rule_data in data.items():
            rules[supplier] = SupplierRule.from_dict(rule_data)
        return rules

    def _save_supplier_rules(self, rules: Dict[str, SupplierRule]) -> None:
        self._check_write_permission(self.rules_file)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        try:
            data = {k: v.to_dict() for k, v in rules.items()}
            with open(self.rules_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except PermissionError as e:
            raise SupplierRuleError(
                f"权限不足: 无法写入供应商规则文件: {str(e)}。",
                ExitCode.PERMISSION_DENIED,
            ) from e
        except IOError as e:
            raise RuntimeError(f"Failed to save supplier rules: {e}") from e

    def save(self, config: Config) -> None:
        self._check_write_permission(self.config_file)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
        except PermissionError as e:
            raise SupplierRuleError(
                f"权限不足: 无法写入配置文件: {str(e)}。",
                ExitCode.PERMISSION_DENIED,
            ) from e
        except IOError as e:
            raise RuntimeError(f"Failed to save config: {e}") from e

    def exists(self) -> bool:
        return self.config_file.exists()

    def add_supplier_rule(
        self,
        supplier: str,
        valid_tax_rates: Optional[List[float]] = None,
        amount_tolerance: Optional[float] = None,
        required_fields: Optional[List[str]] = None,
        overwrite: bool = False,
    ) -> Tuple[SupplierRule, Dict[str, Dict[str, Any]]]:
        """添加供应商规则，返回 (规则, 冲突信息)"""
        if not supplier or not str(supplier).strip():
            raise SupplierRuleError(
                "供应商名称不能为空。",
                ExitCode.INVALID_ARGUMENT,
            )

        supplier = str(supplier).strip()

        config = self.load()

        if supplier in config.supplier_rules and not overwrite:
            raise SupplierRuleError(
                f"供应商 '{supplier}' 已存在规则。使用 --overwrite 覆盖现有规则。",
                ExitCode.DUPLICATE_SUPPLIER_RULE,
            )

        if valid_tax_rates:
            cleaned_rates, errors = self._validate_tax_rates(valid_tax_rates)
            if errors:
                raise ConfigError(
                    f"税率配置错误: {'; '.join(errors)}。",
                    ExitCode.INVALID_TAX_RATE,
                )
            valid_tax_rates = cleaned_rates

        if required_fields:
            self._validate_required_fields(required_fields)

        now = datetime.now().isoformat()
        if supplier in config.supplier_rules:
            existing = config.supplier_rules[supplier]
            rule = SupplierRule(
                supplier=supplier,
                valid_tax_rates=valid_tax_rates if valid_tax_rates is not None else existing.valid_tax_rates,
                amount_tolerance=amount_tolerance if amount_tolerance is not None else existing.amount_tolerance,
                required_fields=required_fields if required_fields is not None else existing.required_fields,
                created_at=existing.created_at,
                updated_at=now,
            )
        else:
            rule = SupplierRule(
                supplier=supplier,
                valid_tax_rates=valid_tax_rates or [],
                amount_tolerance=amount_tolerance,
                required_fields=required_fields if required_fields is not None else [],
                created_at=now,
                updated_at=now,
            )

        config.supplier_rules[supplier] = rule
        self._save_supplier_rules(config.supplier_rules)

        conflicts = config.detect_conflicts(rule)
        return rule, conflicts

    def update_supplier_rule(
        self,
        supplier: str,
        valid_tax_rates: Optional[List[float]] = None,
        amount_tolerance: Optional[float] = None,
        required_fields: Optional[List[str]] = None,
    ) -> Tuple[SupplierRule, Dict[str, Dict[str, Any]]]:
        """更新供应商规则"""
        return self.add_supplier_rule(
            supplier=supplier,
            valid_tax_rates=valid_tax_rates,
            amount_tolerance=amount_tolerance,
            required_fields=required_fields,
            overwrite=True,
        )

    def delete_supplier_rule(self, supplier: str) -> None:
        """删除供应商规则"""
        config = self.load()
        if supplier not in config.supplier_rules:
            raise SupplierRuleError(
                f"未找到供应商 '{supplier}' 的规则。",
                ExitCode.SUPPLIER_RULE_NOT_FOUND,
            )
        del config.supplier_rules[supplier]
        self._save_supplier_rules(config.supplier_rules)

    def get_supplier_rule(self, supplier: str) -> Tuple[SupplierRule, Dict[str, Dict[str, Any]]]:
        """获取供应商规则及其与全局配置的冲突"""
        config = self.load()
        if supplier not in config.supplier_rules:
            raise SupplierRuleError(
                f"未找到供应商 '{supplier}' 的规则。",
                ExitCode.SUPPLIER_RULE_NOT_FOUND,
            )
        rule = config.supplier_rules[supplier]
        conflicts = config.detect_conflicts(rule)
        return rule, conflicts

    def list_supplier_rules(self) -> List[Tuple[SupplierRule, List[str]]]:
        """列出所有供应商规则，返回 (规则, 冲突字段列表)"""
        config = self.load()
        result = []
        for rule in sorted(config.supplier_rules.values(), key=lambda r: r.supplier):
            conflicts = config.detect_conflicts(rule)
            result.append((rule, list(conflicts.keys())))
        return result
