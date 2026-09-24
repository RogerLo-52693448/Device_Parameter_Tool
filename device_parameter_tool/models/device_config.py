"""Data models for site device configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from device_parameter_tool.utils.validators import (
    validate_ip,
    validate_lidar_assignment,
    validate_log_level,
    validate_non_negative_number,
    validate_port,
    validate_positive_number,
    validate_protocol,
)


@dataclass(slots=True)
class CameraConfig:
    latitude: float = 0.0
    longitude: float = 0.0
    orientation_deg: float = 0.0
    ip: str = "127.0.0.1"
    port: int = 554
    protocol: str = "rtsp"

    def validate(self) -> None:
        validate_ip(self.ip, "Camera IP")
        validate_port(self.port, "Camera Port")
        validate_protocol(self.protocol)


@dataclass(slots=True)
class LaneConfig:
    lane_number: int
    width_mm: float

    def validate(self) -> None:
        if self.lane_number < 0:
            raise ValueError("車道編號不可為負數")
        validate_positive_number(self.width_mm, f"Lane{self.lane_number} 寬度")


@dataclass(slots=True)
class LidarConfig:
    assigned_lanes: list[int] = field(default_factory=list)
    center_distance_mm: float = 0.0

    def validate(self, available_lane_numbers: set[int]) -> None:
        self.assigned_lanes = validate_lidar_assignment(self.assigned_lanes, available_lane_numbers)
        validate_non_negative_number(self.center_distance_mm, "Lidar 中心點距離")


@dataclass(slots=True)
class HostConfig:
    ip: str = "127.0.0.1"
    port: int = 8080
    log_level: str = "INFO"

    def validate(self) -> None:
        validate_ip(self.ip, "Host IP")
        validate_port(self.port, "Host Port")
        self.log_level = validate_log_level(self.log_level)


@dataclass(slots=True)
class DeviceConfig:
    site_name: str = "未命名點位"
    note: str = ""
    camera: CameraConfig = field(default_factory=CameraConfig)
    lanes: list[LaneConfig] = field(default_factory=list)
    lidars: list[LidarConfig] = field(default_factory=list)
    host: HostConfig = field(default_factory=HostConfig)

    def validate(self) -> None:
        self.camera.validate()
        self.host.validate()
        seen_lane_numbers: set[int] = set()
        for lane in self.lanes:
            lane.validate()
            if lane.lane_number in seen_lane_numbers:
                raise ValueError(f"車道編號重複: Lane{lane.lane_number}")
            seen_lane_numbers.add(lane.lane_number)
        if not self.lanes:
            raise ValueError("至少需要 1 個車道")
        for lidar in self.lidars:
            lidar.validate(seen_lane_numbers)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeviceConfig":
        config = cls(
            site_name=data.get("site_name", "未命名點位"),
            note=data.get("note", ""),
            camera=CameraConfig(**data.get("camera", {})),
            lanes=[LaneConfig(**lane) for lane in data.get("lanes", [])],
            lidars=[LidarConfig(**lidar) for lidar in data.get("lidars", [])],
            host=HostConfig(**data.get("host", {})),
        )
        config.validate()
        return config
