"""Reusable lidar effective range calculation service."""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from device_parameter_tool.models.device_config import DeviceConfig, LaneConfig, LidarConfig
from device_parameter_tool.utils.validators import validate_lidar_assignment

SCAN_LIMIT = 5500.0
SOPAS_MM_PER_DEGREE = 200.0
SOPAS_CENTER_ANGLE = 90


@dataclass(slots=True)
class LidarCalculationResult:
    index: int
    assigned: list[int]
    center: float
    scan_right: float
    scan_left: float
    offset_value: float
    offset_formula: str
    inner_boundary: float
    outer_boundary: float
    assigned_width: float
    is_innermost: bool
    is_outermost: bool
    right_compensation: float
    left_compensation: float
    status: str
    messages: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LidarCalculationSummary:
    results: list[LidarCalculationResult]
    warnings: list[str]
    errors: list[str]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


@dataclass(slots=True)
class SopasFieldResult:
    index: int
    assigned: list[int]
    offset_value: float
    field1: tuple[int, int]
    field2: tuple[int, int]
    field3: tuple[int, int]
    field4: tuple[int, int] | None
    field5: tuple[int, int] | None
    field6: tuple[int, int] | None
    center_inner: int
    center_outer: int | None


def calculate_lidar_results(lanes: list[LaneConfig], lidars: list[LidarConfig]) -> LidarCalculationSummary:
    if not lanes:
        raise ValueError("至少需要 1 個車道")
    all_lanes_sorted = sorted(lanes, key=lambda lane: lane.lane_number)
    lane_width_map = {lane.lane_number: lane.width_mm for lane in all_lanes_sorted}
    min_lane_number = all_lanes_sorted[0].lane_number
    max_lane_number = all_lanes_sorted[-1].lane_number
    available_lane_numbers = {lane.lane_number for lane in all_lanes_sorted}

    results: list[LidarCalculationResult] = []
    warnings: list[str] = []
    errors: list[str] = []
    prev_lidars_total = 0.0

    for i, lidar in enumerate(lidars):
        assigned = validate_lidar_assignment(sorted(lidar.assigned_lanes), available_lane_numbers)
        if not assigned:
            raise ValueError(f"LIDAR_{i} 至少要負責 1 個車道")
        center = lidar.center_distance_mm
        min_assigned = assigned[0]
        max_assigned = assigned[-1]

        inner_boundary = sum(width for lane_number, width in lane_width_map.items() if lane_number < min_assigned)
        assigned_width = sum(lane_width_map[lane_number] for lane_number in assigned)
        outer_boundary = inner_boundary + assigned_width

        is_innermost = min_assigned == min_lane_number
        is_outermost = max_assigned == max_lane_number
        right_compensation = 0.0 if is_innermost else 500.0
        left_compensation = 0.0 if is_outermost else 500.0

        scan_right = center - inner_boundary + right_compensation
        scan_left = outer_boundary - center + left_compensation

        if len(assigned) == 2:
            right_lane_width = lane_width_map[assigned[0]]
            offset_value = abs(center - prev_lidars_total - right_lane_width)
        else:
            offset_value = abs(center - prev_lidars_total)

        prev_parts = [
            f"Lane{lane_number}({lane_width_map[lane_number]:.0f})"
            for prev_lidar in lidars[:i]
            for lane_number in sorted(prev_lidar.assigned_lanes)
        ]
        if i == 0 and len(assigned) == 2:
            offset_formula = f"|{center:.0f} - Lane{assigned[0]}({lane_width_map[assigned[0]]:.0f})|"
        elif i == 0:
            offset_formula = f"|{center:.0f} - 0|"
        elif len(assigned) == 2:
            offset_formula = (
                f"|{center:.0f} - {' + '.join(prev_parts)} - "
                f"Lane{assigned[0]}({lane_width_map[assigned[0]]:.0f})|"
            )
        else:
            offset_formula = f"|{center:.0f} - {' + '.join(prev_parts)}|"

        status = "normal"
        messages: list[str] = []
        if scan_right > SCAN_LIMIT:
            warning = f"LIDAR_{i}: scan_right={scan_right:.0f}mm 超過 {SCAN_LIMIT:.0f}mm 偵測上限，建議拆分車道並增加 Lidar 數量"
            warnings.append(warning)
            messages.append(warning)
            status = "warning"
        if scan_left > SCAN_LIMIT:
            warning = f"LIDAR_{i}: scan_left={scan_left:.0f}mm 超過 {SCAN_LIMIT:.0f}mm 偵測上限，建議拆分車道並增加 Lidar 數量"
            warnings.append(warning)
            messages.append(warning)
            status = "warning"
        if scan_right < 0 or scan_left < 0:
            error = f"LIDAR_{i}: 有效偵測範圍出現負值，請檢查中心點距離與車道指派"
            errors.append(error)
            messages.append(error)
            status = "error"

        results.append(
            LidarCalculationResult(
                index=i,
                assigned=assigned,
                center=center,
                scan_right=scan_right,
                scan_left=scan_left,
                offset_value=offset_value,
                offset_formula=offset_formula,
                inner_boundary=inner_boundary,
                outer_boundary=outer_boundary,
                assigned_width=assigned_width,
                is_innermost=is_innermost,
                is_outermost=is_outermost,
                right_compensation=right_compensation,
                left_compensation=left_compensation,
                status=status,
                messages=messages,
            )
        )
        prev_lidars_total += assigned_width

    return LidarCalculationSummary(results=results, warnings=warnings, errors=errors)


