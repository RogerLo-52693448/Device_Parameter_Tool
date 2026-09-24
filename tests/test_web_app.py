import json

from device_parameter_tool.web.app import create_app


FORM_DATA = {
    "site_name": "台北交流道",
    "note": "中文備註測試",
    "lane_count": "2",
    "lidar_count": "1",
    "camera_id": "CAM-01",
    "camera_name": "北上主攝影機",
    "camera_latitude": "25.0478",
    "camera_longitude": "121.5319",
    "camera_orientation_deg": "90",
    "camera_orientation_label": "東向",
    "camera_resolution": "1920x1080",
    "camera_fps": "30",
    "camera_exposure": "auto",
    "camera_white_balance": "auto",
    "camera_gain": "1.5",
    "camera_shutter_speed": "1/60",
    "camera_rtsp_url": "rtsp://192.168.1.10/main",
    "camera_ip": "192.168.1.10",
    "camera_port": "554",
    "camera_protocol": "rtsp",
    "lane_0_id": "L0",
    "lane_0_number": "0",
    "lane_0_width_mm": "3500",
    "lane_0_description": "內側",
    "lane_1_id": "L1",
    "lane_1_number": "1",
    "lane_1_width_mm": "3300",
    "lane_1_description": "外側",
    "lidar_0_id": "LD-01",
    "lidar_0_assigned_lanes": "0,1",
    "lidar_0_center_distance_mm": "3600",
    "lidar_0_auto_calculate": "on",
    "lidar_0_description": "主要 Lidar",
    "host_ip": "192.168.1.20",
    "host_port": "8080",
    "host_log_level": "INFO",
    "host_mqtt_ip": "192.168.1.21",
    "host_mqtt_port": "1883",
    "host_mqtt_timeout": "60",
    "host_rtsp_transport": "tcp",
    "host_save_root": "./captures",
    "host_buffer_seconds": "3.5",
    "host_max_retries": "5",
    "host_log_dir": "./logs",
    "host_trigger_topic": "site/event",
    "host_trigger_topic_contains": "incident",
    "host_trigger_source": "radar",
    "host_trigger_state": "active",
}


def test_web_save_and_history_round_trip(tmp_path):
    app = create_app(tmp_path)
    client = app.test_client()

    response = client.post("/save", data=FORM_DATA)

    assert response.status_code == 200
    assert "中文備註測試" in response.get_data(as_text=True)
    assert "設定已儲存" in response.get_data(as_text=True)

    history_path = tmp_path / "site_history.json"
    history_data = json.loads(history_path.read_text(encoding="utf-8"))
    assert history_data[0]["note"] == "中文備註測試"
    assert history_data[0]["config"]["site_name"] == "台北交流道"
    assert history_data[0]["config"]["camera"]["camera_id"] == "CAM-01"
    assert history_data[0]["config"]["host"]["mqtt_ip"] == "192.168.1.21"
    assert history_data[0]["config"]["lanes"][0]["lane_id"] == "L0"

    history_response = client.get("/history/0")
    history_text = history_response.get_data(as_text=True)
    assert history_response.status_code == 200
    assert "台北交流道" in history_text
    assert "中文備註測試" in history_text
    assert "北上主攝影機" in history_text
    assert "主要 Lidar" in history_text
