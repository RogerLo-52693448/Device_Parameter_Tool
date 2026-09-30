"""Reusable lidar effective range calculation service."""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from device_parameter_tool.models.device_config import DeviceConfig, LaneConfig, LidarConfig
from device_parameter_tool.utils.validators import lane_slot_labels, physical_slots_from_inner_outer, validate_traffic_mode
SCAN_LIMIT = 5500.0
SOPAS_MM_PER_DEGREE = 200.0
SOPAS_CENTER_ANGLE = 90


@dataclass(slots=True)
class LidarCalculationResult:
    index: int
    inner_lane: int | None
    outer_lane: int | None
    right_lane: int | None
    left_lane: int | None
    assigned: list[int]
    center: float
    scan_inner: float
    scan_outer: float
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
    debug_lines: list[str] = field(default_factory=list)


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
    inner_lane: int | None
    outer_lane: int | None
    right_lane: int | None
    left_lane: int | None
    assigned: list[int]
    offset_value: float
    field1: tuple[int, int] | None
    field2: tuple[int, int] | None
    field3: tuple[int, int] | None
    field4: tuple[int, int] | None
    field5: tuple[int, int] | None
    field6: tuple[int, int] | None
    center_inner: int | None
    center_outer: int | None
    debug_lines: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LaneInfo:
    lane_number: int
    width_mm: float
    inner_boundary: float
    outer_boundary: float


def _build_lane_context(lanes: list[LaneConfig]) -> tuple[list[LaneConfig], dict[int, float], dict[int, float]]:
    all_lanes_sorted = sorted(lanes, key=lambda lane: lane.lane_number)
    lane_width_map = {lane.lane_number: lane.width_mm for lane in all_lanes_sorted}
    lane_start_map: dict[int, float] = {}
    current = 0.0
    for lane in all_lanes_sorted:
        lane_start_map[lane.lane_number] = current
        current += lane.width_mm
    return all_lanes_sorted, lane_width_map, lane_start_map


def calculate_lane_info(lanes: list[LaneConfig]) -> list[LaneInfo]:
    all_lanes_sorted, _, lane_start_map = _build_lane_context(lanes)
    return [
        LaneInfo(
            lane_number=lane.lane_number,
            width_mm=lane.width_mm,
            inner_boundary=lane_start_map[lane.lane_number],
            outer_boundary=lane_start_map[lane.lane_number] + lane.width_mm,
        )
        for lane in all_lanes_sorted
    ]


def _ordered_lidars(
    lidars: list[LidarConfig], available_lane_numbers: set[int], traffic_mode: str
) -> list[tuple[int, list[int], LidarConfig]]:
    validated: list[tuple[int, list[int], LidarConfig]] = []
    for original_index, lidar in enumerate(lidars):
        lidar.validate(sorted(available_lane_numbers), traffic_mode)
        assigned = list(lidar.assigned_lanes)
        validated.append((original_index, assigned, lidar))
    return sorted(validated, key=lambda item: (item[1][0], item[1][-1], item[0]))