def calculate_for_config(config: DeviceConfig) -> LidarCalculationSummary:
    config.validate()
    return calculate_lidar_results(config.lanes, config.lidars)


def calculate_sopas_fields(lanes: list[LaneConfig], lidars: list[LidarConfig]) -> list[SopasFieldResult]:
    if not lanes:
        raise ValueError("至少需要 1 個車道")
    lane_width_map = {lane.lane_number: lane.width_mm for lane in sorted(lanes, key=lambda lane: lane.lane_number)}
    available_lane_numbers = set(lane_width_map)
    prev_lidars_total = 0.0
    results: list[SopasFieldResult] = []

    for index, lidar in enumerate(lidars):
        assigned = validate_lidar_assignment(sorted(lidar.assigned_lanes), available_lane_numbers)
        if not assigned:
            raise ValueError(f"LIDAR_{index} 至少要負責 1 個車道")

        center = lidar.center_distance_mm
        inner_lane_width = lane_width_map[assigned[0]]
        assigned_width = sum(lane_width_map[lane_number] for lane_number in assigned)
        outer_boundary = prev_lidars_total + assigned_width

        offset_right = center - prev_lidars_total - inner_lane_width
        offset_left = center - outer_boundary

        field1_upper = SOPAS_CENTER_ANGLE + math.ceil((inner_lane_width + offset_right) / SOPAS_MM_PER_DEGREE)
        field1_lower = SOPAS_CENTER_ANGLE + math.floor(offset_right / SOPAS_MM_PER_DEGREE)
        center_inner = math.ceil((field1_upper + field1_lower) / 2)

        is_innermost = assigned[0] == min(available_lane_numbers)
        field2_lower = center_inner - 2
        field2_upper = field1_upper if is_innermost else field1_upper + 2
        field3_lower = field1_lower - 2
        field3_upper = center_inner + 2

        field4 = None
        field5 = None
        field6 = None
        center_outer = None
        if len(assigned) == 2:
            field4_upper = field1_lower
            field4_lower = SOPAS_CENTER_ANGLE + math.floor(offset_left / SOPAS_MM_PER_DEGREE)
            center_outer = math.ceil((field4_upper + field4_lower) / 2)
            field4 = (field4_lower, field4_upper)
            field5 = (center_outer - 2, field4_upper + 2)
            field6 = (field4_lower - 2, center_outer + 2)

        results.append(
            SopasFieldResult(
                index=index,
                assigned=assigned,
                offset_value=offset_right,
                field1=(field1_lower, field1_upper),
                field2=(field2_lower, field2_upper),
                field3=(field3_lower, field3_upper),
                field4=field4,
                field5=field5,
                field6=field6,
                center_inner=center_inner,
                center_outer=center_outer,
            )
        )
        prev_lidars_total += assigned_width

    return results


