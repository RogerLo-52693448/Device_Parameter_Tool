import json
import os
import tempfile

import pytest

from src.main.python.models.device_config import (
    CameraConfig,
    DeviceConfig,
    HostConfig,
    LaneConfig,
    LidarUnit,
    TriggerConditions,
)
from src.main.python.services.config_service import ConfigService


def _make_config() -> dict:
    return {
        "cameras": [
            {
                "camera_id": "CAM_001",
                "name": "測試相機",
                "latitude": 25.033,
                "longitude": 121.5654,
                "orientation_degree": 45,
                "orientation_label": "N45E",
                "resolution": "1920x1080",
                "fps": 30,
                "exposure": "auto",
                "white_balance": "auto",
                "gain": 0,
                "shutter_speed": "1/100",
                "rtsp_url": "rtsp://example.com/stream",
                "custom_params": {},
            }
        ],
        "lanes": [
            {"lane_id": "LANE_001", "lane_number": 1, "width": 3.5, "description": "內車道"},
            {"lane_id": "LANE_002", "lane_number": 2, "width": 3.5, "description": "外車道"},
        ],
        "lidars": {
            "lidar_count": 1,
            "units": [
                {
                    "lidar_id": "LIDAR_001",
                    "assigned_lanes": ["LANE_001", "LANE_002"],
                    "lanes_covered": 2,
                    "offset_distance": 0.5,
                    "center_distance": 3.0,
                    "effective_left": 4.0,
                    "effective_right": 3.0,
                    "auto_calculate": True,
                    "description": "測試Lidar",
                }
            ],
        },
        "host": {
            "mqtt_ip": "127.0.0.1",
            "mqtt_port": 1883,
            "mqtt_timeout": 60,
            "rtsp_transport": "tcp",
            "save_root": "/tmp/test",
            "buffer_seconds": 4.0,
            "max_retries": 10,
            "log_level": "INFO",
            "log_dir": "logs",
            "trigger_topic": "LPR/Response/#",
            "trigger_conditions": {
                "topic_contains": "MotionAlarm",
                "source": "1",
                "state": "true",
            },
        },
    }


@pytest.fixture
def config_file(tmp_path):
    """Create a temporary config file and return its path."""
    path = tmp_path / "device_params.json"
    path.write_text(json.dumps(_make_config()), encoding="utf-8")
    return str(path)


@pytest.fixture
def svc(config_file):
    service = ConfigService(config_file)
    service.load_config()
    return service


# ── Load / Save ──────────────────────────────────────────────────────────────

class TestLoadSave:
    def test_load_returns_device_config(self, svc):
        assert isinstance(svc.config, DeviceConfig)

    def test_load_cameras(self, svc):
        assert len(svc.config.cameras) == 1
        assert svc.config.cameras[0].camera_id == "CAM_001"

    def test_load_lanes(self, svc):
        assert len(svc.config.lanes) == 2

    def test_load_lidars(self, svc):
        assert svc.config.lidars.lidar_count == 1

    def test_load_host(self, svc):
        assert svc.config.host.mqtt_ip == "127.0.0.1"

    def test_save_creates_backup(self, svc, config_file):
        svc.save_config()
        assert os.path.exists(config_file + ".bak")

    def test_save_and_reload(self, svc, config_file):
        svc.config.cameras[0].name = "修改後名稱"
        svc.save_config()
        svc2 = ConfigService(config_file)
        svc2.load_config()
        assert svc2.config.cameras[0].name == "修改後名稱"


# ── Camera CRUD ───────────────────────────────────────────────────────────────

class TestCameraCRUD:
    def test_get_existing_camera(self, svc):
        cam = svc.get_camera("CAM_001")
        assert cam is not None
        assert cam.name == "測試相機"

    def test_get_nonexistent_camera(self, svc):
        assert svc.get_camera("NOTEXIST") is None

    def test_add_camera(self, svc):
        cam = CameraConfig(
            camera_id="CAM_002", name="新相機",
            latitude=25.0, longitude=121.0,
            orientation_degree=90, orientation_label="E",
            resolution="1280x720", fps=25,
            exposure="auto", white_balance="auto",
            gain=0.0, shutter_speed="1/60",
            rtsp_url="rtsp://example.com/cam2",
        )
        svc.add_camera(cam)
        assert svc.get_camera("CAM_002") is not None

    def test_add_duplicate_camera_raises(self, svc):
        cam = CameraConfig(
            camera_id="CAM_001", name="重複", latitude=0, longitude=0,
            orientation_degree=0, orientation_label="N",
            resolution="1920x1080", fps=30,
            exposure="auto", white_balance="auto",
            gain=0, shutter_speed="1/100",
            rtsp_url="rtsp://example.com",
        )
        with pytest.raises(ValueError):
            svc.add_camera(cam)

    def test_update_camera(self, svc):
        svc.update_camera("CAM_001", {"fps": 60})
        assert svc.get_camera("CAM_001").fps == 60

    def test_update_nonexistent_camera_raises(self, svc):
        with pytest.raises(ValueError):
            svc.update_camera("NOTEXIST", {"fps": 60})

    def test_delete_camera(self, svc):
        svc.delete_camera("CAM_001")
        assert svc.get_camera("CAM_001") is None

    def test_delete_nonexistent_camera_raises(self, svc):
        with pytest.raises(ValueError):
            svc.delete_camera("NOTEXIST")


# ── Lane CRUD ─────────────────────────────────────────────────────────────────