def calculate_lidar_results(
    lanes: list[LaneConfig],
    lidars: list[LidarConfig],
    traffic_mode: str = "inner_from_right",
) -> LidarCalculationSummary:
    if not lanes:
        raise ValueError("至少需要 1 個車道")
    traffic_mode = validate_traffic_mode(traffic_mode)
    all_lanes_sorted, lane_width_map, lane_start_map = _build_lane_context(lanes)
    min_lane_number = all_lanes_sorted[0].lane_number
    max_lane_number = all_lanes_sorted[-1].lane_number
    available_lane_numbers = {lane.lane_number for lane in all_lanes_sorted}
    ordered_lidars = _ordered_lidars(lidars, available_lane_numbers, traffic_mode)
    inner_label, outer_label = lane_slot_labels(traffic_mode)

    results: list[LidarCalculationResult] = []
    warnings: list[str] = []
    errors: list[str] = []

    for _, (original_index, assigned, lidar) in enumerate(ordered_lidars):
        center = lidar.center_distance_mm
        min_assigned = assigned[0]
        max_assigned = assigned[-1]

        inner_boundary = lane_start_map[min_assigned]
        assigned_width = sum(lane_width_map[lane_number] for lane_number in assigned)
        outer_boundary = inner_boundary + assigned_width

        is_innermost = min_assigned == min_lane_number
        is_outermost = max_assigned == max_lane_number
        right_compensation = 0.0 if is_innermost else 500.0
        left_compensation = 0.0 if is_outermost else 500.0

        scan_inner = center - inner_boundary + right_compensation
        scan_outer = outer_boundary - center + left_compensation
        scan_right, scan_left = physical_slots_from_inner_outer(scan_inner, scan_outer, traffic_mode)

        before_parts = [
            f"Lane{lane.lane_number}({lane.width_mm:.0f})"
            for lane in all_lanes_sorted
            if lane_start_map[lane.lane_number] < inner_boundary
        ]
        if len(assigned) == 2:
            right_lane_width = lane_width_map[assigned[0]]
            offset_value = abs(center - inner_boundary - right_lane_width)
        else:
            offset_value = abs(center - inner_boundary)

        if not before_parts and len(assigned) == 2:
            offset_formula = f"|{center:.0f} - Lane{assigned[0]}({lane_width_map[assigned[0]]:.0f})|"
        elif not before_parts:
            offset_formula = f"|{center:.0f} - 0|"
        elif len(assigned) == 2:
            offset_formula = (
                f"|{center:.0f} - {' + '.join(before_parts)} - "
                f"Lane{assigned[0]}({lane_width_map[assigned[0]]:.0f})|"
            )
        else:
            offset_formula = f"|{center:.0f} - {' + '.join(before_parts)}|"

        status = "normal"
        messages: list[str] = []
        if scan_right > SCAN_LIMIT:
            warning = f"LIDAR_{original_index}: scan_right={scan_right:.0f}mm 超過 {SCAN_LIMIT:.0f}mm 偵測上限，建議拆分車道並增加 Lidar 數量"
            warnings.append(warning)
            messages.append(warning)
            status = "warning"
        if scan_left > SCAN_LIMIT:
            warning = f"LIDAR_{original_index}: scan_left={scan_left:.0f}mm 超過 {SCAN_LIMIT:.0f}mm 偵測上限，建議拆分車道並增加 Lidar 數量"
            warnings.append(warning)
            messages.append(warning)
            status = "warning"
        if scan_right < 0 or scan_left < 0:
            error = f"LIDAR_{original_index}: 有效偵測範圍出現負值，請檢查中心點距離與車道指派"
            errors.append(error)
            messages.append(error)
            status = "error"

        results.append(
            LidarCalculationResult(
                index=original_index,
                inner_lane=lidar.inner_lane,
                outer_lane=lidar.outer_lane,
                right_lane=lidar.right_lane,
                left_lane=lidar.left_lane,
                assigned=assigned,
                center=center,
                scan_inner=scan_inner,
                scan_outer=scan_outer,
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
                debug_lines=[
                    f"內={lidar.inner_lane if lidar.inner_lane is not None else '—'} / 外={lidar.outer_lane if lidar.outer_lane is not None else '—'}",
                    f"{inner_label}={lidar.right_lane if traffic_mode == 'inner_from_right' else lidar.left_lane if lidar.left_lane is not None else '—'} / "
                    f"{outer_label}={lidar.left_lane if traffic_mode == 'inner_from_right' else lidar.right_lane if lidar.right_lane is not None else '—'}",
                    f"負責車道邊界: {inner_boundary:.0f}mm ~ {outer_boundary:.0f}mm",
                    f"最內側: {'是' if is_innermost else '否'} (內側補償 +{right_compensation:.0f}mm)",
                    f"最外側: {'是' if is_outermost else '否'} (外側補償 +{left_compensation:.0f}mm)",
                    f"scan_inner = {center:.0f} - {inner_boundary:.0f} + {right_compensation:.0f} = {scan_inner:.0f}mm",
                    f"scan_outer = {outer_boundary:.0f} - {center:.0f} + {left_compensation:.0f} = {scan_outer:.0f}mm",
                    f"偏差值     = {offset_formula} = {offset_value:.0f}mm",
                ],
            )
        )

    return LidarCalculationSummary(results=results, warnings=warnings, errors=errors)


def calculate_for_config(config: DeviceConfig) -> LidarCalculationSummary:
    config.validate()
    primary_summary = calculate_lidar_results(config.lanes, config.lidars, config.traffic_mode)
    if config.has_backup and config.backup_lidars:
        calculate_lidar_results(config.lanes, config.backup_lidars, config.traffic_mode)
    return primary_summary


