import json
import os
from pathlib import Path

from .models import validate_project


def load_project(path, fallback):
    file_path = Path(path)
    if not file_path.exists():
        return fallback
    try:
        with file_path.open(encoding="utf-8") as project_file:
            return validate_project(json.load(project_file))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"無法讀取本機設定檔：{exc}") from exc


def save_project(path, project):
    validate_project(project)
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = file_path.with_name(file_path.name + ".tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as project_file:
            json.dump(project, project_file, ensure_ascii=False, indent=2, allow_nan=False)
            project_file.write("\n")
        os.replace(temporary_path, file_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
