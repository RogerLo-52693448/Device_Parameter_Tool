import json

from device_parameter_tool.web.app import create_app


FORM_DATA = {
    "site_name": "台北交流道",
    "note": "中文備註測試",
    "lane_count": "2",
    "lidar_count": "1",
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
    assert history_data[0]["config"]["lanes"][0]["lane_id"] == "L0"
    assert history_data[0]["config"]["camera"]["camera_id"] == "CAM-01"

    history_response = client.get("/history/0")
    history_text = history_response.get_data(as_text=True)
    assert history_response.status_code == 200
    assert "台北交流道" in history_text
    assert "中文備註測試" in history_text
    assert "已載入歷史紀錄" in history_text
    assert "renderLidars()" in history_text


def test_web_page_uses_dynamic_lane_and_lidar_sections(tmp_path):
    app = create_app(tmp_path)
    client = app.test_client()

    response = client.get("/")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="lane-count"' in text
    assert 'id="lidar-count"' in text
    assert "renderLanes()" in text
    assert "renderLidars()" in text
    assert "Camera" not in text
    assert "Host" not in text
