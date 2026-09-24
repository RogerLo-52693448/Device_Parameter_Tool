import pytest

from device_parameter_tool.models.device_config import DeviceConfig
from device_parameter_tool.services.config_service import ConfigService
from device_parameter_tool.utils.validators import validate_lidar_assignment, validate_port


def sample_config(note: str = "測試備註") -> DeviceConfig:
    return DeviceConfig.from_dict(
        {
            "site_name": "03F-040.7N",
            "note": note,
            "camera": {
                "latitude": 25.1,
                "longitude": 121.6,
                "orientation_deg": 90.0,
                "ip": "192.168.0.10",
                "port": 554,
                "protocol": "rtsp",
            },
            "lanes": [
                {"lane_number": 0, "width_mm": 3500.0},
                {"lane_number": 1, "width_mm": 3300.0},
            ],
            "lidars": [
                {"assigned_lanes": [0, 1], "center_distance_mm": 3600.0},
            ],
            "host": {
                "ip": "192.168.0.20",
                "port": 8080,
                "log_level": "INFO",
            },
        }
    )


def test_device_config_round_trip_serialization():
    config = sample_config()

    restored = DeviceConfig.from_dict(config.to_dict())

    assert restored.to_dict() == config.to_dict()
    assert restored.note == "測試備註"


def test_save_config_creates_backup(tmp_path):
    service = ConfigService(config_path=tmp_path / "config.json", history_path=tmp_path / "history.json")
    first = sample_config("第一次")
    second = sample_config("第二次")

    service.save_config(first)
    service.save_config(second)

    backup_path = tmp_path / "config.json.bak"
    assert backup_path.exists()
    assert "第一次" in backup_path.read_text(encoding="utf-8")


def test_validate_port_and_lidar_assignment_errors():
    with pytest.raises(ValueError):
        validate_port(70000)

    with pytest.raises(ValueError):
        validate_lidar_assignment([0, 2], {0, 1, 2})