def render_text_report(config: DeviceConfig, summary: LidarCalculationSummary) -> str:
    field_results = calculate_sopas_fields(config.lanes, config.lidars) if config.lidars else []
    lines = ["=" * 90, f"  計算結果 — {config.site_name}", "=" * 90, "", "  【車道資訊】", ""]
    lines.append("  ┌────────┬──────────┐")
    lines.append("  │ 車道   │ 寬度(mm) │")
    lines.append("  ├────────┼──────────┤")
    for lane in sorted(config.lanes, key=lambda item: item.lane_number):
        lines.append(f"  │ Lane{lane.lane_number:<2} │ {lane.width_mm:>8.0f} │")
    lines.append("  ├────────┼──────────┤")
    lines.append(f"  │ 合計   │ {sum(lane.width_mm for lane in config.lanes):>8.0f} │")
    lines.append("  └────────┴──────────┘")
    lines.append("")
    lines.append("  [護欄]" + "".join(f" |← Lane{lane.lane_number}:{lane.width_mm:.0f} →|" for lane in sorted(config.lanes, key=lambda item: item.lane_number)) + " [外側]")
    lines.extend(["", "  【Lidar 輸入資訊】", "", "  ┌─────────┬────────────────┬──────────────┐", "  │ Lidar   │ 負責車道       │ 中心距離(mm) │", "  ├─────────┼────────────────┼──────────────┤"])
    for index, lidar in enumerate(config.lidars):
        lanes_str = "+".join(f"Lane{lane}" for lane in sorted(lidar.assigned_lanes))
        lines.append(f"  │ LIDAR_{index} │ {lanes_str:<14} │ {lidar.center_distance_mm:>12.0f} │")
    lines.append("  └─────────┴────────────────┴──────────────┘")
    lines.extend(["", "  【計算結果】", "", "  ┌─────────┬────────────────┬──────────────┬──────────────┬──────────────┬──────────────┬────────┐", "  │ Lidar   │ 負責車道       │ 中心距離(mm) │ scan_right   │ scan_left    │ 偏差值(mm)   │ 狀態   │", "  ├─────────┼────────────────┼──────────────┼──────────────┼──────────────┼──────────────┼────────┤"])
    for result in summary.results:
        lanes_str = "+".join(f"Lane{lane}" for lane in result.assigned)
        status_map = {"normal": "✓ 正常", "warning": "⚠ 警告", "error": "✗ 錯誤"}
        lines.append(f"  │ LIDAR_{result.index} │ {lanes_str:<14} │ {result.center:>12.0f} │ {result.scan_right:>12.0f} │ {result.scan_left:>12.0f} │ {result.offset_value:>12.0f} │ {status_map[result.status]} │")
    lines.append("  └─────────┴────────────────┴──────────────┴──────────────┴──────────────┴──────────────┴────────┘")
    if summary.warnings:
        lines.extend(["", "  ⚠️  警告訊息:"])
        lines.extend(f"    → {warning}" for warning in summary.warnings)
    if summary.errors:
        lines.extend(["", "  ✗ 錯誤訊息:"])
        lines.extend(f"    → {error}" for error in summary.errors)
    lines.append("")
    lines.append("  【詳細計算過程】")
    for result in summary.results:
        lanes_str = "+".join(f"Lane{lane}" for lane in result.assigned)
        lines.extend([
            "",
            f"  LIDAR_{result.index} ({lanes_str}, center={result.center:.0f}mm):",
            f"    負責車道邊界: {result.inner_boundary:.0f}mm ~ {result.outer_boundary:.0f}mm",
            f"    最內側: {'是' if result.is_innermost else '否'} (右補償 +{result.right_compensation:.0f}mm)",
            f"    最外側: {'是' if result.is_outermost else '否'} (左補償 +{result.left_compensation:.0f}mm)",
            f"    scan_right = {result.center:.0f} - {result.inner_boundary:.0f} + {result.right_compensation:.0f} = {result.scan_right:.0f}mm",
            f"    scan_left  = {result.outer_boundary:.0f} - {result.center:.0f} + {result.left_compensation:.0f} = {result.scan_left:.0f}mm",
            f"    偏差值     = {result.offset_formula} = {result.offset_value:.0f}mm",
        ])
    if field_results:
        lines.extend(["", "  【Field 範圍】", ""])
        for field in field_results:
            lanes_str = "+".join(f"Lane{lane}" for lane in field.assigned)
            def fmt(value: tuple[int, int] | None) -> str:
                return f"{value[0]}° ~ {value[1]}°" if value is not None else "—"
            lines.append(
                f"  LIDAR_{field.index} ({lanes_str}) | "
                f"F1 {fmt(field.field1)} | F2 {fmt(field.field2)} | F3 {fmt(field.field3)} | "
                f"F4 {fmt(field.field4)} | F5 {fmt(field.field5)} | F6 {fmt(field.field6)}"
            )
    lines.extend(["", "=" * 90, "  完成！", "=" * 90])
    return "\n".join(lines)
