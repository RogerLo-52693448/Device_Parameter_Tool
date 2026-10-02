"""Validation helpers for device parameter tool."""

from __future__ import annotations

from ipaddress import ip_address

VALID_PROTOCOLS = {"rtsp", "http", "https", "udp", "tcp"}
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}
TRAFFIC_MODES = {"inner_from_right", "inner_from_left"}
LIDAR_LABEL_STARTS = {0, 1}
SITE_ROUTE_OPTIONS = [
    ("國一", "01F"),
    ("國三", "03F"),
    ("國三甲", "03A"),
    ("國一高架", "01H"),
    ("國二", "02F"),
    ("國四", "04F"),
    ("國六", "06F"),
    ("國十", "10F"),
]
SITE_ROUTE_INDEX_MAP = dict(SITE_ROUTE_OPTIONS)


def validate_ip(value: str, field_name: str = "IP") -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} 不可為空")
    try:
        ip_address(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} 格式不正確") from exc
    return value


def validate_port(value: int, field_name: str = "Port") -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} 必須為整數")
    if value < 1 or value > 65535:
        raise ValueError(f"{field_name} 必須介於 1 到 65535")
    return value


def validate_non_negative_number(value: float, field_name: str) -> float:
    if value < 0:
        raise ValueError(f"{field_name} 不可為負數")
    return value


def validate_positive_number(value: float, field_name: str) -> float:
    if value <= 0:
        raise ValueError(f"{field_name} 必須大於 0")
    return value


def validate_protocol(value: str) -> str:
    protocol = value.strip().lower()
    if protocol not in VALID_PROTOCOLS:
        raise ValueError(f"傳輸協定必須為 {', '.join(sorted(VALID_PROTOCOLS))}")
    return protocol


def validate_log_level(value: str) -> str:
    level = value.strip().upper()
    if level not in VALID_LOG_LEVELS:
        raise ValueError(f"log level 必須為 {', '.join(sorted(VALID_LOG_LEVELS))}")
    return level


def validate_traffic_mode(value: str) -> str:
    mode = value.strip().lower()
    if mode not in TRAFFIC_MODES:
        raise ValueError(f"traffic mode 必須為 {', '.join(sorted(TRAFFIC_MODES))}")
    return mode


def validate_lidar_label_start(value: int) -> int:
    if value not in LIDAR_LABEL_STARTS:
        raise ValueError("Lidar 起始編號必須為 0 或 1")
    return value


def lane_slot_labels(traffic_mode: str) -> tuple[str, str]:
    mode = validate_traffic_mode(traffic_mode)
    return ("右", "左") if mode == "inner_from_right" else ("左", "右")


def physical_slots_from_inner_outer(
    inner_lane: int | None,
    outer_lane: int | None,
    traffic_mode: str,
) -> tuple[int | None, int | None]:
    mode = validate_traffic_mode(traffic_mode)
    if mode == "inner_from_right":
        return inner_lane, outer_lane
    return outer_lane, inner_lane


def inner_outer_from_physical_slots(
    right_lane: int | None,
    left_lane: int | None,
    traffic_mode: str,
) -> tuple[int | None, int | None]:
    mode = validate_traffic_mode(traffic_mode)
    if mode == "inner_from_right":
        return right_lane, left_lane
    return left_lane, right_lane


def validate_site_name(value: str) -> str:
    site_name = value.strip()
    if not site_name:
        raise ValueError("點位名稱不可為空")
    allowed_prefixes = ", ".join(prefix for _, prefix in SITE_ROUTE_OPTIONS)
    if not any(site_name.startswith(prefix) for _, prefix in SITE_ROUTE_OPTIONS):
        raise ValueError(f"點位名稱開頭必須為以下搜尋索引之一: {allowed_prefixes}")
    return site_name


def site_route_label(site_name: str) -> str | None:
    for label, prefix in SITE_ROUTE_OPTIONS:
        if site_name.startswith(prefix):
            return label
    return None


def validate_lidar_assignment(assigned_lanes: list[int], available_lane_numbers: set[int] | list[int]) -> list[int]:
    normalized = sorted(set(assigned_lanes))
    ordered_lane_numbers = sorted(available_lane_numbers)
    if not normalized:
        raise ValueError("Lidar 至少要負責 1 個車道")
    if len(normalized) > 2:
        raise ValueError("Lidar 最多只能負責 2 個車道")
    if any(lane not in ordered_lane_numbers for lane in normalized):
        raise ValueError("Lidar 指派了不存在的車道")
    if len(normalized) == 2:
        lane_positions = {lane: index for index, lane in enumerate(ordered_lane_numbers)}
        if lane_positions[normalized[1]] - lane_positions[normalized[0]] != 1:
            raise ValueError("Lidar 若負責 2 個車道，車道必須相鄰")
    return normalized


def validate_lidar_lane_slots(
    inner_lane: int | None,
    outer_lane: int | None,
    available_lane_numbers: set[int] | list[int],
) -> tuple[int | None, int | None, list[int]]:
    ordered_lane_numbers = sorted(available_lane_numbers)
    active_lanes = [lane for lane in (inner_lane, outer_lane) if lane is not None]
    if not active_lanes:
        raise ValueError("Lidar 至少要負責 1 個車道")
    if any(lane not in ordered_lane_numbers for lane in active_lanes):
        raise ValueError("Lidar 指派了不存在的車道")
    if inner_lane is not None and outer_lane is not None:
        if inner_lane == outer_lane:
            raise ValueError("Lidar 內外車道不可重複")
        lane_positions = {lane: index for index, lane in enumerate(ordered_lane_numbers)}
        if lane_positions[outer_lane] - lane_positions[inner_lane] != 1:
            raise ValueError("Lidar 內外車道必須相鄰，且外車道需在內車道外側")
    return inner_lane, outer_lane, active_lanes
