"""JSON config and history persistence services."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from shutil import copy2
from typing import Any

from device_parameter_tool.models.device_config import DeviceConfig


@dataclass(slots=True)
class HistoryRecord:
    saved_at: str
    note: str
    config: DeviceConfig

    def to_dict(self) -> dict[str, Any]:
        return {
            "saved_at": self.saved_at,
            "note": self.note,
            "config": self.config.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistoryRecord":
        return cls(
            saved_at=data["saved_at"],
            note=data.get("note", ""),
            config=DeviceConfig.from_dict(data["config"]),
        )


DEFAULT_CONFIG_PATH = Path("data/current_config.json")
DEFAULT_HISTORY_PATH = Path("data/site_history.json")


class ConfigService:
    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH, history_path: Path = DEFAULT_HISTORY_PATH):
        self.config_path = Path(config_path)
        self.history_path = Path(history_path)

    def save_config(self, config: DeviceConfig, path: Path | None = None) -> Path:
        target_path = Path(path or self.config_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            backup_path = target_path.with_suffix(target_path.suffix + ".bak")
            copy2(target_path, backup_path)
        target_path.write_text(json.dumps(config.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return target_path

    def load_config(self, path: Path | None = None) -> DeviceConfig:
        target_path = Path(path or self.config_path)
        data = json.loads(target_path.read_text(encoding="utf-8"))
        return DeviceConfig.from_dict(data)

    def append_history(self, config: DeviceConfig, note: str = "") -> HistoryRecord:
        history = self.load_history()
        record = HistoryRecord(
            saved_at=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
            note=note,
            config=DeviceConfig.from_dict(config.to_dict()),
        )
        history.insert(0, record)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.write_text(
            json.dumps([item.to_dict() for item in history], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return record

    def load_history(self) -> list[HistoryRecord]:
        if not self.history_path.exists():
            return []
        data = json.loads(self.history_path.read_text(encoding="utf-8"))
        return [HistoryRecord.from_dict(item) for item in data]
