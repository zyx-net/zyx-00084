import json
import os
from pathlib import Path
from typing import Optional, Tuple, List
from .models import Config, ExitCode


class ConfigError(Exception):
    def __init__(self, message: str, exit_code: ExitCode = ExitCode.INVALID_CONFIG):
        super().__init__(message)
        self.exit_code = exit_code


class ConfigManager:
    def __init__(self, workspace: Optional[str] = None):
        self.workspace = Path(workspace or os.getcwd())
        self.config_dir = self.workspace / ".invoice_validator"
        self.config_file = self.config_dir / "config.json"

    def load(self) -> Config:
        if not self.config_file.exists():
            return Config()
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
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

    def save(self, config: Config) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise RuntimeError(f"Failed to save config: {e}") from e

    def exists(self) -> bool:
        return self.config_file.exists()
