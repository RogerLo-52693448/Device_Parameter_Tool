from typing import Any


def validate_latitude(val: Any) -> float:
    """Validate latitude: -90 ~ 90."""
    val = float(val)
    if not (-90 <= val <= 90):
        raise ValueError(f"緯度必須介於 -90 ~ 90，輸入值: {val}")
    return val


def validate_longitude(val: Any) -> float:
    """Validate longitude: -180 ~ 180."""
    val = float(val)
    if not (-180 <= val <= 180):
        raise ValueError(f"經度必須介於 -180 ~ 180，輸入值: {val}")
    return val


def validate_orientation(val: Any) -> float:
    """Validate orientation degree: 0 ~ 360."""
    val = float(val)
    if not (0 <= val <= 360):
        raise ValueError(f"方向角度必須介於 0 ~ 360，輸入值: {val}")
    return val


def validate_port(val: Any) -> int:
    """Validate network port: 1 ~ 65535."""
    val = int(val)
    if not (1 <= val <= 65535):
        raise ValueError(f"Port 必須介於 1 ~ 65535，輸入值: {val}")
    return val


def validate_positive_float(val: Any) -> float:
    """Validate value is a positive float (> 0)."""
    val = float(val)
    if val <= 0:
        raise ValueError(f"值必須大於 0，輸入值: {val}")
    return val


def validate_non_negative_float(val: Any) -> float:
    """Validate value is a non-negative float (>= 0)."""
    val = float(val)
    if val < 0:
        raise ValueError(f"值必須大於等於 0，輸入值: {val}")
    return val


def validate_positive_int(val: Any) -> int:
    """Validate value is a positive integer (>= 1)."""
    val = int(val)
    if val < 1:
        raise ValueError(f"值必須大於等於 1，輸入值: {val}")
    return val


def validate_non_negative_int(val: Any) -> int:
    """Validate value is a non-negative integer (>= 0)."""
    val = int(val)
    if val < 0:
        raise ValueError(f"值必須大於等於 0，輸入值: {val}")
    return val


def validate_log_level(val: Any) -> str:
    """Validate log level: DEBUG/INFO/WARNING/ERROR."""
    val = str(val).upper()
    allowed = {"DEBUG", "INFO", "WARNING", "ERROR"}
    if val not in allowed:
        raise ValueError(f"日誌等級必須為 DEBUG/INFO/WARNING/ERROR，輸入值: {val}")
    return val


def validate_transport(val: Any) -> str:
    """Validate RTSP transport: tcp/udp."""
    val = str(val).lower()
    if val not in {"tcp", "udp"}:
        raise ValueError(f"RTSP 傳輸方式必須為 tcp 或 udp，輸入值: {val}")
    return val
