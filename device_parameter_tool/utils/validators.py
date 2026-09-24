"""Validation helpers for device parameter tool."""

from __future__ import annotations

from ipaddress import ip_address

VALID_PROTOCOLS = {"rtsp", "http", "https", "udp", "tcp"}
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


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
