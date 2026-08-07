"""
Lidar Effective Zone Calculation Verification Tool

Purpose: Interactive input of lane and Lidar data to automatically calculate effective detection range
Run: python examples/verify_lidar_calculation.py

Calculation logic:
  - Reference point: inner shoulder barrier
  - center_distance: distance from Lidar to the inner shoulder barrier (mm)
  - right: toward the barrier (inner side)
  - left: away from the barrier (outer side)
  - Cross-lane compensation: +500mm for non-innermost/non-outermost boundaries
  - Offset: deviation of Lidar installation from the ideal position
  - scan warning: exceeding 5500mm requires splitting the lane
  - Offset: based on the outer boundary of the rightmost lane assigned to this Lidar (consistent for all Lidars)
  - Offset error: exceeds ±1500mm (except for the last Lidar responsible for only 1 lane)
"""

import json
import math
import os
from datetime import datetime
from pathlib import Path

SCAN_LIMIT = 5500.0          # mm, warn if exceeded
OFFSET_ALERT_LIMIT = 1500.0  # mm, treat as error if offset exceeds this
WIDTH_CONSISTENCY_WARNING_THRESHOLD = 500.0  # mm, warn if measurement difference exceeds this
MAX_RECORDS_PER_SITE = 3     # max records per site
SOPAS_MM_PER_DEGREE = 200.0  # mm per degree in SOPAS
SOPAS_CENTER_ANGLE = 90      # SOPAS reference angle (90° = straight down)
RECORDS_FILE = "lidar_records.json"
VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"
MAX_VERSION_DISPLAY_LENGTH = 15
VERSION_TRUNCATE_VISIBLE_LENGTH = 12


def get_tool_version() -> str:
    """Read the VERSION file in the project root directory as the tool version number."""
    try:
        with VERSION_FILE.open("r", encoding="utf-8") as f:
            version = f.read().strip()
            return version or "unknown"
    except OSError:
        return "unknown"


def calculate_lidar_results(
    all_lanes: list,
    lidar_assignments: list,
    lidar_centers: list,
):
    """
    Calculate scan_right, scan_left, and offset for all Lidars.

    Args:
        all_lanes: [(lane_number, width_mm), ...] all lanes
        lidar_assignments: [[lane_numbers], ...] lanes assigned to each Lidar
        lidar_centers: [center_distance, ...] center distance for each Lidar

    Returns:
        list of result dicts
    """
    all_lanes_sorted = sorted(all_lanes, key=lambda x: x[0])
    lane_width_map = {num: width for num, width in all_lanes_sorted}

    min_lane_number = all_lanes_sorted[0][0]
    max_lane_number = all_lanes_sorted[-1][0]

    results = []

    for i in range(len(lidar_assignments)):
        assigned = sorted(lidar_assignments[i])
        center = lidar_centers[i]

        min_assigned = assigned[0]
        max_assigned = assigned[-1]

        # Boundary calculation
        inner_boundary = sum(
            width for num, width in all_lanes_sorted if num < min_assigned
        )
        assigned_width = sum(lane_width_map[n] for n in assigned)
        outer_boundary = inner_boundary + assigned_width

        is_innermost = (min_assigned == min_lane_number)
        is_outermost = (max_assigned == max_lane_number)

        right_compensation = 0.0 if is_innermost else 500.0
        left_compensation = 0.0 if is_outermost else 500.0

        scan_right = center - inner_boundary + right_compensation
        scan_left = outer_boundary - center + left_compensation

        # Offset calculation (unified formula for all Lidars):
        # offset_value (right-side reference) = center - total width of lanes covered by preceding Lidars - width of this Lidar's rightmost (innermost) lane
        #   = center - outer boundary of this Lidar's rightmost (innermost) lane (i.e. the inner/outer lane boundary)
        # LIDAR_0 (innermost, 2 lanes): center - Lane0 width
        # LIDAR_1 (middle,    2 lanes): center - LIDAR_0 total width - LIDAR_1 rightmost lane width
        # LIDAR_2 (outermost, 1 lane):  center - LIDAR_0 total width - LIDAR_1 total width - Lane4 width
        # Offset preserves sign:
        #   positive = installation position is further out than the outer lane boundary
        #   negative = installation position is inside the outer lane boundary (Lidar is within the lane range)
        prev_lidars_total = 0.0
        for j in range(i):
            prev_assigned = sorted(lidar_assignments[j])
            prev_lidars_total += sum(lane_width_map[n] for n in prev_assigned)

        # Subtract the rightmost (innermost) lane width to normalize the offset reference across all Lidars
        right_lane_width = lane_width_map[assigned[0]]
        offset_value = center - prev_lidars_total - right_lane_width

        # offset_left (outer-side reference) = center - outer_boundary
        #   = distance from Lidar center to the outermost boundary of its assigned lanes
        #   used for SOPAS Field4~6 (outer lanes) so each side references its own boundary
        offset_left = center - outer_boundary

        # Offset calculation formula description
        if i == 0:
            offset_formula = f"{center:.0f} - Lane{assigned[0]}({lane_width_map[assigned[0]]:.0f})"
        else:
            prev_parts = []
            for j in range(i):
                for ln in sorted(lidar_assignments[j]):
                    prev_parts.append(f"Lane{ln}({lane_width_map[ln]:.0f})")
            prev_str = " + ".join(prev_parts)
            offset_formula = f"{center:.0f} - {prev_str} - Lane{assigned[0]}({lane_width_map[assigned[0]]:.0f})"

        results.append({
            "index": i,
            "assigned": assigned,
            "center": center,
            "scan_right": scan_right,
            "scan_left": scan_left,
            "offset_value": offset_value,
            "offset_left": offset_left,
            "offset_formula": offset_formula,
            "inner_boundary": inner_boundary,
            "outer_boundary": outer_boundary,
            "assigned_width": assigned_width,
            "is_innermost": is_innermost,
            "is_outermost": is_outermost,
            "right_compensation": right_compensation,
            "left_compensation": left_compensation,
        })

    return results


