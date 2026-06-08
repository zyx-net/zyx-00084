import json
import os
from pathlib import Path
from typing import Optional
from .models import Config


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
            return Config(
                field_mapping=data.get("field_mapping", Config().field_mapping),
                valid_tax_rates=data.get("valid_tax_rates", Config().valid_tax_rates),
                amount_tolerance=data.get("amount_tolerance", Config().amount_tolerance),
                required_fields=data.get("required_fields", Config().required_fields),
            )
        except (json.JSONDecodeError, IOError) as e:
            raise RuntimeError(f"Failed to load config: {e}") from e

    def save(self, config: Config) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise RuntimeError(f"Failed to save config: {e}") from e

    def exists(self) -> bool:
        return self.config_file.exists()
