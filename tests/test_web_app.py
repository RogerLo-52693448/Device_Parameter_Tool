import json

from device_parameter_tool.web.app import create_app


FORM_DATA = {
    "site_name": "台北交流道",
    "note": "中文備註測試",
    "has_backup": "on",
    "lane_count": "2",
    "primary_lidar_count": "1",
    "backup_lidar_count": "1",
    "lane_0_number": "0",
    "lane_0_width_mm": "3500",
    "lane_1_number": "1",
    "lane_1_width_mm": "3300",
    "primary_lidar_0_lane_a": "0",
    "primary_lidar_0_lane_b": "1",
    "primary_lidar_0_center_distance_mm": "3600",
    "primary_lidar_0_auto_calculate": "on",
    "backup_lidar_0_lane_a": "0",
    "backup_lidar_0_lane_b": "1",
    "backup_lidar_0_center_distance_mm": "3650",
    "backup_lidar_0_auto_calculate": "on",
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
    assert history_data[0]["config"]["lanes"][0]["lane_number"] == 0
    assert history_data[0]["config"]["has_backup"] is True
    assert history_data[0]["config"]["backup_lidars"][0]["assigned_lanes"] == [0, 1]
    assert "T" not in history_data[0]["saved_at"]
    assert "Z" not in history_data[0]["saved_at"]

    history_response = client.get("/history/0")
    history_text = history_response.get_data(as_text=True)
    assert history_response.status_code == 200
    assert "台北交流道" in history_text
    assert "中文備註測試" in history_text
    assert "已載入歷史紀錄" in history_text
    assert "備援 Lidar" in history_text
    assert "Field 範圍" in history_text
    assert "Field1" in history_text


def test_web_page_uses_dynamic_lane_and_lidar_sections(tmp_path):
    app = create_app(tmp_path)
    client = app.test_client()

    response = client.get("/")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="lane-count"' in text
    assert 'id="primary-lidar-count"' in text
    assert 'id="backup-lidar-count"' in text
    assert "renderLanes()" in text
    assert "renderLidars('primary'" in text
    assert 'id="has-backup"' in text
    assert "lidar-block-title" in text
    assert "Primary Lidar Configuration" in text
    assert "Lane0" in text
    assert "Lane6" in text
    assert "None" in text
    assert "Camera" not in text
    assert "Host" not in text
    assert "Lane ID" not in text
    assert "Lidar ID" not in text


def test_web_save_invalid_input_shows_error(tmp_path):
    app = create_app(tmp_path)
    client = app.test_client()

    bad_data = dict(FORM_DATA)
    bad_data["primary_lidar_0_lane_a"] = "none"
    bad_data["primary_lidar_0_lane_b"] = "none"

    response = client.post("/save", data=bad_data)
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "至少要負責 1 個車道" in text


def test_web_preview_invalid_input_shows_error(tmp_path):
    app = create_app(tmp_path)
    client = app.test_client()

    bad_data = dict(FORM_DATA)
    bad_data["primary_lidar_0_lane_a"] = "none"
    bad_data["primary_lidar_0_lane_b"] = "none"

    response = client.post("/preview", data=bad_data)
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "至少要負責 1 個車道" in text


def test_web_save_invalid_backup_input_shows_error(tmp_path):
    app = create_app(tmp_path)
    client = app.test_client()

    bad_data = dict(FORM_DATA)
    bad_data["backup_lidar_0_lane_a"] = "none"
    bad_data["backup_lidar_0_lane_b"] = "none"

    response = client.post("/save", data=bad_data)
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "至少要負責 1 個車道" in text