def calculate_lane_coordinates(all_lanes: list):
    """
    Calculate coordinate range for each lane (coordinates start at 0).

    Lane0 = (0, Lane0 width)
    Lane1 = (Lane0 width, Lane0+Lane1 width)
    Lane2 = (Lane0+Lane1 width, Lane0+Lane1+Lane2 width)
    and so on.

    Args:
        all_lanes: [(lane_number, width_mm), ...] all lanes (no pre-sorting required; sorted internally by lane number)

    Returns:
        list of (lane_number, start_mm, end_mm) sorted by lane number in ascending order
    """
    sorted_lanes = sorted(all_lanes, key=lambda x: x[0])
    coords = []
    cumulative = 0.0
    for num, width in sorted_lanes:
        coords.append((num, cumulative, cumulative + width))
        cumulative += width
    return coords


def calculate_sopas_angles(all_lanes: list, lidar_assignments: list, lidar_centers: list):
    """
    Calculate detection angle ranges for each Lidar in SOPAS software.

    Reference: 90° corresponds to directly below the sensor; angles increase toward the right barrier and decrease toward the left.
    Conversion rule: 1° = SOPAS_MM_PER_DEGREE mm (default 200 mm).
    Fractional values are rounded away from zero (positive values round up, negative values round down) to ensure full lane coverage.

    Args:
        all_lanes: [(lane_number, width_mm), ...] all lanes
        lidar_assignments: [[lane_numbers], ...] lanes assigned to each Lidar (ordered from right barrier to left)
        lidar_centers: center distance for each Lidar (mm), i.e. distance from each Lidar's 90° position to the right barrier

    Returns:
        list of dicts (same order as lidar_assignments):
            index            - Lidar index
            assigned         - assigned lanes
            right_dist_mm    - distance from this Lidar's right boundary to the 90° reference (mm); positive=right side, negative=left side
            left_dist_mm     - distance from this Lidar's left boundary to the 90° reference (mm)
            right_angle      - right detection angle upper limit (degrees)
            left_angle       - left detection angle lower limit (degrees)
            assigned_width_mm - total width of this Lidar's assigned lanes (mm)
    """
    sorted_lanes = sorted(all_lanes, key=lambda x: x[0])
    lane_width_map = {num: width for num, width in sorted_lanes}

    results = []
    if len(lidar_assignments) != len(lidar_centers):
        raise ValueError("Inconsistent Lidar lane assignments and center distances for SOPAS calculation")

    for i, (assigned, center) in enumerate(zip(lidar_assignments, lidar_centers)):
        assigned_sorted = sorted(assigned)
        assigned_width = sum(lane_width_map[n] for n in assigned_sorted)
        right_dist = float(center)
        left_dist = right_dist - assigned_width

        # ceil ensures the right angle fully covers the right boundary (positive rounds up, negative rounds toward zero)
        right_deg = math.ceil(right_dist / SOPAS_MM_PER_DEGREE)
        # floor ensures the left angle fully covers the left boundary (negative rounds toward negative infinity, i.e. larger absolute value)
        left_deg = math.floor(left_dist / SOPAS_MM_PER_DEGREE)

        results.append({
            "index": i,
            "assigned": assigned_sorted,
            "right_dist_mm": right_dist,
            "left_dist_mm": left_dist,
            "right_angle": SOPAS_CENTER_ANGLE + right_deg,
            "left_angle": SOPAS_CENTER_ANGLE + left_deg,
            "assigned_width_mm": assigned_width,
        })

    return results


