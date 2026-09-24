"""Flask web UI for the device parameter tool."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

from device_parameter_tool.models.device_config import DeviceConfig, LaneConfig, LidarConfig
from device_parameter_tool.services.config_service import ConfigService
from device_parameter_tool.services.lidar_calculator import calculate_lidar_results


def _coerce_int(value: str | None, default: int = 0) -> int:
    if value is None or str(value).strip() == "":
        return default
    return int(value)


def _coerce_float(value: str | None, default: float = 0.0) -> float:
    if value is None or str(value).strip() == "":
        return default
    return float(value)


def _coerce_bool(value: str | None) -> bool:
    return value in {"1", "true", "True", "on", "yes"}


def _parse_lane_pair(first_value: str | None, second_value: str | None) -> list[int]:
    lanes: list[int] = []
    for value in (first_value, second_value):
        if value is None or str(value).strip() == "" or str(value).strip().lower() == "none":
            continue
        lane_number = int(value)
        if lane_number not in lanes:
            lanes.append(lane_number)
    return lanes


def _build_lane_rows(form, lane_count: int) -> list[LaneConfig]:
    lanes: list[LaneConfig] = []
    for index in range(lane_count):
        lanes.append(
            LaneConfig(
                lane_number=_coerce_int(form.get(f"lane_{index}_number"), index),
                width_mm=_coerce_float(form.get(f"lane_{index}_width_mm"), 0.0),
            )
        )
    return lanes


def _build_lidar_rows(form, lidar_count: int, prefix: str = "primary") -> list[LidarConfig]:
    lidars: list[LidarConfig] = []
    for index in range(lidar_count):
        lidars.append(
            LidarConfig(
                assigned_lanes=_parse_lane_pair(
                    form.get(f"{prefix}_lidar_{index}_lane_a"),
                    form.get(f"{prefix}_lidar_{index}_lane_b"),
                ),
                center_distance_mm=_coerce_float(form.get(f"{prefix}_lidar_{index}_center_distance_mm"), 0.0),
                auto_calculate=_coerce_bool(form.get(f"{prefix}_lidar_{index}_auto_calculate")),
            )
        )
    return lidars


def _config_from_form(form) -> DeviceConfig:
    lane_count = _coerce_int(form.get("lane_count"), 1)
    lidar_count = _coerce_int(form.get("primary_lidar_count"), 1)
    backup_lidar_count = _coerce_int(form.get("backup_lidar_count"), lidar_count)
    has_backup = _coerce_bool(form.get("has_backup"))
    return DeviceConfig(
        site_name=form.get("site_name", "未命名點位").strip() or "未命名點位",
        note=form.get("note", ""),
        has_backup=has_backup,
        lanes=_build_lane_rows(form, lane_count),
        lidars=_build_lidar_rows(form, lidar_count, prefix="primary"),
        backup_lidars=_build_lidar_rows(form, backup_lidar_count, prefix="backup") if has_backup else [],
    )


def _lidar_form_rows(lidars: list[LidarConfig]) -> list[dict]:
    return [
        {
            "lane_a": lidar.assigned_lanes[0] if lidar.assigned_lanes else "none",
            "lane_b": lidar.assigned_lanes[1] if len(lidar.assigned_lanes) > 1 else "none",
            "center_distance_mm": lidar.center_distance_mm,
            "auto_calculate": lidar.auto_calculate,
        }
        for lidar in lidars
    ]


def _form_defaults(config: DeviceConfig) -> dict:
    lane_rows = [
        {
            "lane_number": lane.lane_number,
            "width_mm": lane.width_mm,
        }
        for lane in sorted(config.lanes, key=lambda item: item.lane_number)
    ]
    lidar_rows = _lidar_form_rows(config.lidars)
    backup_lidar_rows = _lidar_form_rows(config.backup_lidars)
    return {
        "site_name": config.site_name,
        "note": config.note,
        "has_backup": config.has_backup,
        "lane_count": max(1, len(lane_rows)),
        "primary_lidar_count": max(1, len(lidar_rows)),
        "backup_lidar_count": max(1, len(backup_lidar_rows) if backup_lidar_rows else len(lidar_rows)),
        "lanes": lane_rows or [{"lane_number": 0, "width_mm": ""}],
        "lidars": lidar_rows or [{"lane_a": 0, "lane_b": "none", "center_distance_mm": "", "auto_calculate": True}],
        "backup_lidars": backup_lidar_rows or [{"lane_a": 0, "lane_b": "none", "center_distance_mm": "", "auto_calculate": True}],
        "lane_options": [{"value": "none", "label": "None"}] + [{"value": i, "label": f"Lane{i}"} for i in range(7)],
    }


def create_app(data_dir: str | Path | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates")
    base_dir = Path(data_dir or "data")
    service = ConfigService(config_path=base_dir / "current_config.json", history_path=base_dir / "site_history.json")

    def render_page(config: DeviceConfig, message: str = "", error: str = ""):
        summaries = []
        try:
            if config.lanes and config.lidars:
                summaries.append(("主 Lidar", calculate_lidar_results(config.lanes, config.lidars)))
            if config.has_backup and config.lanes and config.backup_lidars:
                summaries.append(("備援 Lidar", calculate_lidar_results(config.lanes, config.backup_lidars)))
        except ValueError as exc:
            error = str(exc)
        return render_template(
            "index.html",
            form=_form_defaults(config),
            summaries=summaries,
            message=message,
            error=error,
            history=service.load_history(),
        )

    @app.get("/")
    def index():
        if service.config_path.exists():
            config = service.load_config()
        else:
            config = DeviceConfig(lanes=[LaneConfig(lane_number=0, width_mm=3500.0)])
        return render_page(config)

    @app.post("/preview")
    def preview():
        config = _config_from_form(request.form)
        try:
            config.validate()
        except ValueError as exc:
            return render_page(config, error=str(exc))
        return render_page(config, message="已更新預覽")

    @app.post("/save")
    def save():
        config = _config_from_form(request.form)
        config.validate()
        service.save_config(config)
        service.append_history(config, note=config.note)
        return render_page(config, message="設定已儲存，並寫入 Site History")

    @app.get("/history/<int:index>")
    def load_history(index: int):
        history = service.load_history()
        if index < 0 or index >= len(history):
            return redirect(url_for("index"))
        record = history[index]
        config = DeviceConfig.from_dict(record.config.to_dict())
        config.note = record.note
        return render_page(config, message=f"已載入歷史紀錄：{record.saved_at}")

    return app


def main() -> None:
    create_app().run(debug=False)


if __name__ == "__main__":
    main()
