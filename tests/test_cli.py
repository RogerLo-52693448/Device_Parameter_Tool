from device_parameter_tool.core.cli import show_report
from device_parameter_tool.models.device_config import DeviceConfig, LaneConfig, LidarConfig


def test_show_report_renders_primary_and_backup_sections(capsys):
    config = DeviceConfig(
        site_name="CLI 測試",
        lanes=[LaneConfig(0, 3500.0), LaneConfig(1, 3300.0)],
        lidars=[LidarConfig([0], 1200.0)],
        has_backup=True,
        backup_lidars=[LidarConfig([0, 1], 3600.0)],
    )

    show_report(config)

    output = capsys.readouterr().out
    assert "【主 Lidar】" in output
    assert "【備援 Lidar】" in output
    assert "右(Lane1)=0" in output
    assert "Field1" in output