def calculate_sopas_fields(
    lanes: list[LaneConfig],
    lidars: list[LidarConfig],
    traffic_mode: str = "inner_from_right",
) -> list[SopasFieldResult]:
    if not lanes:
        raise ValueError("至少需要 1 個車道")
    traffic_mode = validate_traffic_mode(traffic_mode)
    all_lanes_sorted, lane_width_map, lane_start_map = _build_lane_context(lanes)
    available_lane_numbers = set(lane_width_map)
    results: list[SopasFieldResult] = []
    ordered_lidars = _ordered_lidars(lidars, available_lane_numbers, traffic_mode)
    inner_label, outer_label = lane_slot_labels(traffic_mode)

    for original_index, assigned, lidar in ordered_lidars:
        center = lidar.center_distance_mm
        min_assigned = assigned[0]
        primary_lane = lidar.inner_lane if lidar.inner_lane is not None else lidar.outer_lane
        if primary_lane is None:
            raise ValueError(f"LIDAR_{original_index}: 至少要負責 1 個車道")
        primary_lane_width = lane_width_map[primary_lane]
        assigned_width = sum(lane_width_map[lane_number] for lane_number in assigned)
        inner_boundary = lane_start_map[min_assigned]
        outer_boundary = inner_boundary + assigned_width

        offset_primary = center - inner_boundary - primary_lane_width
        offset_left = center - outer_boundary

        primary_upper = SOPAS_CENTER_ANGLE + math.ceil((primary_lane_width + offset_primary) / SOPAS_MM_PER_DEGREE)
        primary_lower = SOPAS_CENTER_ANGLE + math.floor(offset_primary / SOPAS_MM_PER_DEGREE)
        if primary_lower > primary_upper:
            raise ValueError(f"LIDAR_{original_index}: Field 範圍計算失敗，請檢查中心點距離")
        primary_center = math.ceil((primary_upper + primary_lower) / 2)
        primary_is_innermost = primary_lane == all_lanes_sorted[0].lane_number
        primary_field2 = (primary_center - 2, primary_upper if primary_is_innermost else primary_upper + 2)
        primary_field3 = (primary_lower - 2, primary_center + 2)

        field1 = None
        field2 = None
        field3 = None
        field4 = None
        field5 = None
        field6 = None
        center_inner = primary_center if lidar.inner_lane is not None else None
        center_outer = primary_center if lidar.inner_lane is None and lidar.outer_lane is not None else None
        if lidar.inner_lane is not None:
            field1 = (primary_lower, primary_upper)
            field2 = primary_field2
            field3 = primary_field3
        if lidar.outer_lane is not None and lidar.inner_lane is None:
            field4 = (primary_lower, primary_upper)
            field5 = primary_field2
            field6 = primary_field3
        elif lidar.outer_lane is not None and lidar.inner_lane is not None:
            field4_upper = primary_lower - 1
            field4_lower = SOPAS_CENTER_ANGLE + math.floor(offset_left / SOPAS_MM_PER_DEGREE)
            if field4_lower > field4_upper:
                raise ValueError(f"LIDAR_{original_index}: 外側車道 Field 範圍計算失敗，請檢查中心點距離")
            center_outer = math.ceil((field4_upper + field4_lower) / 2)
            field4 = (field4_lower, field4_upper)
            field5 = (center_outer - 2, field4_upper + 2)
            field6 = (field4_lower - 2, center_outer + 2)

        results.append(
            SopasFieldResult(
                index=original_index,
                inner_lane=lidar.inner_lane,
                outer_lane=lidar.outer_lane,
                right_lane=lidar.right_lane,
                left_lane=lidar.left_lane,
                assigned=assigned,
                offset_value=offset_primary,
                field1=field1,
                field2=field2,
                field3=field3,
                field4=field4,
                field5=field5,
                field6=field6,
                center_inner=center_inner,
                center_outer=center_outer,
                debug_lines=[
                    f"內={lidar.inner_lane if lidar.inner_lane is not None else '—'} → {'Field1~Field3' if lidar.inner_lane is not None else '未配置'}",
                    f"外={lidar.outer_lane if lidar.outer_lane is not None else '—'} → {'Field4~Field6' if lidar.outer_lane is not None else '未配置'}",
                    f"{inner_label}半邊語意: Field2 靠{inner_label} / Field3 靠{outer_label}",
                    f"{outer_label}半邊語意: Field5 靠{inner_label} / Field6 靠{outer_label}",
                    f"主 offset = {center:.0f} - {inner_boundary:.0f} - {primary_lane_width:.0f} = {offset_primary:.0f}mm",
                    (
                        f"Field1 = {field1[0]}° ~ {field1[1]}° / Field2 = {field2[0]}° ~ {field2[1]}° / Field3 = {field3[0]}° ~ {field3[1]}°"
                        if field1 and field2 and field3
                        else "Field1~Field3 未配置"
                    ),
                    (
                        f"左側 offset = {center:.0f} - {outer_boundary:.0f} = {offset_left:.0f}mm / "
                        f"Field4 = {field4_lower}° ~ {field4_upper}° / Field5 = {field5[0]}° ~ {field5[1]}° / "
                        f"Field6 = {field6[0]}° ~ {field6[1]}°"
                    ) if lidar.outer_lane is not None and lidar.inner_lane is not None and field4 and field5 and field6 else (
                        f"Field4 = {field4[0]}° ~ {field4[1]}° / Field5 = {field5[0]}° ~ {field5[1]}° / Field6 = {field6[0]}° ~ {field6[1]}°"
                        if field4 and field5 and field6 else "Field4~Field6 未配置"
                    ),
                ],
            )
        )

    return results


