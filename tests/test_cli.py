from device_parameter_tool.core.cli import config_clone, lane_menu, show_report
from device_parameter_tool.models.device_config import DeviceConfig, LaneConfig, LidarConfig


def test_show_report_renders_primary_and_backup_sections(capsys):
    config = DeviceConfig(
        site_name="01F-CLI 測試",
        lanes=[LaneConfig(0, 3500.0), LaneConfig(1, 3300.0)],
        lidars=[LidarConfig([0], 1200.0)],
        has_backup=True,
        backup_lidars=[LidarConfig([0, 1], 3600.0)],
    )

    show_report(config)

    output = capsys.readouterr().out
    assert "【主 Lidar】" in output
    assert "【備援 Lidar】" in output
    assert "內線在右側" in output or "inner_from_right" in output
    assert "Lane0" in output
    assert "Field1" in output
    assert "Field 模式" in output


def test_clone_allows_incomplete_config_without_sharing_mutable_state():
    config = DeviceConfig(lanes=[LaneConfig(0, 3500.0)])

    snapshot = config_clone(config)
    config.lanes[0].width_mm = 4000.0

    assert snapshot.site_name == config.site_name
    assert snapshot.lanes[0].width_mm == 3500.0


def test_lane_menu_can_return_before_site_setup(monkeypatch):
    config = DeviceConfig(lanes=[LaneConfig(0, 3500.0)])
    monkeypatch.setattr("builtins.input", lambda _: "4")

    lane_menu(config)
