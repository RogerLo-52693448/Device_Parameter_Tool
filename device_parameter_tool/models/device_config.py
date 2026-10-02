"""Data models for site device configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from device_parameter_tool.utils.validators import (
    inner_outer_from_physical_slots,
    physical_slots_from_inner_outer,
    validate_ip,
    validate_lidar_assignment,
    validate_lidar_label_start,
    validate_lidar_lane_slots,
    validate_log_level,
    validate_non_negative_number,
    validate_port,
    validate_positive_number,
    validate_protocol,
    validate_site_name,
    validate_traffic_mode,
)


def _parse_lane_reference(value: int | str) -> int:
    if isinstance(value, int):
        return value
    normalized = value.strip()
    if normalized.lower().startswith("lane"):
        normalized = normalized[4:]
    if normalized.startswith("_"):
        normalized = normalized[1:]
    return int(normalized)


@dataclass(slots=True)
class CameraConfig:
    camera_id: str = "CAM-01"
    name: str = "Camera 1"
    latitude: float = 0.0
    longitude: float = 0.0
    orientation_deg: float = 0.0
    orientation_label: str = ""
    resolution: str = "1920x1080"
    fps: int = 30
    exposure: str = "auto"
    white_balance: str = "auto"
    gain: float = 1.0
    shutter_speed: str = "auto"
    rtsp_url: str = ""
    ip: str = "127.0.0.1"
    port: int = 554
    protocol: str = "rtsp"
    custom_params: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        validate_ip(self.ip, "Camera IP")
        validate_port(self.port, "Camera Port")
        validate_protocol(self.protocol)
        if self.fps <= 0:
            raise ValueError("Camera FPS 必須大於 0")
        if self.gain < 0:
            raise ValueError("Camera gain 不可為負數")


@dataclass(slots=True)
class LaneConfig:
    lane_number: int
    width_mm: float
    lane_id: str = ""
    description: str = ""

    @property
    def width(self) -> float:
        return self.width_mm

    def validate(self) -> None:
        if self.lane_number < 0:
            raise ValueError("車道編號不可為負數")
        validate_positive_number(self.width_mm, f"Lane{self.lane_number} 寬度")


@dataclass(slots=True)
class LidarConfig:
    assigned_lanes: list[int] = field(default_factory=list)
    center_distance_mm: float = 0.0
    inner_lane: int | None = None
    outer_lane: int | None = None
    right_lane: int | None = None
    left_lane: int | None = None
    lidar_id: str = ""
    offset_distance_mm: float = 0.0
    effective_left_mm: float = 0.0
    effective_right_mm: float = 0.0
    auto_calculate: bool = True
    description: str = ""

    def sync_lane_slots(self, traffic_mode: str = "inner_from_right") -> None:
        normalized = validate_lidar_assignment(self.assigned_lanes, set(self.assigned_lanes)) if self.assigned_lanes else []
        validate_traffic_mode(traffic_mode)
        if self.inner_lane is None and self.outer_lane is None:
            if self.right_lane is not None or self.left_lane is not None:
                self.inner_lane, self.outer_lane = inner_outer_from_physical_slots(
                    self.right_lane,
                    self.left_lane,
                    traffic_mode,
                )
            else:
                self.inner_lane = normalized[0] if normalized else None
                self.outer_lane = normalized[1] if len(normalized) > 1 else None
        self.assigned_lanes = [lane for lane in (self.inner_lane, self.outer_lane) if lane is not None] or normalized
        self.right_lane, self.left_lane = physical_slots_from_inner_outer(
            self.inner_lane,
            self.outer_lane,
            traffic_mode,
        )

    def validate(self, available_lane_numbers: set[int] | list[int], traffic_mode: str = "inner_from_right") -> None:
        self.sync_lane_slots(traffic_mode)
        self.inner_lane, self.outer_lane, self.assigned_lanes = validate_lidar_lane_slots(
            self.inner_lane,
            self.outer_lane,
            available_lane_numbers,
        )
        self.right_lane, self.left_lane = physical_slots_from_inner_outer(
            self.inner_lane,
            self.outer_lane,
            traffic_mode,
        )
        validate_non_negative_number(self.center_distance_mm, "Lidar 中心點距離")
        validate_non_negative_number(self.offset_distance_mm, "Lidar 偏差值")
        validate_non_negative_number(self.effective_left_mm, "Lidar 有效左側範圍")
        validate_non_negative_number(self.effective_right_mm, "Lidar 有效右側範圍")


@dataclass(slots=True)
class TriggerConditions:
    topic_contains: str = ""
    source: str = ""
    state: str = ""


@dataclass(slots=True)
class HostConfig:
    ip: str = "127.0.0.1"
    port: int = 8080
    log_level: str = "INFO"
    mqtt_ip: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_timeout: int = 60
    rtsp_transport: str = "tcp"
    save_root: str = "./data"
    buffer_seconds: float = 3.0
    max_retries: int = 3
    log_dir: str = "./logs"
    trigger_topic: str = ""
    trigger_conditions: TriggerConditions = field(default_factory=TriggerConditions)

    def validate(self) -> None:
        validate_ip(self.ip, "Host IP")
        validate_port(self.port, "Host Port")
        self.log_level = validate_log_level(self.log_level)
        validate_ip(self.mqtt_ip, "MQTT IP")
        validate_port(self.mqtt_port, "MQTT Port")
        if self.mqtt_timeout < 0:
            raise ValueError("MQTT timeout 不可為負數")
        if self.buffer_seconds < 0:
            raise ValueError("buffer seconds 不可為負數")
        if self.max_retries < 0:
            raise ValueError("max retries 不可為負數")


@dataclass(slots=True)
class DeviceConfig:
    site_name: str = "未命名點位"
    note: str = ""
    has_backup: bool = False
    traffic_mode: str = "inner_from_right"
    lidar_label_start: int = 0
    camera: CameraConfig = field(default_factory=CameraConfig)
    lanes: list[LaneConfig] = field(default_factory=list)
    lidars: list[LidarConfig] = field(default_factory=list)
    backup_lidars: list[LidarConfig] = field(default_factory=list)
    host: HostConfig = field(default_factory=HostConfig)

    def validate(self) -> None:
        self.site_name = validate_site_name(self.site_name)
        self.traffic_mode = validate_traffic_mode(self.traffic_mode)
        self.lidar_label_start = validate_lidar_label_start(self.lidar_label_start)
        if not self.has_backup:
            self.backup_lidars = []
        self.camera.validate()
        self.host.validate()
        seen_lane_numbers: set[int] = set()
        ordered_lane_numbers: list[int] = []
        for lane in self.lanes:
            lane.validate()
            if lane.lane_number in seen_lane_numbers:
                raise ValueError(f"車道編號重複: Lane{lane.lane_number}")
            seen_lane_numbers.add(lane.lane_number)
            ordered_lane_numbers.append(lane.lane_number)
        if not self.lanes:
            raise ValueError("至少需要 1 個車道")
        for lidar in self.lidars:
            lidar.validate(sorted(ordered_lane_numbers), self.traffic_mode)
        for lidar in self.backup_lidars:
            lidar.validate(sorted(ordered_lane_numbers), self.traffic_mode)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeviceConfig":
        camera_payload = data.get("camera")
        if camera_payload is None:
            cameras_payload = data.get("cameras", [])
            camera_payload = cameras_payload[0] if cameras_payload else {}
        host_payload = data.get("host", {})
        lanes_payload = data.get("lanes", [])
        lidars_payload = data.get("lidars", [])
        if isinstance(lidars_payload, dict):
            lidars_payload = lidars_payload.get("units", [])
        backup_lidars_payload = data.get("backup_lidars", [])
        if isinstance(backup_lidars_payload, dict):
            backup_lidars_payload = backup_lidars_payload.get("units", [])
        if not backup_lidars_payload and data.get("backup_lidar_assignments"):
            backup_lidars_payload = [
                {
                    "assigned_lanes": assigned,
                    "center_distance": center,
                    "auto_calculate": True,
                }
                for assigned, center in zip(
                    data.get("backup_lidar_assignments", []),
                    data.get("backup_lidar_centers", []),
                )
            ]

        config = cls(
            site_name=data.get("site_name", "未命名點位"),
            note=data.get("note", ""),
            has_backup=bool(data.get("has_backup", bool(backup_lidars_payload))),
            traffic_mode=data.get("traffic_mode", "inner_from_right"),
            lidar_label_start=data.get("lidar_label_start", 0),
            camera=CameraConfig(
                camera_id=camera_payload.get("camera_id", "CAM-01"),
                name=camera_payload.get("name", "Camera 1"),
                latitude=camera_payload.get("latitude", 0.0),
                longitude=camera_payload.get("longitude", 0.0),
                orientation_deg=camera_payload.get("orientation_deg", camera_payload.get("orientation_degree", 0.0)),
                orientation_label=camera_payload.get("orientation_label", ""),
                resolution=camera_payload.get("resolution", "1920x1080"),
                fps=camera_payload.get("fps", 30),
                exposure=camera_payload.get("exposure", "auto"),
                white_balance=camera_payload.get("white_balance", "auto"),
                gain=camera_payload.get("gain", 1.0),
                shutter_speed=camera_payload.get("shutter_speed", "auto"),
                rtsp_url=camera_payload.get("rtsp_url", ""),
                ip=camera_payload.get("ip", "127.0.0.1"),
                port=camera_payload.get("port", 554),
                protocol=camera_payload.get("protocol", "rtsp"),
                custom_params=camera_payload.get("custom_params", {}),
            ),
            lanes=[
                LaneConfig(
                    lane_number=lane["lane_number"],
                    width_mm=lane.get("width_mm", lane.get("width", 0.0)),
                    lane_id=lane.get("lane_id", ""),
                    description=lane.get("description", ""),
                )
                for lane in lanes_payload
            ],
            lidars=[
                LidarConfig(
                    assigned_lanes=[_parse_lane_reference(item) for item in lidar.get("assigned_lanes", [])],
                    inner_lane=_parse_lane_reference(lidar["inner_lane"]) if lidar.get("inner_lane") is not None else None,
                    outer_lane=_parse_lane_reference(lidar["outer_lane"]) if lidar.get("outer_lane") is not None else None,
                    right_lane=_parse_lane_reference(lidar["right_lane"]) if lidar.get("right_lane") is not None else None,
                    left_lane=_parse_lane_reference(lidar["left_lane"]) if lidar.get("left_lane") is not None else None,
                    center_distance_mm=lidar.get("center_distance_mm", lidar.get("center_distance", 0.0)),
                    lidar_id=lidar.get("lidar_id", ""),
                    offset_distance_mm=lidar.get("offset_distance_mm", lidar.get("offset_distance", 0.0)),
                    effective_left_mm=lidar.get("effective_left_mm", lidar.get("effective_left", 0.0)),
                    effective_right_mm=lidar.get("effective_right_mm", lidar.get("effective_right", 0.0)),
                    auto_calculate=lidar.get("auto_calculate", True),
                    description=lidar.get("description", ""),
                )
                for lidar in lidars_payload
            ],
            backup_lidars=[
                LidarConfig(
                    assigned_lanes=[_parse_lane_reference(item) for item in lidar.get("assigned_lanes", [])],
                    inner_lane=_parse_lane_reference(lidar["inner_lane"]) if lidar.get("inner_lane") is not None else None,
                    outer_lane=_parse_lane_reference(lidar["outer_lane"]) if lidar.get("outer_lane") is not None else None,
                    right_lane=_parse_lane_reference(lidar["right_lane"]) if lidar.get("right_lane") is not None else None,
                    left_lane=_parse_lane_reference(lidar["left_lane"]) if lidar.get("left_lane") is not None else None,
                    center_distance_mm=lidar.get("center_distance_mm", lidar.get("center_distance", 0.0)),
                    lidar_id=lidar.get("lidar_id", ""),
                    offset_distance_mm=lidar.get("offset_distance_mm", lidar.get("offset_distance", 0.0)),
                    effective_left_mm=lidar.get("effective_left_mm", lidar.get("effective_left", 0.0)),
                    effective_right_mm=lidar.get("effective_right_mm", lidar.get("effective_right", 0.0)),
                    auto_calculate=lidar.get("auto_calculate", True),
                    description=lidar.get("description", ""),
                )
                for lidar in backup_lidars_payload
            ],
            host=HostConfig(
                ip=host_payload.get("ip", "127.0.0.1"),
                port=host_payload.get("port", 8080),
                log_level=host_payload.get("log_level", "INFO"),
                mqtt_ip=host_payload.get("mqtt_ip", "127.0.0.1"),
                mqtt_port=host_payload.get("mqtt_port", 1883),
                mqtt_timeout=host_payload.get("mqtt_timeout", 60),
                rtsp_transport=host_payload.get("rtsp_transport", "tcp"),
                save_root=host_payload.get("save_root", "./data"),
                buffer_seconds=host_payload.get("buffer_seconds", 3.0),
                max_retries=host_payload.get("max_retries", 3),
                log_dir=host_payload.get("log_dir", "./logs"),
                trigger_topic=host_payload.get("trigger_topic", ""),
                trigger_conditions=TriggerConditions(**host_payload.get("trigger_conditions", {})),
            ),
        )
        config.validate()
        for lidar in config.lidars:
            lidar.sync_lane_slots(config.traffic_mode)
        for lidar in config.backup_lidars:
            lidar.sync_lane_slots(config.traffic_mode)
        return config
