import json

from device_parameter_tool.web.app import create_app


FORM_DATA = {
    "site_name": "台北交流道",
    "note": "中文備註測試",
    "camera_latitude": "25.0478",
    "camera_longitude": "121.5319",
    "camera_orientation_deg": "90",
    "camera_ip": "192.168.1.10",
    "camera_port": "554",
    "camera_protocol": "rtsp",
    "lanes": "0,3500\n1,3300",
    "lidars": "0,1:3600",
    "host_ip": "192.168.1.20",
    "host_port": "8080",
    "host_log_level": "INFO",
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

    history_response = client.get("/history/0")
    history_text = history_response.get_data(as_text=True)
    assert history_response.status_code == 200
    assert "台北交流道" in history_text
    assert "中文備註測試" in history_text