class TestLaneCRUD:
    def test_get_existing_lane(self, svc):
        lane = svc.get_lane("LANE_001")
        assert lane is not None
        assert lane.width == 3.5

    def test_add_lane(self, svc):
        lane = LaneConfig(lane_id="LANE_003", lane_number=3, width=4.0, description="外側")
        svc.add_lane(lane)
        assert svc.get_lane("LANE_003") is not None

    def test_add_duplicate_lane_raises(self, svc):
        lane = LaneConfig(lane_id="LANE_001", lane_number=1, width=3.5)
        with pytest.raises(ValueError):
            svc.add_lane(lane)

    def test_update_lane(self, svc):
        svc.update_lane("LANE_001", {"width": 4.0})
        assert svc.get_lane("LANE_001").width == 4.0

    def test_delete_lane(self, svc):
        svc.delete_lane("LANE_001")
        assert svc.get_lane("LANE_001") is None


# ── Lidar CRUD ────────────────────────────────────────────────────────────────

class TestLidarCRUD:
    def test_get_existing_lidar(self, svc):
        unit = svc.get_lidar("LIDAR_001")
        assert unit is not None

    def test_lanes_covered_property(self, svc):
        unit = svc.get_lidar("LIDAR_001")
        assert unit.lanes_covered == 2

    def test_add_lidar(self, svc):
        unit = LidarUnit(
            lidar_id="LIDAR_002",
            assigned_lanes=["LANE_001"],
            offset_distance=0.0,
            center_distance=2.0,
            effective_left=1.75,
            effective_right=1.75,
        )
        svc.add_lidar(unit)
        assert svc.get_lidar("LIDAR_002") is not None

    def test_update_lidar(self, svc):
        svc.update_lidar("LIDAR_001", {"offset_distance": 1.0})
        assert svc.get_lidar("LIDAR_001").offset_distance == 1.0

    def test_delete_lidar(self, svc):
        svc.delete_lidar("LIDAR_001")
        assert svc.get_lidar("LIDAR_001") is None


# ── Lidar auto-calculation ────────────────────────────────────────────────────

class TestLidarCalculation:
    def test_calculate_effective_range(self, svc):
        # LANE_001 (3.5m) + LANE_002 (3.5m) = 7.0m total
        # offset_distance = 0.5
        # effective_left  = (7/2) + 0.5 = 4.0
        # effective_right = (7/2) - 0.5 = 3.0
        unit = svc.calculate_lidar_effective_range("LIDAR_001")
        assert unit.effective_left == pytest.approx(4.0)
        assert unit.effective_right == pytest.approx(3.0)

    def test_calculate_with_zero_offset(self, svc):
        svc.update_lidar("LIDAR_001", {"offset_distance": 0.0})
        unit = svc.calculate_lidar_effective_range("LIDAR_001")
        assert unit.effective_left == pytest.approx(3.5)
        assert unit.effective_right == pytest.approx(3.5)

    def test_calculate_with_negative_offset(self, svc):
        svc.update_lidar("LIDAR_001", {"offset_distance": -0.5})
        unit = svc.calculate_lidar_effective_range("LIDAR_001")
        assert unit.effective_left == pytest.approx(3.0)
        assert unit.effective_right == pytest.approx(4.0)

    def test_calculate_invalid_lane_raises(self, svc):
        svc.update_lidar("LIDAR_001", {"assigned_lanes": ["LANE_999"]})
        with pytest.raises(ValueError):
            svc.calculate_lidar_effective_range("LIDAR_001")

    def test_recalculate_all_returns_ids(self, svc):
        updated = svc.recalculate_all_lidars()
        assert "LIDAR_001" in updated

    def test_recalculate_skips_manual(self, svc):
        svc.update_lidar("LIDAR_001", {"auto_calculate": False})
        updated = svc.recalculate_all_lidars()
        assert "LIDAR_001" not in updated


# ── Host ──────────────────────────────────────────────────────────────────────

class TestHostUpdate:
    def test_update_host(self, svc):
        svc.update_host({"mqtt_port": 8883})
        assert svc.config.host.mqtt_port == 8883

    def test_update_trigger_conditions(self, svc):
        svc.update_host({"trigger_conditions": {"source": "2"}})
        assert svc.config.host.trigger_conditions.source == "2"


# ── Validate config ───────────────────────────────────────────────────────────

class TestValidateConfig:
    def test_valid_config_no_errors(self, svc):
        errors = svc.validate_config()
        assert errors == []

    def test_invalid_port_caught(self, svc):
        svc.config.host.mqtt_port = 99999
        errors = svc.validate_config()
        assert any("mqtt_port" in e.lower() or "port" in e.lower() for e in errors)

    def test_invalid_log_level_caught(self, svc):
        svc.config.host.log_level = "VERBOSE"
        errors = svc.validate_config()
        assert any("log_level" in e.lower() or "日誌" in e for e in errors)


# ── Export / Import ───────────────────────────────────────────────────────────

class TestExportImport:
    def test_export_creates_file(self, svc, tmp_path):
        export_path = str(tmp_path / "export.json")
        svc.export_config(export_path)
        assert os.path.exists(export_path)

    def test_import_loads_config(self, svc, tmp_path, config_file):
        export_path = str(tmp_path / "export.json")
        svc.export_config(export_path)

        svc2 = ConfigService(config_file)
        svc2.import_config(export_path)
        assert len(svc2.config.cameras) == len(svc.config.cameras)
