import json
import os
import shutil
from typing import Dict, List, Optional

from src.main.python.models.device_config import (
    CameraConfig,
    DeviceConfig,
    HostConfig,
    LaneConfig,
    LidarConfig,
    LidarUnit,
    TriggerConditions,
)
from src.main.python.utils.validators import (
    validate_latitude,
    validate_log_level,
    validate_longitude,
    validate_non_negative_float,
    validate_orientation,
    validate_port,
    validate_positive_float,
    validate_positive_int,
    validate_transport,
)

_DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "resources",
    "config",
    "device_params.json",
)


class ConfigService:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = os.path.abspath(_DEFAULT_CONFIG_PATH)
        self.config_path = config_path
        self.config: DeviceConfig = DeviceConfig()

    def load_config(self) -> DeviceConfig:
        """Load configuration from JSON file."""
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.config = DeviceConfig.from_dict(data)
        return self.config

    def save_config(self) -> None:
        """Save configuration to JSON file (backs up existing file first)."""
        if os.path.exists(self.config_path):
            shutil.copy2(self.config_path, self.config_path + ".bak")
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config.to_dict(), f, ensure_ascii=False, indent=2)

    def validate_config(self) -> List[str]:
        """Validate all config values. Returns list of error messages."""
        errors = []
        for cam in self.config.cameras:
            try:
                validate_latitude(cam.latitude)
            except ValueError as e:
                errors.append(f"相機 {cam.camera_id}: {e}")
            try:
                validate_longitude(cam.longitude)
            except ValueError as e:
                errors.append(f"相機 {cam.camera_id}: {e}")
            try:
                validate_orientation(cam.orientation_degree)
            except ValueError as e:
                errors.append(f"相機 {cam.camera_id}: {e}")
            try:
                validate_positive_int(cam.fps)
            except ValueError as e:
                errors.append(f"相機 {cam.camera_id} FPS: {e}")

        for lane in self.config.lanes:
            try:
                validate_positive_float(lane.width)
            except ValueError as e:
                errors.append(f"車道 {lane.lane_id}: {e}")
            try:
                validate_positive_int(lane.lane_number)
            except ValueError as e:
                errors.append(f"車道 {lane.lane_id} 車道編號: {e}")

        for unit in self.config.lidars.units:
            try:
                validate_non_negative_float(unit.center_distance)
            except ValueError as e:
                errors.append(f"Lidar {unit.lidar_id} 中心點距離: {e}")
            try:
                validate_non_negative_float(unit.effective_left)
            except ValueError as e:
                errors.append(f"Lidar {unit.lidar_id} 往左有效區: {e}")
            try:
                validate_non_negative_float(unit.effective_right)
            except ValueError as e:
                errors.append(f"Lidar {unit.lidar_id} 往右有效區: {e}")
            if unit.lanes_covered < 1:
                errors.append(f"Lidar {unit.lidar_id}: 負責車道數必須 >= 1")

        if self.config.host:
            host = self.config.host
            try:
                validate_port(host.mqtt_port)
            except ValueError as e:
                errors.append(f"主機 MQTT Port: {e}")
            try:
                validate_positive_float(host.buffer_seconds)
            except ValueError as e:
                errors.append(f"主機 buffer_seconds: {e}")
            try:
                validate_positive_int(host.max_retries)
            except ValueError as e:
                errors.append(f"主機 max_retries: {e}")
            try:
                validate_log_level(host.log_level)
            except ValueError as e:
                errors.append(f"主機 log_level: {e}")
            try:
                validate_transport(host.rtsp_transport)
            except ValueError as e:
                errors.append(f"主機 rtsp_transport: {e}")

        return errors

    # ── Camera CRUD ──────────────────────────────────────────────────────────

    def get_camera(self, camera_id: str) -> Optional[CameraConfig]:
        for cam in self.config.cameras:
            if cam.camera_id == camera_id:
                return cam
        return None

    def add_camera(self, camera: CameraConfig) -> None:
        if self.get_camera(camera.camera_id):
            raise ValueError(f"相機 ID {camera.camera_id} 已存在")
        self.config.cameras.append(camera)

    def update_camera(self, camera_id: str, params: dict) -> CameraConfig:
        cam = self.get_camera(camera_id)
        if cam is None:
            raise ValueError(f"找不到相機 ID: {camera_id}")
        for key, value in params.items():
            if hasattr(cam, key):
                setattr(cam, key, value)
        return cam

    def delete_camera(self, camera_id: str) -> None:
        cam = self.get_camera(camera_id)
        if cam is None:
            raise ValueError(f"找不到相機 ID: {camera_id}")
        self.config.cameras.remove(cam)

    # ── Lane CRUD ────────────────────────────────────────────────────────────

    def get_lane(self, lane_id: str) -> Optional[LaneConfig]:
        for lane in self.config.lanes:
            if lane.lane_id == lane_id:
                return lane
        return None

    def add_lane(self, lane: LaneConfig) -> None:
        if self.get_lane(lane.lane_id):
            raise ValueError(f"車道 ID {lane.lane_id} 已存在")
        self.config.lanes.append(lane)

    def update_lane(self, lane_id: str, params: dict) -> LaneConfig:
        lane = self.get_lane(lane_id)
        if lane is None:
            raise ValueError(f"找不到車道 ID: {lane_id}")
        for key, value in params.items():
            if hasattr(lane, key):
                setattr(lane, key, value)
        return lane

    def delete_lane(self, lane_id: str) -> None:
        lane = self.get_lane(lane_id)
        if lane is None:
            raise ValueError(f"找不到車道 ID: {lane_id}")
        self.config.lanes.remove(lane)

    # ── Lidar CRUD ───────────────────────────────────────────────────────────

    def get_lidar(self, lidar_id: str) -> Optional[LidarUnit]:
        for unit in self.config.lidars.units:
            if unit.lidar_id == lidar_id:
                return unit
        return None

    def add_lidar(self, lidar: LidarUnit) -> None:
        if self.get_lidar(lidar.lidar_id):
            raise ValueError(f"Lidar ID {lidar.lidar_id} 已存在")
        self.config.lidars.units.append(lidar)

    def update_lidar(self, lidar_id: str, params: dict) -> LidarUnit:
        unit = self.get_lidar(lidar_id)
        if unit is None:
            raise ValueError(f"找不到 Lidar ID: {lidar_id}")
        for key, value in params.items():
            if hasattr(unit, key):
                setattr(unit, key, value)
        return unit

    def delete_lidar(self, lidar_id: str) -> None:
        unit = self.get_lidar(lidar_id)
        if unit is None:
            raise ValueError(f"找不到 Lidar ID: {lidar_id}")
        self.config.lidars.units.remove(unit)

    # ── Host ─────────────────────────────────────────────────────────────────

    def update_host(self, params: dict) -> HostConfig:
        if self.config.host is None:
            raise ValueError("主機設定不存在")
        host = self.config.host
        for key, value in params.items():
            if key == "trigger_conditions" and isinstance(value, dict):
                tc = host.trigger_conditions
                for k, v in value.items():
                    if hasattr(tc, k):
                        setattr(tc, k, v)
            elif hasattr(host, key):
                setattr(host, key, value)
        return host

    # ── Lidar auto-calculation ────────────────────────────────────────────────

    def calculate_lidar_effective_range(self, lidar_id: str) -> LidarUnit:
        """Calculate effective_left and effective_right from assigned lane widths."""
        unit = self.get_lidar(lidar_id)
        if unit is None:
            raise ValueError(f"找不到 Lidar ID: {lidar_id}")

        lane_map: Dict[str, LaneConfig] = {l.lane_id: l for l in self.config.lanes}
        total_width = 0.0
        for lid in unit.assigned_lanes:
            lane = lane_map.get(lid)
            if lane is None:
                raise ValueError(f"Lidar {lidar_id} 引用了不存在的車道 ID: {lid}")
            total_width += lane.width

        unit.effective_left = (total_width / 2) + unit.offset_distance
        unit.effective_right = (total_width / 2) - unit.offset_distance
        return unit

    def recalculate_all_lidars(self) -> List[str]:
        """Recalculate effective range for all lidars with auto_calculate=True."""
        updated = []
        for unit in self.config.lidars.units:
            if unit.auto_calculate:
                self.calculate_lidar_effective_range(unit.lidar_id)
                updated.append(unit.lidar_id)
        return updated

    # ── Import / Export ───────────────────────────────────────────────────────

    def export_config(self, filepath: str) -> None:
        """Export current config to a specified file path."""
        dirpath = os.path.dirname(os.path.abspath(filepath))
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.config.to_dict(), f, ensure_ascii=False, indent=2)

    def import_config(self, filepath: str) -> DeviceConfig:
        """Import config from a specified file path."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.config = DeviceConfig.from_dict(data)
        return self.config
