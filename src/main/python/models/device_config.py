from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class CameraConfig:
    camera_id: str
    name: str
    latitude: float
    longitude: float
    orientation_degree: float
    orientation_label: str
    resolution: str
    fps: int
    exposure: str
    white_balance: str
    gain: float
    shutter_speed: str
    rtsp_url: str
    custom_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "orientation_degree": self.orientation_degree,
            "orientation_label": self.orientation_label,
            "resolution": self.resolution,
            "fps": self.fps,
            "exposure": self.exposure,
            "white_balance": self.white_balance,
            "gain": self.gain,
            "shutter_speed": self.shutter_speed,
            "rtsp_url": self.rtsp_url,
            "custom_params": self.custom_params,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CameraConfig":
        return cls(
            camera_id=data["camera_id"],
            name=data["name"],
            latitude=data["latitude"],
            longitude=data["longitude"],
            orientation_degree=data["orientation_degree"],
            orientation_label=data["orientation_label"],
            resolution=data["resolution"],
            fps=data["fps"],
            exposure=data["exposure"],
            white_balance=data["white_balance"],
            gain=data["gain"],
            shutter_speed=data["shutter_speed"],
            rtsp_url=data["rtsp_url"],
            custom_params=data.get("custom_params", {}),
        )


@dataclass
class LaneConfig:
    lane_id: str
    lane_number: int
    width: float
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "lane_id": self.lane_id,
            "lane_number": self.lane_number,
            "width": self.width,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LaneConfig":
        return cls(
            lane_id=data["lane_id"],
            lane_number=data["lane_number"],
            width=data["width"],
            description=data.get("description", ""),
        )


@dataclass
class LidarUnit:
    lidar_id: str
    assigned_lanes: List[str]
    offset_distance: float
    center_distance: float
    effective_left: float
    effective_right: float
    auto_calculate: bool = True
    description: str = ""

    @property
    def lanes_covered(self) -> int:
        return len(self.assigned_lanes)

    def to_dict(self) -> dict:
        return {
            "lidar_id": self.lidar_id,
            "assigned_lanes": self.assigned_lanes,
            "lanes_covered": self.lanes_covered,
            "offset_distance": self.offset_distance,
            "center_distance": self.center_distance,
            "effective_left": self.effective_left,
            "effective_right": self.effective_right,
            "auto_calculate": self.auto_calculate,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LidarUnit":
        return cls(
            lidar_id=data["lidar_id"],
            assigned_lanes=data.get("assigned_lanes", []),
            offset_distance=data["offset_distance"],
            center_distance=data["center_distance"],
            effective_left=data["effective_left"],
            effective_right=data["effective_right"],
            auto_calculate=data.get("auto_calculate", True),
            description=data.get("description", ""),
        )


@dataclass
class LidarConfig:
    units: List[LidarUnit] = field(default_factory=list)

    @property
    def lidar_count(self) -> int:
        return len(self.units)

    def to_dict(self) -> dict:
        return {
            "lidar_count": self.lidar_count,
            "units": [u.to_dict() for u in self.units],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LidarConfig":
        units = [LidarUnit.from_dict(u) for u in data.get("units", [])]
        return cls(units=units)


@dataclass
class TriggerConditions:
    topic_contains: str = ""
    source: str = ""
    state: str = ""

    def to_dict(self) -> dict:
        return {
            "topic_contains": self.topic_contains,
            "source": self.source,
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TriggerConditions":
        return cls(
            topic_contains=data.get("topic_contains", ""),
            source=data.get("source", ""),
            state=data.get("state", ""),
        )


@dataclass
class HostConfig:
    mqtt_ip: str
    mqtt_port: int
    mqtt_timeout: int
    rtsp_transport: str
    save_root: str
    buffer_seconds: float
    max_retries: int
    log_level: str
    log_dir: str
    trigger_topic: str
    trigger_conditions: TriggerConditions = field(default_factory=TriggerConditions)

    def to_dict(self) -> dict:
        return {
            "mqtt_ip": self.mqtt_ip,
            "mqtt_port": self.mqtt_port,
            "mqtt_timeout": self.mqtt_timeout,
            "rtsp_transport": self.rtsp_transport,
            "save_root": self.save_root,
            "buffer_seconds": self.buffer_seconds,
            "max_retries": self.max_retries,
            "log_level": self.log_level,
            "log_dir": self.log_dir,
            "trigger_topic": self.trigger_topic,
            "trigger_conditions": self.trigger_conditions.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HostConfig":
        tc_data = data.get("trigger_conditions", {})
        return cls(
            mqtt_ip=data["mqtt_ip"],
            mqtt_port=data["mqtt_port"],
            mqtt_timeout=data["mqtt_timeout"],
            rtsp_transport=data["rtsp_transport"],
            save_root=data["save_root"],
            buffer_seconds=data["buffer_seconds"],
            max_retries=data["max_retries"],
            log_level=data["log_level"],
            log_dir=data["log_dir"],
            trigger_topic=data["trigger_topic"],
            trigger_conditions=TriggerConditions.from_dict(tc_data),
        )


@dataclass
class DeviceConfig:
    cameras: List[CameraConfig] = field(default_factory=list)
    lanes: List[LaneConfig] = field(default_factory=list)
    lidars: LidarConfig = field(default_factory=LidarConfig)
    host: Optional[HostConfig] = None

    def to_dict(self) -> dict:
        return {
            "cameras": [c.to_dict() for c in self.cameras],
            "lanes": [l.to_dict() for l in self.lanes],
            "lidars": self.lidars.to_dict(),
            "host": self.host.to_dict() if self.host else {},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DeviceConfig":
        cameras = [CameraConfig.from_dict(c) for c in data.get("cameras", [])]
        lanes = [LaneConfig.from_dict(l) for l in data.get("lanes", [])]
        lidars = LidarConfig.from_dict(data.get("lidars", {}))
        host_data = data.get("host")
        host = HostConfig.from_dict(host_data) if host_data else None
        return cls(cameras=cameras, lanes=lanes, lidars=lidars, host=host)
