"""Flask web UI for the device parameter tool."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

from device_parameter_tool.models.device_config import CameraConfig, DeviceConfig, HostConfig, LaneConfig, LidarConfig, TriggerConditions
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
        camera=CameraConfig(
            camera_id=form.get("camera_id", "CAM-01").strip() or "CAM-01",
            name=form.get("camera_name", "Camera 1").strip() or "Camera 1",
            latitude=_coerce_float(form.get("camera_latitude"), 0.0),
            longitude=_coerce_float(form.get("camera_longitude"), 0.0),
            orientation_deg=_coerce_float(form.get("camera_orientation_deg"), 0.0),
            orientation_label=form.get("camera_orientation_label", "").strip(),
            resolution=form.get("camera_resolution", "1920x1080").strip() or "1920x1080",
            fps=_coerce_int(form.get("camera_fps"), 30),
            exposure=form.get("camera_exposure", "auto").strip() or "auto",
            white_balance=form.get("camera_white_balance", "auto").strip() or "auto",
            gain=_coerce_float(form.get("camera_gain"), 1.0),
            shutter_speed=form.get("camera_shutter_speed", "auto").strip() or "auto",
            rtsp_url=form.get("camera_rtsp_url", "").strip(),
            ip=form.get("camera_ip", "127.0.0.1").strip() or "127.0.0.1",
            port=_coerce_int(form.get("camera_port"), 554),
            protocol=form.get("camera_protocol", "rtsp").strip() or "rtsp",
        ),
        lanes=_build_lane_rows(form, lane_count),
        lidars=_build_lidar_rows(form, lidar_count),
        host=HostConfig(
            ip=form.get("host_ip", "127.0.0.1").strip() or "127.0.0.1",
            port=_coerce_int(form.get("host_port"), 8080),
            log_level=form.get("host_log_level", "INFO").strip() or "INFO",
            mqtt_ip=form.get("host_mqtt_ip", "127.0.0.1").strip() or "127.0.0.1",
            mqtt_port=_coerce_int(form.get("host_mqtt_port"), 1883),
            mqtt_timeout=_coerce_int(form.get("host_mqtt_timeout"), 60),
            rtsp_transport=form.get("host_rtsp_transport", "tcp").strip() or "tcp",
            save_root=form.get("host_save_root", "./data").strip() or "./data",
            buffer_seconds=_coerce_float(form.get("host_buffer_seconds"), 3.0),
            max_retries=_coerce_int(form.get("host_max_retries"), 3),
            log_dir=form.get("host_log_dir", "./logs").strip() or "./logs",
            trigger_topic=form.get("host_trigger_topic", "").strip(),
            trigger_conditions=TriggerConditions(
                topic_contains=form.get("host_trigger_topic_contains", "").strip(),
                source=form.get("host_trigger_source", "").strip(),
                state=form.get("host_trigger_state", "").strip(),
            ),
        ),
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
        "camera": {
            "camera_id": config.camera.camera_id,
            "name": config.camera.name,
            "latitude": config.camera.latitude,
            "longitude": config.camera.longitude,
            "orientation_deg": config.camera.orientation_deg,
            "orientation_label": config.camera.orientation_label,
            "resolution": config.camera.resolution,
            "fps": config.camera.fps,
            "exposure": config.camera.exposure,
            "white_balance": config.camera.white_balance,
            "gain": config.camera.gain,
            "shutter_speed": config.camera.shutter_speed,
            "rtsp_url": config.camera.rtsp_url,
            "ip": config.camera.ip,
            "port": config.camera.port,
            "protocol": config.camera.protocol,
        },
        "lanes": lane_rows or [{"lane_id": "", "lane_number": 0, "width_mm": "", "description": ""}],
        "lidars": lidar_rows or [{"lidar_id": "", "assigned_lanes": "", "center_distance_mm": "", "auto_calculate": True, "description": ""}],
        "host": {
            "ip": config.host.ip,
            "port": config.host.port,
            "log_level": config.host.log_level,
            "mqtt_ip": config.host.mqtt_ip,
            "mqtt_port": config.host.mqtt_port,
            "mqtt_timeout": config.host.mqtt_timeout,
            "rtsp_transport": config.host.rtsp_transport,
            "save_root": config.host.save_root,
            "buffer_seconds": config.host.buffer_seconds,
            "max_retries": config.host.max_retries,
            "log_dir": config.host.log_dir,
            "trigger_topic": config.host.trigger_topic,
            "trigger_topic_contains": config.host.trigger_conditions.topic_contains,
            "trigger_source": config.host.trigger_conditions.source,
            "trigger_state": config.host.trigger_conditions.state,
        },
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