def calculate_sopas_fields(all_lanes: list, lidar_assignments: list, lidar_centers: list):
    """
    Calculate the 6 Field detection angle ranges for each Lidar in SOPAS software.
    Based on the offsets from Dtmod_Primary Lidar and Dtmod_Backup Lidar.

    Field1~Field3: inner lanes (closer to barrier)
    Field4~Field6: outer lanes (farther from barrier; None if Lidar covers only 1 lane)

    Calculation example (LIDAR_0: inner lane Lane0=4300mm, outer lane Lane1=3800mm, offset=-300mm):
      offset_right = center - Lane0 = 4000 - 4300 = -300mm (inner reference, used for Field1~3)
      offset_left  = center - outer_boundary = 4000 - 8100 = -4100mm (outer reference, used for Field4~6)
      Field1 (full inner lane range):
        upper = 90 + ceil((inner_lane_width + offset_right) / 200)  = 110°
        lower = 90 + floor(offset_right / 200)                      = 88°
      center = ceil((upper + lower) / 2) = 99°
      Field2 (inner/barrier half, no extra compensation on barrier side): (center-2) ~ upper           = 97°~110°
      Field3 (outer half, +2° on each side):                             (lower-2) ~ (center+2)        = 86°~101°
      Field4 (full outer lane range, calculated from outer boundary inward):
        upper = Field1 lower                                                   = 88°
        lower = 90 + floor(offset_left / 200)                                 = 69°
      center = ceil((Field4 upper + Field4 lower) / 2) = 79°
      Field5 (Field1-side half, +2° on each side): (center-2) ~ (Field4 upper+2)  = 77°~90°
      Field6 (outer half, +2° on each side):        (Field4 lower-2) ~ (center+2)  = 67°~81°

    Args:
        all_lanes: [(lane_number, width_mm), ...] all lanes
        lidar_assignments: [[lane_numbers], ...] lanes assigned to each Lidar (max 2 per Lidar)
        lidar_centers: center distance for each Lidar (mm)

    Returns:
        list of dicts (same order as lidar_assignments):
            index        - Lidar index
            assigned     - assigned lanes
            offset_value - offset (mm), from Dtmod calculation result
            field1       - (lower_angle, upper_angle) full inner lane range (degrees)
            field2       - (lower_angle, upper_angle) inner lane barrier half (degrees)
            field3       - (lower_angle, upper_angle) inner lane outer half (degrees)
            field4       - (lower_angle, upper_angle) full outer lane range; None if only 1 lane
            field5       - (lower_angle, upper_angle) outer lane Field1-side half; None if absent
            field6       - (lower_angle, upper_angle) outer lane outer half; None if absent
            center_inner - inner lane center angle (degrees)
            center_outer - outer lane center angle (degrees); None if absent
    """
    dtmod_results = calculate_lidar_results(all_lanes, lidar_assignments, lidar_centers)
    sorted_lanes = sorted(all_lanes, key=lambda x: x[0])
    lane_width_map = {num: width for num, width in sorted_lanes}

    fields_list = []
    for r in dtmod_results:
        assigned = sorted(r["assigned"])
        offset = r["offset_value"]
        inner_lane_width = lane_width_map[assigned[0]]

        # Field1: full inner lane range
        # ceil ensures the upper bound (barrier side) is fully covered; floor ensures the lower bound (outer side) is fully covered
        # (inner_lane_width + offset) = distance from Lidar to the barrier-side lane boundary (mm)
        # offset = distance from Lidar to the outer edge of the inner lane (mm); negative means Lidar is shifted toward the barrier
        f1_upper = SOPAS_CENTER_ANGLE + math.ceil((inner_lane_width + offset) / SOPAS_MM_PER_DEGREE)
        f1_lower = SOPAS_CENTER_ANGLE + math.floor(offset / SOPAS_MM_PER_DEGREE)

        # Inner lane center angle (rounded up)
        center_inner = math.ceil((f1_upper + f1_lower) / 2)

        # Field2: inner half
        # - Innermost Lidar: no extra compensation on the barrier side
        # - Non-innermost Lidar: add 2° on the right side
        #   (Field upper bound = larger angle, representing further right/barrier side)
        f2_lower = center_inner - 2
        f2_upper = f1_upper if r["is_innermost"] else (f1_upper + 2)

        # Field3: outer half (+2° on each side)
        f3_lower = f1_lower - 2
        f3_upper = center_inner + 2

        entry = {
            "index": r["index"],
            "assigned": assigned,
            "offset_value": offset,
            "field1": (f1_lower, f1_upper),
            "field2": (f2_lower, f2_upper),
            "field3": (f3_lower, f3_upper),
            "center_inner": center_inner,
            "field4": None,
            "field5": None,
            "field6": None,
            "center_outer": None,
        }

        if len(assigned) == 2:
            # Field4: full outer lane range
            # Use offset_left (= center - outer_boundary) as the outer reference,
            # so each side references its own boundary compensation independently
            offset_left = r["offset_left"]
            f4_upper = f1_lower
            f4_lower = SOPAS_CENTER_ANGLE + math.floor(offset_left / SOPAS_MM_PER_DEGREE)

            # Outer lane center angle (rounded up)
            center_outer = math.ceil((f4_upper + f4_lower) / 2)

            # Field5: Field1-side half (+2° on each side)
            f5_lower = center_outer - 2
            f5_upper = f4_upper + 2

            # Field6: outer half (+2° on each side)
            f6_lower = f4_lower - 2
            f6_upper = center_outer + 2

            entry["field4"] = (f4_lower, f4_upper)
            entry["field5"] = (f5_lower, f5_upper)
            entry["field6"] = (f6_lower, f6_upper)
            entry["center_outer"] = center_outer

        fields_list.append(entry)

    return fields_list


