"""Flask web UI for the device parameter tool."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

from device_parameter_tool.models.device_config import DeviceConfig, LaneConfig, LidarConfig
from device_parameter_tool.services.config_service import ConfigService
from device_parameter_tool.services.lidar_calculator import calculate_for_config


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


def _parse_assigned_lanes(raw: str) -> list[int]:
    return [int(item.strip()) for item in raw.split(",") if item.strip()]


def _build_lane_rows(form, lane_count: int) -> list[LaneConfig]:
    lanes: list[LaneConfig] = []
    for index in range(lane_count):
        lanes.append(
            LaneConfig(
                lane_number=_coerce_int(form.get(f"lane_{index}_number"), index),
                width_mm=_coerce_float(form.get(f"lane_{index}_width_mm"), 0.0),
                lane_id=form.get(f"lane_{index}_id", "").strip(),
                description=form.get(f"lane_{index}_description", "").strip(),
            )
        )
    return lanes


def _build_lidar_rows(form, lidar_count: int) -> list[LidarConfig]:
    lidars: list[LidarConfig] = []
    for index in range(lidar_count):
        lidars.append(
            LidarConfig(
                lidar_id=form.get(f"lidar_{index}_id", "").strip(),
                assigned_lanes=_parse_assigned_lanes(form.get(f"lidar_{index}_assigned_lanes", "").strip()),
                center_distance_mm=_coerce_float(form.get(f"lidar_{index}_center_distance_mm"), 0.0),
                auto_calculate=_coerce_bool(form.get(f"lidar_{index}_auto_calculate")),
                description=form.get(f"lidar_{index}_description", "").strip(),
            )
        )
    return lidars


def _config_from_form(form) -> DeviceConfig:
    lane_count = _coerce_int(form.get("lane_count"), 1)
    lidar_count = _coerce_int(form.get("lidar_count"), 1)
    return DeviceConfig(
        site_name=form.get("site_name", "未命名點位").strip() or "未命名點位",
        note=form.get("note", ""),
        lanes=_build_lane_rows(form, lane_count),
        lidars=_build_lidar_rows(form, lidar_count),
    )


def _form_defaults(config: DeviceConfig) -> dict:
    lane_rows = [
        {
            "lane_id": lane.lane_id,
            "lane_number": lane.lane_number,
            "width_mm": lane.width_mm,
            "description": lane.description,
        }
        for lane in sorted(config.lanes, key=lambda item: item.lane_number)
    ]
    lidar_rows = [
        {
            "lidar_id": lidar.lidar_id,
            "assigned_lanes": ",".join(str(item) for item in lidar.assigned_lanes),
            "center_distance_mm": lidar.center_distance_mm,
            "auto_calculate": lidar.auto_calculate,
            "description": lidar.description,
        }
        for lidar in config.lidars
    ]
    return {
        "site_name": config.site_name,
        "note": config.note,
        "lane_count": max(1, len(lane_rows)),
        "lidar_count": max(1, len(lidar_rows)),
        "lanes": lane_rows or [{"lane_id": "", "lane_number": 0, "width_mm": "", "description": ""}],
        "lidars": lidar_rows or [{"lidar_id": "", "assigned_lanes": "", "center_distance_mm": "", "auto_calculate": True, "description": ""}],
    }


def create_app(data_dir: str | Path | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates")
    base_dir = Path(data_dir or "data")
    service = ConfigService(config_path=base_dir / "current_config.json", history_path=base_dir / "site_history.json")

    def render_page(config: DeviceConfig, message: str = "", error: str = ""):
        summary = None
        try:
            if config.lanes and config.lidars:
                summary = calculate_for_config(config)
        except ValueError as exc:
            error = str(exc)
        return render_template(
            "index.html",
            form=_form_defaults(config),
            summary=summary,
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
