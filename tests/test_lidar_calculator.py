from device_parameter_tool.models.device_config import LaneConfig, LidarConfig
from device_parameter_tool.services.lidar_calculator import SCAN_LIMIT, calculate_lidar_results


def test_lidar_boundary_and_compensation_scenarios():
    lanes = [
        LaneConfig(0, 3500.0),
        LaneConfig(1, 3300.0),
        LaneConfig(2, 3200.0),
        LaneConfig(3, 3100.0),
    ]
    lidars = [
        LidarConfig([0], 1200.0),
        LidarConfig([1, 2], 7000.0),
        LidarConfig([3], 10300.0),
    ]

    summary = calculate_lidar_results(lanes, lidars)

    assert summary.errors == []
    assert summary.results[0].is_innermost is True
    assert summary.results[0].right_compensation == 0.0
    assert summary.results[0].left_compensation == 500.0
    assert summary.results[0].scan_right == 1200.0
    assert summary.results[0].scan_left == 2800.0

    assert summary.results[1].is_innermost is False
    assert summary.results[1].is_outermost is False
    assert summary.results[1].right_compensation == 500.0
    assert summary.results[1].left_compensation == 500.0
    assert summary.results[1].scan_right == 4000.0
    assert summary.results[1].scan_left == 3500.0
    assert summary.results[1].offset_value == 200.0

    assert summary.results[2].is_outermost is True
    assert summary.results[2].left_compensation == 0.0
    assert summary.results[2].scan_right == 800.0
    assert summary.results[2].scan_left == 2800.0


def test_lidar_warning_and_negative_error():
    lanes = [LaneConfig(0, 3500.0), LaneConfig(1, 3500.0)]

    warning_summary = calculate_lidar_results(lanes, [LidarConfig([0, 1], 1000.0)])
    assert any(str(int(SCAN_LIMIT)) in message for message in warning_summary.warnings)
    assert warning_summary.results[0].status == "warning"

    error_summary = calculate_lidar_results(lanes, [LidarConfig([1], 1000.0)])
    assert error_summary.errors
    assert error_summary.results[0].status == "error"