def save_result(site_name, all_lanes, lidar_assignments, lidar_centers, results,
                records_file=None, note="", last_lidar_outer_dist=None,
                has_backup=False, backup_lidar_assignments=None,
                backup_lidar_centers=None, backup_results=None,
                backup_last_lidar_outer_dist=None):
    """
    Save a calculation record; each site keeps at most MAX_RECORDS_PER_SITE records (oldest is auto-deleted when exceeded).

    Args:
        site_name: site name
        all_lanes: [(lane_num, width_mm), ...]
        lidar_assignments: [[lane_numbers], ...]
        lidar_centers: [center_distance, ...]
        results: return value of calculate_lidar_results()
        records_file: file path for storage (default RECORDS_FILE)
        note: note string describing the reason for saving (may be empty)
        last_lidar_outer_dist: distance from the last Lidar to the outer barrier (mm); may be None
        has_backup: whether backup Lidar is enabled
        backup_lidar_assignments: assigned lanes for backup Lidar
        backup_lidar_centers: center distances for backup Lidar
        backup_results: calculation results for backup Lidar
        backup_last_lidar_outer_dist: distance from the last backup Lidar to the outer barrier (mm); may be None

    Returns:
        timestamp (str): timestamp of this record (YYYYMMDDHHMM)
    """
    if records_file is None:
        records_file = RECORDS_FILE

    all_records = {}
    if os.path.exists(records_file) and os.path.getsize(records_file) > 0:
        try:
            with open(records_file, "r", encoding="utf-8") as f:
                all_records = json.load(f)
        except json.JSONDecodeError:
            all_records = {}

    if site_name not in all_records:
        all_records[site_name] = []

    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    record = {
        "timestamp": timestamp,
        "note": note,
        "all_lanes": [list(lane) for lane in all_lanes],
        "has_backup": bool(has_backup),
        "lidar_assignments": lidar_assignments,
        "lidar_centers": lidar_centers,
        "last_lidar_outer_dist": last_lidar_outer_dist,
        "results": results,
        "backup_lidar_assignments": backup_lidar_assignments or [],
        "backup_lidar_centers": backup_lidar_centers or [],
        "backup_last_lidar_outer_dist": backup_last_lidar_outer_dist,
        "backup_results": backup_results or [],
    }

    all_records[site_name].append(record)

    if len(all_records[site_name]) > MAX_RECORDS_PER_SITE:
        all_records[site_name] = all_records[site_name][-MAX_RECORDS_PER_SITE:]

    with open(records_file, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    return timestamp


def load_records(site_name, records_file=None):
    """
    Load all history records for the specified site.

    Args:
        site_name: site name
        records_file: file path for storage (default RECORDS_FILE)

    Returns:
        list of record dicts (oldest first), or [] if none
    """
    if records_file is None:
        records_file = RECORDS_FILE

    if not os.path.exists(records_file):
        return []

    try:
        with open(records_file, "r", encoding="utf-8") as f:
            all_records = json.load(f)
    except json.JSONDecodeError:
        return []

    return all_records.get(site_name, [])


def is_last_single_lane_lidar(result, total_results=None):
    if total_results is None:
        return False
    return result.get("index") == (total_results - 1) and len(result.get("assigned", [])) == 1


def _offset_is_error(offset_value, skip_alert=False):
    """Determine whether the offset exceeds the ±1500mm error threshold (skipped for the last Lidar responsible for only 1 lane).

    Args:
        offset_value: offset (mm)
        skip_alert: whether to skip the offset error check

    Returns:
        bool: True when abs(offset_value) > OFFSET_ALERT_LIMIT, otherwise False
    """
    if skip_alert:
        return False
    return abs(offset_value) > OFFSET_ALERT_LIMIT



def _print_result_tables(site_name, all_lanes, lidar_assignments, lidar_centers,
                          results, prev_results=None, last_lidar_outer_dist=None):
    """Shared result display function (optionally accepts prev_results to show differences)."""
    lidar_count = len(lidar_assignments)

    print()
    print("=" * 100)
    print(f"  Results — {site_name}")
    print("=" * 100)

    # Lane info
    lane_coords = calculate_lane_coordinates(all_lanes)
    lane_coords_map = {num: (start, end) for num, start, end in lane_coords}
    print()
    print("  [Lane Info]")
    print()
    print("  ┌────────┬──────────┬──────────────────────────┐")
    print("  │ Lane   │ Width(mm)│ Coordinate Range(mm)     │")
    print("  ├────────┼──────────┼──────────────────────────┤")
    for num, width in all_lanes:
        start, end = lane_coords_map[num]
        coord_str = f"{start:.0f} ~ {end:.0f}"
        print(f"  │ Lane{num}  │ {width:>8.0f} │ {coord_str:<26} │")
    print("  ├────────┼──────────┼──────────────────────────┤")
    print(f"  │ Total  │ {sum(w for _, w in all_lanes):>8.0f} │ {'':26} │")
    print("  └────────┴──────────┴──────────────────────────┘")
    print()

    print("  [Barrier]", end="")
    for num, width in all_lanes:
        print(f" |← Lane{num}:{width:.0f} →|", end="")
    print(" [Outer]")
    print()

    # Lidar input info
    print("  [Lidar Input Info]")
    print()
    print("  ┌─────────┬────────────────┬──────────────┐")
    print("  │ Lidar   │ Assigned Lanes │ Center(mm)   │")
    print("  ├─────────┼────────────────┼──────────────┤")
    for i in range(lidar_count):
        lanes_str = "+".join([f"Lane{n}" for n in sorted(lidar_assignments[i])])
        print(f"  │ LIDAR_{i} │ {lanes_str:<14} │ {lidar_centers[i]:>12.0f} │")
    print("  └─────────┴────────────────┴──────────────┘")
    print()

    # Results table (with diff column)
    print("  [Results]")
    print()
    if prev_results:
        print("  ┌─────────┬────────────────┬──────────────┬──────────────────────┬──────────────────────┬──────────────────────┬────────┐")
        print("  │ Lidar   │ Assigned Lanes │ Center(mm)   │ scan_right (diff)    │ scan_left (diff)     │ Offset(mm) (diff)    │ Status │")
        print("  ├─────────┼────────────────┼──────────────┼──────────────────────┼──────────────────────┼──────────────────────┼────────┤")
    else:
        print("  ┌─────────┬────────────────┬──────────────┬──────────────┬──────────────┬──────────────┬────────┐")
        print("  │ Lidar   │ Assigned Lanes │ Center(mm)   │ scan_right   │ scan_left    │ Offset(mm)   │ Status │")
        print("  ├─────────┼────────────────┼──────────────┼──────────────┼──────────────┼──────────────┼────────┤")

    def _diff(new_val, old_val):
        d = new_val - old_val
        return f"{new_val:.0f} ({'+' if d >= 0 else ''}{d:.0f})"

    warnings = []
    total_results = len(results)
    for r in results:
        lanes_str = "+".join([f"Lane{n}" for n in r["assigned"]])
        status = "✓ OK"
        if r["scan_right"] > SCAN_LIMIT or r["scan_left"] > SCAN_LIMIT:
            status = "⚠ Warning"
            if r["scan_right"] > SCAN_LIMIT:
                warnings.append(f"LIDAR_{r['index']}: scan_right={r['scan_right']:.0f}mm exceeds {SCAN_LIMIT:.0f}mm detection limit")
            if r["scan_left"] > SCAN_LIMIT:
                warnings.append(f"LIDAR_{r['index']}: scan_left={r['scan_left']:.0f}mm exceeds {SCAN_LIMIT:.0f}mm detection limit")
        if _offset_is_error(
            r["offset_value"],
            skip_alert=is_last_single_lane_lidar(r, total_results=total_results),
        ):
            status = "✗ Error"

        if prev_results:
            pr = next((p for p in prev_results if p["index"] == r["index"]), None)
            sr_str = _diff(r["scan_right"], pr["scan_right"]) if pr else f"{r['scan_right']:.0f}"
            sl_str = _diff(r["scan_left"], pr["scan_left"]) if pr else f"{r['scan_left']:.0f}"
            ov_str = _diff(r["offset_value"], pr["offset_value"]) if pr else f"{r['offset_value']:.0f}"
            print(f"  │ LIDAR_{r['index']} │ {lanes_str:<14} │ {r['center']:>12.0f} │ {sr_str:<20} │ {sl_str:<20} │ {ov_str:<20} │ {status} │")
        else:
            print(f"  │ LIDAR_{r['index']} │ {lanes_str:<14} │ {r['center']:>12.0f} │ {r['scan_right']:>12.0f} │ {r['scan_left']:>12.0f} │ {r['offset_value']:>12.0f} │ {status} │")

    if prev_results:
        print("  └─────────┴────────────────┴──────────────┴──────────────────────┴──────────────────────┴──────────────────────┴────────┘")
    else:
        print("  └─────────┴────────────────┴──────────────┴──────────────┴──────────────┴──────────────┴────────┘")

    if warnings:
        print()
        print("  ⚠️  Warnings:")
        for w in warnings:
            print(f"    → {w}")
            print(f"      Suggestion: split the lane further and add more Lidars to reduce the detection range")

    # Calculation details
    print()
    print("  [Calculation Details]")
    for r in results:
        lanes_str = "+".join([f"Lane{n}" for n in r["assigned"]])
        print()
        print(f"  LIDAR_{r['index']} ({lanes_str}, center={r['center']:.0f}mm):")
        print(f"    Assigned lane boundary: {r['inner_boundary']:.0f}mm ~ {r['outer_boundary']:.0f}mm")
        print(f"    Innermost: {'Yes' if r['is_innermost'] else 'No'} (right compensation +{r['right_compensation']:.0f}mm)")
        print(f"    Outermost: {'Yes' if r['is_outermost'] else 'No'} (left compensation +{r['left_compensation']:.0f}mm)")
        print(f"    scan_right = {r['center']:.0f} - {r['inner_boundary']:.0f} + {r['right_compensation']:.0f} = {r['scan_right']:.0f}mm")
        print(f"    scan_left  = {r['outer_boundary']:.0f} - {r['center']:.0f} + {r['left_compensation']:.0f} = {r['scan_left']:.0f}mm")
        print(f"    Offset     = {r['offset_formula']} = {r['offset_value']:.0f}mm")

    # Lane width consistency check
    if last_lidar_outer_dist is not None:
        last_center = lidar_centers[-1]
        total_measured = last_center + last_lidar_outer_dist
        total_lanes = sum(w for _, w in all_lanes)
        diff = abs(total_measured - total_lanes)
        print()
        print("  [Lane Width Consistency Check]")
        print()
        print(f"    Last Lidar center distance (to inner barrier) : {last_center:.0f} mm")
        print(f"    Last Lidar to outer barrier distance          : {last_lidar_outer_dist:.0f} mm")
        print(f"    Measured total (center + outer)               : {total_measured:.0f} mm")
        print(f"    Sum of all lane widths                        : {total_lanes:.0f} mm")
        print(f"    Difference                                    : {diff:.0f} mm")
        if diff >= WIDTH_CONSISTENCY_WARNING_THRESHOLD:
            print()
            print(
                f"  ⚠️  Warning! Measured total vs total lane width difference is {diff:.0f} mm "
                f"(≥ {WIDTH_CONSISTENCY_WARNING_THRESHOLD:.0f} mm). Please verify measurement data."
            )
            warnings.append(
                f"Lane width consistency: measured total={total_measured:.0f}mm vs total lane width={total_lanes:.0f}mm, "
                f"difference={diff:.0f}mm (≥{WIDTH_CONSISTENCY_WARNING_THRESHOLD:.0f}mm)"
            )
        else:
            print()
            print(
                f"  ✓ Lane width consistency OK, difference {diff:.0f} mm "
                f"< {WIDTH_CONSISTENCY_WARNING_THRESHOLD:.0f} mm."
            )

    print()
    print("=" * 100)
    print("  Done!")
    print("=" * 100)

    return warnings


def load_and_modify():
    """Load an existing record, modify lane/center values, recalculate, and save as a new record."""
    print()
    site_name = input("Enter site name: ").strip()
    if not site_name:
        print("   ✗ Site name cannot be empty")
        return

    records = load_records(site_name)
    if not records:
        print(f"   ✗ No records found for site \"{site_name}\". Please use \"New Input\" to create data first.")
        return

    # Show history list
    print()
    print(f"  Site \"{site_name}\" has {len(records)} record(s):")
    print()
    print("  ┌────┬──────────────┬──────────────────────────────────────────┬────────────┐")
    print("  │ #  │ Timestamp    │ Note                                     │ Total Width│")
    print("  ├────┼──────────────┼──────────────────────────────────────────┼────────────┤")
    for idx, rec in enumerate(records):
        ts = rec.get("timestamp", "unknown")
        note = rec.get("note", "")
        total_w = sum(lane[1] for lane in rec["all_lanes"])
        print(f"  │ {idx+1:<2} │ {ts:<12} │ {note:<40} │ {total_w:>10.0f} │")
    print("  └────┴──────────────┴──────────────────────────────────────────┴────────────┘")
    print()

    # Select record
    while True:
        try:
            choice = int(input(f"  Select record number to load (1~{len(records)}): ").strip())
            if 1 <= choice <= len(records):
                break
            print(f"   ✗ Please enter a number between 1 and {len(records)}")
        except ValueError:
            print("   ✗ Please enter a number")

    base_rec = records[choice - 1]
    all_lanes = [tuple(lane) for lane in base_rec["all_lanes"]]
    lidar_assignments = base_rec["lidar_assignments"]
    lidar_centers = base_rec["lidar_centers"]
    prev_results = base_rec["results"]
    last_lidar_outer_dist = base_rec.get("last_lidar_outer_dist")

    print()
    print(f"  Loaded record #{choice} ({base_rec.get('timestamp', '')})")

    # ── Modify lane widths ──────────────────────────────────────────────
    print()
    print("  [Modify Lane Widths] (press Enter to keep current value)")
    new_lanes = []
    for num, width in all_lanes:
        while True:
            raw = input(f"   Lane{num} current width: {width:.0f}mm, new width (Enter to keep): ").strip()
            if raw == "":
                new_lanes.append((num, width))
                break
            try:
                new_w = float(raw)
                if new_w <= 0:
                    print("   ✗ Width must be greater than 0")
                    continue
                new_lanes.append((num, new_w))
                break
            except ValueError:
                print("   ✗ Please enter a number")

    # ── Modify Lidar center distances ────────────────────────────────────
    print()
    print("  [Modify Lidar Center Distances] (press Enter to keep current value)")
    new_centers = []
    for i, center in enumerate(lidar_centers):
        while True:
            raw = input(f"   LIDAR_{i} current center distance: {center:.0f}mm, new distance (Enter to keep): ").strip()
            if raw == "":
                new_centers.append(center)
                break
            try:
                new_c = float(raw)
                if new_c < 0:
                    print("   ✗ Distance cannot be negative")
                    continue
                new_centers.append(new_c)
                break
            except ValueError:
                print("   ✗ Please enter a number")

    # ── Modify last Lidar to outer barrier distance ──────────────────────
    print()
    last_lidar_idx = len(lidar_assignments) - 1
    outer_display = f"{last_lidar_outer_dist:.0f}mm" if last_lidar_outer_dist is not None else "not set"
    print(f"  [Modify LIDAR_{last_lidar_idx} to outer barrier distance] (press Enter to keep current value)")
    new_last_lidar_outer_dist = last_lidar_outer_dist
    while True:
        raw = input(f"   LIDAR_{last_lidar_idx} current outer barrier distance: {outer_display}, new distance (Enter to keep): ").strip()
        if raw == "":
            break
        try:
            new_val = float(raw)
            new_last_lidar_outer_dist = new_val
            break
        except ValueError:
            print("   ✗ Please enter a number")

    # ── Recalculate ──────────────────────────────────────────────────────
    new_results = calculate_lidar_results(new_lanes, lidar_assignments, new_centers)
    _print_result_tables(site_name, new_lanes, lidar_assignments, new_centers,
                         new_results, prev_results=prev_results,
                         last_lidar_outer_dist=new_last_lidar_outer_dist)

    # ── Save ─────────────────────────────────────────────────────────────
    print()
    save_yn = input("  Save this result? (y/n, default y): ").strip().lower()
    if save_yn in ("", "y", "yes"):
        note = input("  Note (explain reason for adjustment, may be empty): ").strip()
        ts = save_result(site_name, new_lanes, lidar_assignments, new_centers,
                         new_results, note=note, last_lidar_outer_dist=new_last_lidar_outer_dist)
        records_now = load_records(site_name)
        print(f"  ✓ Saved! Timestamp: {ts}, {site_name} has {len(records_now)} record(s)")
    else:
        print("  ✗ Save skipped")
    print()


def main():
    version = get_tool_version()
    version_display = (
        version
        if len(version) <= MAX_VERSION_DISPLAY_LENGTH
        else version[:VERSION_TRUNCATE_VISIBLE_LENGTH] + "..."
    )
    print()
    print("╔══════════════════════════════════════════════╗")
    print(f"║   Lidar Effective Zone Calculator v{version_display:<15}║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print("  Select operation mode:")
    print("  [1] New Input")
    print("  [2] Load existing record and modify")
    print()
    while True:
        mode = input("  Enter option (1 or 2, default 1): ").strip()
        if mode in ("", "1"):
            mode = "1"
            break
        if mode == "2":
            break
        print("   ✗ Please enter 1 or 2")

    if mode == "2":
        load_and_modify()
        return

    print()
    # ── 1. Site name ──────────────────────────────────────────────────
    site_name = input("1. Enter site name (e.g. 03F-040.7N): ").strip()
    if not site_name:
        site_name = "Unnamed Site"
    print(f"   → Site: {site_name}")
    print()

    # ── 2. Number of lanes ───────────────────────────────────────────
    while True:
        try:
            lane_count = int(input("2. Enter number of lanes: "))
            if lane_count < 1:
                print("   ✗ Number of lanes must be at least 1")
                continue
            break
        except ValueError:
            print("   ✗ Please enter an integer")
    print(f"   → Number of lanes: {lane_count}")
    print()

    # ── 3. Number of Lidars ──────────────────────────────────────────
    while True:
        try:
            lidar_count = int(input("3. Enter number of Lidars: "))
            if lidar_count < 1:
                print("   ✗ Number of Lidars must be at least 1")
                continue
            break
        except ValueError:
            print("   ✗ Please enter an integer")
    print(f"   → Number of Lidars: {lidar_count}")
    print()

    # ── 4. Lane widths ───────────────────────────────────────────────
    print("4. Enter width for each lane (mm):")
    all_lanes = []
    for i in range(lane_count):
        while True:
            try:
                width = float(input(f"   Lane{i} width (mm): "))
                if width <= 0:
                    print("   ✗ Width must be greater than 0")
                    continue
                all_lanes.append((i, width))
                break
            except ValueError:
                print("   ✗ Please enter a number")
    print()

    # ── 5. Assigned lanes per Lidar ─────────────────────────────────
    print("5. Enter assigned lanes for each Lidar (max 2 lanes):")
    lidar_assignments = []
    for i in range(lidar_count):
        while True:
            raw = input(f"   LIDAR_{i} assigned lane numbers (comma-separated, e.g. 0,1): ").strip()
            try:
                assigned = [int(x.strip()) for x in raw.split(",") if x.strip()]
                if not assigned:
                    print("   ✗ At least 1 lane must be assigned")
                    continue
                if len(assigned) > 2:
                    print("   ✗ At most 2 lanes can be assigned")
                    continue
                valid = True
                for ln in assigned:
                    if ln < 0 or ln >= lane_count:
                        print(f"   ✗ Lane{ln} does not exist (valid range: 0~{lane_count - 1})")
                        valid = False
                        break
                if not valid:
                    continue
                lidar_assignments.append(assigned)
                print(f"   → LIDAR_{i} assigned: Lane{assigned}")
                break
            except ValueError:
                print("   ✗ Please enter numbers separated by commas")
    print()

    # ── 6. Lidar center distances ────────────────────────────────────
    print("6. Enter center distance for each Lidar (to inner shoulder barrier, mm):")
    lidar_centers = []
    for i in range(lidar_count):
        while True:
            try:
                center = float(input(f"   LIDAR_{i} center distance (mm): "))
                if center < 0:
                    print("   ✗ Distance cannot be negative")
                    continue
                lidar_centers.append(center)
                break
            except ValueError:
                print("   ✗ Please enter a number")

    # Last Lidar to outer barrier distance
    last_lidar_outer_dist = None
    while True:
        try:
            raw = input(f"   LIDAR_{lidar_count - 1} to outer barrier distance (mm): ")
            val = float(raw)
            last_lidar_outer_dist = val
            break
        except ValueError:
            print("   ✗ Please enter a number")
    print()

    # ── 7. Calculate and display results ─────────────────────────────
    results = calculate_lidar_results(all_lanes, lidar_assignments, lidar_centers)
    _print_result_tables(site_name, all_lanes, lidar_assignments, lidar_centers, results,
                         last_lidar_outer_dist=last_lidar_outer_dist)

    # ── 8. Save results ───────────────────────────────────────────────
    print()
    save_yn = input("  Save this result? (y/n, default y): ").strip().lower()
    if save_yn in ("", "y", "yes"):
        note = input("  Note (explain reason for this input, may be empty): ").strip()
        ts = save_result(site_name, all_lanes, lidar_assignments, lidar_centers,
                         results, note=note, last_lidar_outer_dist=last_lidar_outer_dist)
        records = load_records(site_name)
        print(f"  ✓ Saved! Timestamp: {ts}, {site_name} has {len(records)} record(s)")
    else:
        print("  ✗ Save skipped")
    print()


if __name__ == "__main__":
    main()
