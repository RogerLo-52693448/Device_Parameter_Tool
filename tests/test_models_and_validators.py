import pytest

from device_parameter_tool.models.device_config import DeviceConfig
from device_parameter_tool.services.config_service import ConfigService
from device_parameter_tool.utils.validators import validate_lidar_assignment, validate_port


def sample_config(note: str = "測試備註") -> DeviceConfig:
    return DeviceConfig.from_dict(
        {
            "site_name": "03F-040.7N",
            "note": note,
            "has_backup": True,
            "camera": {
                "camera_id": "CAM-01",
                "name": "主攝影機",
                "latitude": 25.1,
                "longitude": 121.6,
                "orientation_deg": 90.0,
                "orientation_label": "東向",
                "resolution": "1920x1080",
                "fps": 30,
                "exposure": "auto",
                "white_balance": "auto",
                "gain": 1.0,
                "shutter_speed": "auto",
                "rtsp_url": "rtsp://192.168.0.10/stream",
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
            "backup_lidars": [
                {"assigned_lanes": [0, 1], "center_distance_mm": 3650.0},
            ],
            "host": {
                "ip": "192.168.0.20",
                "port": 8080,
                "log_level": "INFO",
                "mqtt_ip": "192.168.0.21",
                "mqtt_port": 1883,
                "mqtt_timeout": 60,
                "rtsp_transport": "tcp",
                "save_root": "./captures",
                "buffer_seconds": 3.5,
                "max_retries": 5,
                "log_dir": "./logs",
                "trigger_topic": "site/event",
                "trigger_conditions": {
                    "topic_contains": "incident",
                    "source": "radar",
                    "state": "active",
                },
            },
        }
    )


def test_device_config_round_trip_serialization():
    config = sample_config()

    restored = DeviceConfig.from_dict(config.to_dict())

    assert restored.to_dict() == config.to_dict()
    assert restored.note == "測試備註"
    assert restored.camera.camera_id == "CAM-01"
    assert restored.host.mqtt_ip == "192.168.0.21"
    assert restored.has_backup is True
    assert restored.backup_lidars[0].center_distance_mm == 3650.0


def test_legacy_model_shape_is_supported():
    config = DeviceConfig.from_dict(
        {
            "site_name": "legacy-site",
            "cameras": [
                {
                    "camera_id": "OLD-CAM",
                    "name": "舊版攝影機",
                    "latitude": 25.0,
                    "longitude": 121.0,
                    "orientation_degree": 45.0,
                    "orientation_label": "NE",
                    "resolution": "1280x720",
                    "fps": 25,
                    "exposure": "manual",
                    "white_balance": "auto",
                    "gain": 2.0,
                    "shutter_speed": "1/120",
                    "rtsp_url": "rtsp://legacy",
                    "ip": "192.168.10.10",
                    "port": 554,
                    "protocol": "rtsp",
                }
            ],
            "lanes": [
                {"lane_id": "Lane-A", "lane_number": 0, "width": 3500.0},
                {"lane_id": "Lane-B", "lane_number": 1, "width": 3400.0},
            ],
            "lidars": {
                "units": [
                    {
                        "lidar_id": "OLD-LD",
                        "assigned_lanes": ["0", "1"],
                        "offset_distance": 0.0,
                        "center_distance": 3600.0,
                        "effective_left": 0.0,
                        "effective_right": 0.0,
                        "auto_calculate": True,
                    }
                ]
            },
            "host": {
                "mqtt_ip": "192.168.10.20",
                "mqtt_port": 1883,
                "mqtt_timeout": 30,
                "rtsp_transport": "tcp",
                "save_root": "./legacy",
                "buffer_seconds": 2.0,
                "max_retries": 3,
                "log_level": "INFO",
                "log_dir": "./legacy-logs",
                "trigger_topic": "legacy/topic",
                "trigger_conditions": {"topic_contains": "x", "source": "y", "state": "z"},
            },
            "has_backup": True,
            "backup_lidar_assignments": [[0, 1]],
            "backup_lidar_centers": [3700.0],
        }
    )

    assert config.camera.name == "舊版攝影機"
    assert config.camera.orientation_deg == 45.0
    assert config.lanes[0].width_mm == 3500.0
    assert config.lidars[0].assigned_lanes == [0, 1]
    assert config.host.mqtt_port == 1883
    assert config.has_backup is True
    assert config.backup_lidars[0].assigned_lanes == [0, 1]


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
