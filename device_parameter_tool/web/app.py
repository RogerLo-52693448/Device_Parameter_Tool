"""Flask web UI for the device parameter tool."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

from device_parameter_tool.models.device_config import CameraConfig, DeviceConfig, HostConfig, LaneConfig, LidarConfig
from device_parameter_tool.services.config_service import ConfigService
from device_parameter_tool.services.lidar_calculator import calculate_for_config


def _parse_lanes(raw: str) -> list[LaneConfig]:
    lanes: list[LaneConfig] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        lane_number, width = [item.strip() for item in line.split(",", maxsplit=1)]
        lanes.append(LaneConfig(lane_number=int(lane_number), width_mm=float(width)))
    return lanes


def _parse_lidars(raw: str) -> list[LidarConfig]:
    lidars: list[LidarConfig] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        lane_part, center = [item.strip() for item in line.split(":", maxsplit=1)]
        assigned_lanes = [int(item.strip()) for item in lane_part.split(",") if item.strip()]
        lidars.append(LidarConfig(assigned_lanes=assigned_lanes, center_distance_mm=float(center)))
    return lidars


def _config_from_form(form) -> DeviceConfig:
    return DeviceConfig(
        site_name=form.get("site_name", "未命名點位").strip() or "未命名點位",
        note=form.get("note", ""),
        camera=CameraConfig(
            latitude=float(form.get("camera_latitude", 0) or 0),
            longitude=float(form.get("camera_longitude", 0) or 0),
            orientation_deg=float(form.get("camera_orientation_deg", 0) or 0),
            ip=form.get("camera_ip", "127.0.0.1"),
            port=int(form.get("camera_port", 554) or 554),
            protocol=form.get("camera_protocol", "rtsp"),
        ),
        lanes=_parse_lanes(form.get("lanes", "")),
        lidars=_parse_lidars(form.get("lidars", "")),
        host=HostConfig(
            ip=form.get("host_ip", "127.0.0.1"),
            port=int(form.get("host_port", 8080) or 8080),
            log_level=form.get("host_log_level", "INFO"),
        ),
    )


def _form_defaults(config: DeviceConfig) -> dict[str, str | int | float]:
    return {
        "site_name": config.site_name,
        "note": config.note,
        "camera_latitude": config.camera.latitude,
        "camera_longitude": config.camera.longitude,
        "camera_orientation_deg": config.camera.orientation_deg,
        "camera_ip": config.camera.ip,
        "camera_port": config.camera.port,
        "camera_protocol": config.camera.protocol,
        "lanes": "\n".join(f"{lane.lane_number},{lane.width_mm}" for lane in sorted(config.lanes, key=lambda item: item.lane_number)),
        "lidars": "\n".join(
            f"{','.join(str(lane) for lane in lidar.assigned_lanes)}:{lidar.center_distance_mm}"
            for lidar in config.lidars
        ),
        "host_ip": config.host.ip,
        "host_port": config.host.port,
        "host_log_level": config.host.log_level,
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
    create_app().run(debug=True)


if __name__ == "__main__":
    main()