def render_text_report(config: DeviceConfig, summary: LidarCalculationSummary) -> str:
    field_results = calculate_sopas_fields(config.lanes, config.lidars, config.traffic_mode) if config.lidars else []
    inner_label, outer_label = lane_slot_labels(config.traffic_mode)
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
    lines.append(f"  交通模式: {config.traffic_mode} ({inner_label}=內側, {outer_label}=外側)")
    lines.extend(["", "  【Lidar 輸入資訊】", "", f"  ┌─────────┬────────────┬────────────┬──────────────┐", f"  │ Lidar   │ {inner_label:<10} │ {outer_label:<10} │ 中心距離(mm) │", "  ├─────────┼────────────┼────────────┼──────────────┤"])
    for index, lidar in enumerate(config.lidars):
        inner_lane = f"Lane{lidar.inner_lane}" if lidar.inner_lane is not None else "—"
        outer_lane = f"Lane{lidar.outer_lane}" if lidar.outer_lane is not None else "—"
        lines.append(f"  │ LIDAR_{index} │ {inner_lane:<10} │ {outer_lane:<10} │ {lidar.center_distance_mm:>12.0f} │")
    lines.append("  └─────────┴────────────┴────────────┴──────────────┘")
    lines.extend(["", "  【計算結果】", "", "  ┌─────────┬────────────┬────────────┬──────────────┬──────────────┬──────────────┬──────────────┬────────┐", f"  │ Lidar   │ {inner_label:<10} │ {outer_label:<10} │ 中心距離(mm) │ scan_right   │ scan_left    │ 偏差值(mm)   │ 狀態   │", "  ├─────────┼────────────┼────────────┼──────────────┼──────────────┼──────────────┼──────────────┼────────┤"])
    for result in summary.results:
        status_map = {"normal": "✓ 正常", "warning": "⚠ 警告", "error": "✗ 錯誤"}
        inner_lane = f"Lane{result.inner_lane}" if result.inner_lane is not None else "—"
        outer_lane = f"Lane{result.outer_lane}" if result.outer_lane is not None else "—"
        lines.append(f"  │ LIDAR_{result.index} │ {inner_lane:<10} │ {outer_lane:<10} │ {result.center:>12.0f} │ {result.scan_right:>12.0f} │ {result.scan_left:>12.0f} │ {result.offset_value:>12.0f} │ {status_map[result.status]} │")
    lines.append("  └─────────┴────────────┴────────────┴──────────────┴──────────────┴──────────────┴──────────────┴────────┘")
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
        lines.extend(["", f"  LIDAR_{result.index} ({lanes_str}, center={result.center:.0f}mm):"])
        lines.extend(f"    {line}" for line in result.debug_lines)
    if field_results:
        lines.extend(["", "  【Field 範圍 / 偵錯資訊】", ""])
        for field in field_results:
            lanes_str = "+".join(f"Lane{lane}" for lane in field.assigned)
            def fmt(value: tuple[int, int] | None) -> str:
                return f"{value[0]}° ~ {value[1]}°" if value is not None else "—"
            lines.append(
                f"  LIDAR_{field.index} ({lanes_str}) | "
                f"F1 {fmt(field.field1)} | F2 {fmt(field.field2)} | F3 {fmt(field.field3)} | "
                f"F4 {fmt(field.field4)} | F5 {fmt(field.field5)} | F6 {fmt(field.field6)}"
            )
            lines.extend(f"    {line}" for line in field.debug_lines)
    lines.extend(["", "=" * 90, "  完成！", "=" * 90])
    return "\n".join(lines)
