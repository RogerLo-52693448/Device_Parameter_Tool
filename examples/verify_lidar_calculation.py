"""
Lidar 有效區計算驗證工具

用途: 互動式輸入車道與 Lidar 資訊，自動計算有效偵測範圍
執行: python examples/verify_lidar_calculation.py

計算邏輯:
  - 基���點: 內路肩護欄
  - center_distance: Lidar 到內路肩護欄的距離 (mm)
  - 右(right): 靠近護欄方向 (內側)
  - 左(left): 遠離護欄方向 (外側)
  - 跨車道補償: 非最內/最外邊界 +500mm
  - 偏差值: Lidar 安裝位置偏離理想位置的距離
  - scan 警告: 超過 5500mm 需拆分車道
  - 偏差值: 以「此 Lidar 負責的最右側車道之外側邊界」為基準（對所有 Lidar 一致）
  - 偏差值錯誤: 超出 ±1500mm（最後一顆且僅負責 1 車道除外）
"""

import json
import math
import os
from datetime import datetime
from pathlib import Path

SCAN_LIMIT = 5500.0          # mm, 超過此值需警告
OFFSET_ALERT_LIMIT = 1500.0  # mm, 偏差值超出此範圍視為錯誤
WIDTH_CONSISTENCY_WARNING_THRESHOLD = 500.0  # mm, 超過此值需提示量測差異
MAX_RECORDS_PER_SITE = 3     # 每個點位最多保留筆數
SOPAS_MM_PER_DEGREE = 200.0  # mm, SOPAS 每度對應距離
SOPAS_CENTER_ANGLE = 90      # 度, SOPAS 基準角度（90 度朝正下方）
RECORDS_FILE = "lidar_records.json"
VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"
MAX_VERSION_DISPLAY_LENGTH = 15
VERSION_TRUNCATE_VISIBLE_LENGTH = 12


def get_tool_version() -> str:
    """讀取專案根目錄 VERSION 檔案作為工具版本號。"""
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
    計算所有 Lidar 的 scan_right, scan_left, 偏差值

    Args:
        all_lanes: [(lane_number, width_mm), ...] 所有車道
        lidar_assignments: [[lane_numbers], ...] 每個 Lidar 負責的車道
        lidar_centers: [center_distance, ...] 每個 Lidar 的中心距離

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

        # 邊界計算
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

        # 偏差值計算（所有 Lidar 統一公式）:
        # offset_value (右側基準) = center - 前面所有 Lidar 負責車道總寬 - 此 Lidar 右側（最內側）車道寬
        #   = center - 此 Lidar 右側（最內側）車道的外側邊界（即內外側車道分界）
        # LIDAR_0 (最內側, 2車道): center - Lane0寬
        # LIDAR_1 (中間,   2車道): center - LIDAR_0負責總寬 - LIDAR_1右側車道寬
        # LIDAR_2 (最外側, 1車道): center - LIDAR_0負責總寬 - LIDAR_1負責總寬 - Lane4寬
        # 偏差值保留正負號：
        #   正值 = 安裝位置比車道外側邊界更外側
        #   負值 = 安裝位置在車道外側邊界的內側（即 Lidar 在車道範圍內）
        prev_lidars_total = 0.0
        for j in range(i):
            prev_assigned = sorted(lidar_assignments[j])
            prev_lidars_total += sum(lane_width_map[n] for n in prev_assigned)

        # 統一減去右側（最內側）車道寬，使所有 Lidar 的偏差值基準相同
        right_lane_width = lane_width_map[assigned[0]]
        offset_value = center - prev_lidars_total - right_lane_width

        # offset_left (外側基準) = center - outer_boundary
        #   = Lidar 中心到此 Lidar 負責車道最外側邊界的距離
        #   供 SOPAS Field4~6（外側車道）使用，確保左右側各自以對應邊界為基準
        offset_left = center - outer_boundary

        # 偏差值計算過程描述
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
    計算每個車道的座標範圍（座標從 0 開始）

    Lane0 = (0, Lane0寬)
    Lane1 = (Lane0寬, Lane0+Lane1寬)
    Lane2 = (Lane0+Lane1寬, Lane0+Lane1+Lane2寬)
    以此類推

    Args:
        all_lanes: [(lane_number, width_mm), ...] 所有車道（不需預先排序，函式內部會依車道編號排序）

    Returns:
        list of (lane_number, start_mm, end_mm)，依車道編號由小到大排列
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
    計算各 Lidar 在 SOPAS 軟體中的偵測角度範圍。

    基準：90 度對應感測器正下方，往右側護欄方向為正（角度增大），往左側為負（角度減小）。
    換算規則：1 度 = SOPAS_MM_PER_DEGREE mm（預設 200mm），
    小數點無條件向遠離零方向進位（正值取上整，負值取下整），以確保完整覆蓋車道。

    Args:
        all_lanes: [(lane_number, width_mm), ...] 所有車道
        lidar_assignments: [[lane_numbers], ...] 各 Lidar 負責的車道（由右側護欄往左排列）
        lidar_centers: 各 Lidar 的中心距離 (mm)，亦即各自 90 度位置到右側護欄的距離

    Returns:
        list of dicts（順序同 lidar_assignments）:
            index            - Lidar 序號
            assigned         - 負責車道清單
            right_dist_mm    - 此 Lidar 右側邊界到 90 度基準的距離 (mm)，正值=右側，負值=左側
            left_dist_mm     - 此 Lidar 左側邊界到 90 度基準的距離 (mm)
            right_angle      - 右側偵測角度上限 (度)
            left_angle       - 左側偵測角度下限 (度)
            assigned_width_mm - 此 Lidar 負責車道總寬 (mm)
    """
    sorted_lanes = sorted(all_lanes, key=lambda x: x[0])
    lane_width_map = {num: width for num, width in sorted_lanes}

    results = []
    if len(lidar_assignments) != len(lidar_centers):
        raise ValueError("SOPAS 計算所需的 Lidar 負責車道與中心距離數量不一致")

    for i, (assigned, center) in enumerate(zip(lidar_assignments, lidar_centers)):
        assigned_sorted = sorted(assigned)
        assigned_width = sum(lane_width_map[n] for n in assigned_sorted)
        right_dist = float(center)
        left_dist = right_dist - assigned_width

        # ceil 確保右側角度足以覆蓋整個右側邊界（正值向上、負值趨近零）
        right_deg = math.ceil(right_dist / SOPAS_MM_PER_DEGREE)
        # floor 確保左側角度足以覆蓋整個左側邊界（負值向負無窮，即更大的絕對值）
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
    計算各 Lidar 在 SOPAS 軟體中的 6 個 Field 偵測角度範圍。
    以 Dtmod_Primary Lidar 和 Dtmod_Backup Lidar 的偏差值為基礎計算。

    Field1~Field3：內側車道（靠近護欄）
    Field4~Field6：外側車道（遠離護欄，若 Lidar 只負責 1 個車道則為 None）

    計算公式（以 LIDAR_0 為例，內側車道 Lane0=4300mm，外側車道 Lane1=3800mm，偏差值=-300mm）：
      偏差值 offset_right = center - Lane0 = 4000 - 4300 = -300mm （內側基準，用於 Field1~3）
      偏差值 offset_left  = center - outer_boundary = 4000 - 8100 = -4100mm （外側基準，用於 Field4~6）
      Field1（內側車道完整範圍）:
        上界 = 90 + ceil((inner_lane_width + offset_right) / 200)  = 110°
        下界 = 90 + floor(offset_right / 200)                      = 88°
      中心點 = ceil((上界 + 下界) / 2) = 99°
      Field2（內側護欄半段，護欄側不額外補償）: (中心點-2) ~ 上界           = 97°~110°
      Field3（外側半段，兩側各補 2°）:         (下界-2) ~ (中心點+2)        = 86°~101°
      Field4（外側車道完整範圍，從外側邊界往內計算）:
        上界 = Field1 下界                                                   = 88°
        下界 = 90 + floor(offset_left / 200)                                 = 69°
      中心點 = ceil((Field4上界 + Field4下界) / 2) = 79°
      Field5（靠 Field1 側半段，兩側各補 2°）: (中心點-2) ~ (Field4上界+2)  = 77°~90°
      Field6（外側半段，兩側各補 2°）:         (Field4下界-2) ~ (中心點+2)  = 67°~81°

    Args:
        all_lanes: [(lane_number, width_mm), ...] 所有車道
        lidar_assignments: [[lane_numbers], ...] 各 Lidar 負責的車道（最多 2 個車道）
        lidar_centers: 各 Lidar 的中心距離 (mm)

    Returns:
        list of dicts（順序同 lidar_assignments）:
            index        - Lidar 序號
            assigned     - 負責車道清單
            offset_value - 偏差值 (mm)，來自 Dtmod 計算結果
            field1       - (lower_angle, upper_angle) 內側車道完整範圍 (度)
            field2       - (lower_angle, upper_angle) 內側車道護欄半段 (度)
            field3       - (lower_angle, upper_angle) 內側車道外側半段 (度)
            field4       - (lower_angle, upper_angle) 外側車道完整範圍，只有 1 車道則為 None
            field5       - (lower_angle, upper_angle) 外側車道靠 Field1 側半段，若無則為 None
            field6       - (lower_angle, upper_angle) 外側車道外側半段，若無則為 None
            center_inner - 內側車道中心角度 (度)
            center_outer - 外側車道中心角度 (度)，若無則為 None
    """
    dtmod_results = calculate_lidar_results(all_lanes, lidar_assignments, lidar_centers)
    sorted_lanes = sorted(all_lanes, key=lambda x: x[0])
    lane_width_map = {num: width for num, width in sorted_lanes}

    fields_list = []
    for r in dtmod_results:
        assigned = sorted(r["assigned"])
        offset = r["offset_value"]
        inner_lane_width = lane_width_map[assigned[0]]

        # Field1: 內側車道完整範圍
        # ceil 確保上界（護欄側）完整涵蓋；floor 確保下界（外側）完整涵蓋
        # (inner_lane_width + offset) = Lidar 到護欄側車道邊界的距離 (mm)
        # offset = Lidar 到內側車道外緣的距離 (mm)，負值表示 Lidar 偏向護欄側
        f1_upper = SOPAS_CENTER_ANGLE + math.ceil((inner_lane_width + offset) / SOPAS_MM_PER_DEGREE)
        f1_lower = SOPAS_CENTER_ANGLE + math.floor(offset / SOPAS_MM_PER_DEGREE)

        # 內側車道中心角度（無條件進位）
        center_inner = math.ceil((f1_upper + f1_lower) / 2)

        # Field2: 內側半段
        # - 最內側 Lidar：護欄側不額外補償
        # - 非最內側 Lidar：右側額外補 2°
        #   （Field 上界 = 較大角度，代表更靠右側／護欄側）
        f2_lower = center_inner - 2
        f2_upper = f1_upper if r["is_innermost"] else (f1_upper + 2)

        # Field3: 外側半段（兩側各補 2°）
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
            # Field4: 外側車道完整範圍
            # 使用 offset_left（= center - outer_boundary）作為外側基準，
            # 使左右兩側各自以對應邊界補償，不再共用 offset_right
            offset_left = r["offset_left"]
            f4_upper = f1_lower
            f4_lower = SOPAS_CENTER_ANGLE + math.floor(offset_left / SOPAS_MM_PER_DEGREE)

            # 外側車道中心角度（無條件進位）
            center_outer = math.ceil((f4_upper + f4_lower) / 2)

            # Field5: 靠 Field1 側半段（兩側各補 2°）
            f5_lower = center_outer - 2
            f5_upper = f4_upper + 2

            # Field6: 外側半段（兩側各補 2°）
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
    儲存一筆計算記錄，每個點位最多保留 MAX_RECORDS_PER_SITE 筆（超過自動刪除最早的）。

    Args:
        site_name: 點位名稱
        all_lanes: [(lane_num, width_mm), ...]
        lidar_assignments: [[lane_numbers], ...]
        lidar_centers: [center_distance, ...]
        results: calculate_lidar_results() 的回傳值
        records_file: 儲存檔案路徑 (預設 RECORDS_FILE)
        note: 備註字串，記錄此次儲存的原因（可留空）
        last_lidar_outer_dist: 最後一顆 Lidar 到外側護欄的距離 (mm)，可為 None
        has_backup: 是否啟用備援 Lidar
        backup_lidar_assignments: 備援 Lidar 負責車道
        backup_lidar_centers: 備援 Lidar 中心距離
        backup_results: 備援 Lidar 計算結果
        backup_last_lidar_outer_dist: 備援最後一顆 Lidar 到外側護欄的距離 (mm)，可為 None

    Returns:
        timestamp (str): 此筆記錄的時間戳記 (YYYYMMDDHHMM)
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
    讀取指定點位的所有歷史記錄。

    Args:
        site_name: 點位名稱
        records_file: 儲存檔案路徑 (預設 RECORDS_FILE)

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
    """判斷偏差值是否超出 ±1500mm 錯誤門檻（最後一顆且僅負責 1 車道可略過）。

    Args:
        offset_value: 偏差值（mm）
        skip_alert: 是否略過偏差值錯誤判斷

    Returns:
        bool: abs(offset_value) > OFFSET_ALERT_LIMIT 時為 True，否則為 False
    """
    if skip_alert:
        return False
    return abs(offset_value) > OFFSET_ALERT_LIMIT



def _print_result_tables(site_name, all_lanes, lidar_assignments, lidar_centers,
                          results, prev_results=None, last_lidar_outer_dist=None):
    """共用的結果顯示函式（可選傳入 prev_results 以顯示差異）。"""
    lidar_count = len(lidar_assignments)

    print()
    print("=" * 100)
    print(f"  計算結果 — {site_name}")
    print("=" * 100)

    # 車道資訊
    lane_coords = calculate_lane_coordinates(all_lanes)
    lane_coords_map = {num: (start, end) for num, start, end in lane_coords}
    print()
    print("  【車道資訊】")
    print()
    print("  ┌────────┬──────────┬──────────────────────────┐")
    print("  │ 車道   │ 寬度(mm) │ 座標範圍(mm)             │")
    print("  ├────────┼──────────┼──────────────────────────┤")
    for num, width in all_lanes:
        start, end = lane_coords_map[num]
        coord_str = f"{start:.0f} ~ {end:.0f}"
        print(f"  │ Lane{num}  │ {width:>8.0f} │ {coord_str:<26} │")
    print("  ├────────┼──────────┼──────────────────────────┤")
    print(f"  │ 合計   │ {sum(w for _, w in all_lanes):>8.0f} │ {'':26} │")
    print("  └────────┴──────────┴──────────────────────────┘")
    print()

    print("  [護欄]", end="")
    for num, width in all_lanes:
        print(f" |← Lane{num}:{width:.0f} →|", end="")
    print(" [外側]")
    print()

    # Lidar 輸入資訊
    print("  【Lidar 輸入資訊】")
    print()
    print("  ┌─────────┬────────────────┬──────────────┐")
    print("  │ Lidar   │ 負責車道       │ 中心距離(mm) │")
    print("  ├─────────┼────────────────┼──────────────┤")
    for i in range(lidar_count):
        lanes_str = "+".join([f"Lane{n}" for n in sorted(lidar_assignments[i])])
        print(f"  │ LIDAR_{i} │ {lanes_str:<14} │ {lidar_centers[i]:>12.0f} │")
    print("  └─────────┴────────────────┴──────────────┘")
    print()

    # 計算結果表格（含差異欄）
    print("  【計算結果】")
    print()
    if prev_results:
        print("  ┌─────────┬────────────────┬──────────────┬──────────────────────┬──────────────────────┬──────────────────────┬────────┐")
        print("  │ Lidar   │ 負責車道       │ 中心距離(mm) │ scan_right (差異)    │ scan_left (差異)     │ 偏差值(mm) (差異)    │ 狀態   │")
        print("  ├─────────┼────────────────┼──────────────┼──────────────────────┼──────────────────────┼──────────────────────┼────────┤")
    else:
        print("  ┌─────────┬────────────────┬──────────────┬──────────────┬──────────────┬──────────────┬────────┐")
        print("  │ Lidar   │ 負責車道       │ 中心距離(mm) │ scan_right   │ scan_left    │ 偏差值(mm)   │ 狀態   │")
        print("  ├─────────┼────────────────┼──────────────┼──────────────┼──────────────┼──────────────┼────────┤")

    def _diff(new_val, old_val):
        d = new_val - old_val
        return f"{new_val:.0f} ({'+' if d >= 0 else ''}{d:.0f})"

    warnings = []
    total_results = len(results)
    for r in results:
        lanes_str = "+".join([f"Lane{n}" for n in r["assigned"]])
        status = "✓ 正常"
        if r["scan_right"] > SCAN_LIMIT or r["scan_left"] > SCAN_LIMIT:
            status = "⚠ 警告"
            if r["scan_right"] > SCAN_LIMIT:
                warnings.append(f"LIDAR_{r['index']}: scan_right={r['scan_right']:.0f}mm 超過 {SCAN_LIMIT:.0f}mm 偵測上限")
            if r["scan_left"] > SCAN_LIMIT:
                warnings.append(f"LIDAR_{r['index']}: scan_left={r['scan_left']:.0f}mm 超過 {SCAN_LIMIT:.0f}mm 偵測上限")
        if _offset_is_error(
            r["offset_value"],
            skip_alert=is_last_single_lane_lidar(r, total_results=total_results),
        ):
            status = "✗ 錯誤"

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
        print("  ⚠️  警告訊息:")
        for w in warnings:
            print(f"    → {w}")
            print(f"      建議: 需要再拆分車道，增加 Lidar 數量以縮小偵測範圍")

    # 詳細計算過程
    print()
    print("  【詳細計算過程】")
    for r in results:
        lanes_str = "+".join([f"Lane{n}" for n in r["assigned"]])
        print()
        print(f"  LIDAR_{r['index']} ({lanes_str}, center={r['center']:.0f}mm):")
        print(f"    負責車道邊界: {r['inner_boundary']:.0f}mm ~ {r['outer_boundary']:.0f}mm")
        print(f"    最內側: {'是' if r['is_innermost'] else '否'} (右補償 +{r['right_compensation']:.0f}mm)")
        print(f"    最外側: {'是' if r['is_outermost'] else '否'} (左補償 +{r['left_compensation']:.0f}mm)")
        print(f"    scan_right = {r['center']:.0f} - {r['inner_boundary']:.0f} + {r['right_compensation']:.0f} = {r['scan_right']:.0f}mm")
        print(f"    scan_left  = {r['outer_boundary']:.0f} - {r['center']:.0f} + {r['left_compensation']:.0f} = {r['scan_left']:.0f}mm")
        print(f"    偏差值     = {r['offset_formula']} = {r['offset_value']:.0f}mm")

    # 路寬一致性檢核
    if last_lidar_outer_dist is not None:
        last_center = lidar_centers[-1]
        total_measured = last_center + last_lidar_outer_dist
        total_lanes = sum(w for _, w in all_lanes)
        diff = abs(total_measured - total_lanes)
        print()
        print("  【路寬一致性檢核】")
        print()
        print(f"    最後一顆 Lidar 中心距離 (到內側護欄) : {last_center:.0f} mm")
        print(f"    最後一顆 Lidar 到外側護欄距離        : {last_lidar_outer_dist:.0f} mm")
        print(f"    實測合計 (中心 + 外側)               : {total_measured:.0f} mm")
        print(f"    所有車道寬度加總                     : {total_lanes:.0f} mm")
        print(f"    差距                                 : {diff:.0f} mm")
        if diff >= WIDTH_CONSISTENCY_WARNING_THRESHOLD:
            print()
            print(
                f"  ⚠️  注意！實測合計與車道總寬差距達 {diff:.0f} mm "
                f"(≥ {WIDTH_CONSISTENCY_WARNING_THRESHOLD:.0f} mm)，請確認量測資料是否正確。"
            )
            warnings.append(
                f"路寬一致性: 實測合計={total_measured:.0f}mm vs 車道總寬={total_lanes:.0f}mm，"
                f"差距={diff:.0f}mm (≥{WIDTH_CONSISTENCY_WARNING_THRESHOLD:.0f}mm)"
            )
        else:
            print()
            print(
                f"  ✓ 路寬一致性正常，差距 {diff:.0f} mm "
                f"< {WIDTH_CONSISTENCY_WARNING_THRESHOLD:.0f} mm。"
            )

    print()
    print("=" * 100)
    print("  完成！")
    print("=" * 100)

    return warnings


def load_and_modify():
    """載入既有記錄並修改車道/中心點，重新計算後存為新一筆。"""
    print()
    site_name = input("請輸入點位名稱: ").strip()
    if not site_name:
        print("   ✗ 點位名稱不能為空")
        return

    records = load_records(site_name)
    if not records:
        print(f"   ✗ 找不到點位「{site_name}」的記錄，請先使用「全新輸入」建立資料。")
        return

    # 顯示歷史記錄清單
    print()
    print(f"  點位「{site_name}」共有 {len(records)} 筆記錄：")
    print()
    print("  ┌────┬──────────────┬──────────────────────────────────────────┬────────────┐")
    print("  │ #  │ 時間戳       │ 備註                                     │ 車道總寬   │")
    print("  ├────┼──────────────┼──────────────────────────────────────────┼────────────┤")
    for idx, rec in enumerate(records):
        ts = rec.get("timestamp", "未知")
        note = rec.get("note", "")
        total_w = sum(lane[1] for lane in rec["all_lanes"])
        print(f"  │ {idx+1:<2} │ {ts:<12} │ {note:<40} │ {total_w:>10.0f} │")
    print("  └────┴──────────────┴──────────────────────────────────────────┴────────────┘")
    print()

    # 選擇記錄
    while True:
        try:
            choice = int(input(f"  請選擇要載入的記錄編號 (1~{len(records)}): ").strip())
            if 1 <= choice <= len(records):
                break
            print(f"   ✗ 請輸入 1 到 {len(records)} 之間的數字")
        except ValueError:
            print("   ✗ 請輸入數字")

    base_rec = records[choice - 1]
    all_lanes = [tuple(lane) for lane in base_rec["all_lanes"]]
    lidar_assignments = base_rec["lidar_assignments"]
    lidar_centers = base_rec["lidar_centers"]
    prev_results = base_rec["results"]
    last_lidar_outer_dist = base_rec.get("last_lidar_outer_dist")

    print()
    print(f"  已載入第 {choice} 筆記錄（{base_rec.get('timestamp', '')}）")

    # ── 修改車道寬度 ──────────────────────────────────────────────
    print()
    print("  【修改車道寬度】（直接 Enter 保留原值）")
    new_lanes = []
    for num, width in all_lanes:
        while True:
            raw = input(f"   Lane{num} 目前寬度: {width:.0f}mm，新寬度 (Enter 保留): ").strip()
            if raw == "":
                new_lanes.append((num, width))
                break
            try:
                new_w = float(raw)
                if new_w <= 0:
                    print("   ✗ 寬度必須大於 0")
                    continue
                new_lanes.append((num, new_w))
                break
            except ValueError:
                print("   ✗ 請輸入數字")

    # ── 修改 Lidar 中心點距離 ────────────────────────────────────
    print()
    print("  【修改 Lidar 中心點距離】（直接 Enter 保留原值）")
    new_centers = []
    for i, center in enumerate(lidar_centers):
        while True:
            raw = input(f"   LIDAR_{i} 目前中心距離: {center:.0f}mm，新距離 (Enter 保留): ").strip()
            if raw == "":
                new_centers.append(center)
                break
            try:
                new_c = float(raw)
                if new_c < 0:
                    print("   ✗ 距離不可為負數")
                    continue
                new_centers.append(new_c)
                break
            except ValueError:
                print("   ✗ 請輸入數字")

    # ── 修改最後一顆 Lidar 到外側護欄的距離 ─────────────────────
    print()
    last_lidar_idx = len(lidar_assignments) - 1
    outer_display = f"{last_lidar_outer_dist:.0f}mm" if last_lidar_outer_dist is not None else "未設定"
    print(f"  【修改 LIDAR_{last_lidar_idx} 到外側護欄的距離】（直接 Enter 保留原值）")
    new_last_lidar_outer_dist = last_lidar_outer_dist
    while True:
        raw = input(f"   LIDAR_{last_lidar_idx} 目前外側護欄距離: {outer_display}，新距離 (Enter 保留): ").strip()
        if raw == "":
            break
        try:
            new_val = float(raw)
            new_last_lidar_outer_dist = new_val
            break
        except ValueError:
            print("   ✗ 請輸入數字")

    # ── 重新計算 ─────────────────────────────────────────────────
    new_results = calculate_lidar_results(new_lanes, lidar_assignments, new_centers)
    _print_result_tables(site_name, new_lanes, lidar_assignments, new_centers,
                         new_results, prev_results=prev_results,
                         last_lidar_outer_dist=new_last_lidar_outer_dist)

    # ── 儲存 ─────────────────────────────────────────────────────
    print()
    save_yn = input("  是否儲存此次結果？(y/n，預設 y): ").strip().lower()
    if save_yn in ("", "y", "yes"):
        note = input("  備註（說明調整原因，可留空）: ").strip()
        ts = save_result(site_name, new_lanes, lidar_assignments, new_centers,
                         new_results, note=note, last_lidar_outer_dist=new_last_lidar_outer_dist)
        records_now = load_records(site_name)
        print(f"  ✓ 已儲存！時間: {ts}，{site_name} 共 {len(records_now)} 筆記錄")
    else:
        print("  ✗ 略過儲存")
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
    print(f"║   Lidar 有效區計算驗證工具 v{version_display:<15}║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print("  請選擇操作模式：")
    print("  [1] 全新輸入")
    print("  [2] 載入既有記錄並修改")
    print()
    while True:
        mode = input("  請輸入選項 (1 或 2，預設 1): ").strip()
        if mode in ("", "1"):
            mode = "1"
            break
        if mode == "2":
            break
        print("   ✗ 請輸入 1 或 2")

    if mode == "2":
        load_and_modify()
        return

    print()
    # ── 1. 建立點位名稱 ──────────────────────────────────────────
    site_name = input("1. 請輸入點位名稱 (例如 03F-040.7N): ").strip()
    if not site_name:
        site_name = "未命名點位"
    print(f"   → 點位: {site_name}")
    print()

    # ── 2. 輸入車道數量 ──────────────────────────────────────────
    while True:
        try:
            lane_count = int(input("2. 請輸入車道數量: "))
            if lane_count < 1:
                print("   ✗ 車道數量至少為 1")
                continue
            break
        except ValueError:
            print("   ✗ 請輸入整數")
    print(f"   → 車道數量: {lane_count}")
    print()

    # ── 3. 輸入 Lidar 數量 ───────────────────────────────────────
    while True:
        try:
            lidar_count = int(input("3. 請輸入 Lidar 數量: "))
            if lidar_count < 1:
                print("   ✗ Lidar 數量至少為 1")
                continue
            break
        except ValueError:
            print("   ✗ 請輸入整數")
    print(f"   → Lidar 數量: {lidar_count}")
    print()

    # ── 4. 分別輸入每個車道寬度 ──────────────────────────────────
    print("4. 請分別輸入每個車道寬度 (mm):")
    all_lanes = []
    for i in range(lane_count):
        while True:
            try:
                width = float(input(f"   Lane{i} 寬度 (mm): "))
                if width <= 0:
                    print("   ✗ 寬度必須大於 0")
                    continue
                all_lanes.append((i, width))
                break
            except ValueError:
                print("   ✗ 請輸入數字")
    print()

    # ── 5. 輸入每個 Lidar 負責哪幾個車道 ─────────────────────────
    print("5. 請輸入每個 Lidar 負責的車道 (最多 2 個):")
    lidar_assignments = []
    for i in range(lidar_count):
        while True:
            raw = input(f"   LIDAR_{i} 負責車道編號 (逗號分隔, 例如 0,1): ").strip()
            try:
                assigned = [int(x.strip()) for x in raw.split(",") if x.strip()]
                if not assigned:
                    print("   ✗ 至少要指定 1 個車道")
                    continue
                if len(assigned) > 2:
                    print("   ✗ 最多負責 2 個車道")
                    continue
                valid = True
                for ln in assigned:
                    if ln < 0 or ln >= lane_count:
                        print(f"   ✗ 車道 Lane{ln} 不存在 (有效範圍: 0~{lane_count - 1})")
                        valid = False
                        break
                if not valid:
                    continue
                lidar_assignments.append(assigned)
                print(f"   → LIDAR_{i} 負責: Lane{assigned}")
                break
            except ValueError:
                print("   ✗ 請輸入數字，用逗號分隔")
    print()

    # ── 6. 輸入每個 Lidar 中心點距離 ─────────────────────────────
    print("6. 請輸入每個 Lidar 的中心點距離 (到內路肩護欄, mm):")
    lidar_centers = []
    for i in range(lidar_count):
        while True:
            try:
                center = float(input(f"   LIDAR_{i} 中心點距離 (mm): "))
                if center < 0:
                    print("   ✗ 距離不可為負數")
                    continue
                lidar_centers.append(center)
                break
            except ValueError:
                print("   ✗ 請輸入數字")

    # 最後一顆 Lidar 到外側護欄的距離
    last_lidar_outer_dist = None
    while True:
        try:
            raw = input(f"   LIDAR_{lidar_count - 1} 到外側護欄的距離 (mm): ")
            val = float(raw)
            last_lidar_outer_dist = val
            break
        except ValueError:
            print("   ✗ 請輸入數字")
    print()

    # ── 7. 計算並顯示結果 ────────────────────────────────────────
    results = calculate_lidar_results(all_lanes, lidar_assignments, lidar_centers)
    _print_result_tables(site_name, all_lanes, lidar_assignments, lidar_centers, results,
                         last_lidar_outer_dist=last_lidar_outer_dist)

    # ── 8. 儲存結果 ──────────────────────────────────────────────
    print()
    save_yn = input("  是否儲存此次結果？(y/n，預設 y): ").strip().lower()
    if save_yn in ("", "y", "yes"):
        note = input("  備註（說明此次輸入原因，可留空）: ").strip()
        ts = save_result(site_name, all_lanes, lidar_assignments, lidar_centers,
                         results, note=note, last_lidar_outer_dist=last_lidar_outer_dist)
        records = load_records(site_name)
        print(f"  ✓ 已儲存！時間: {ts}，{site_name} 共 {len(records)} 筆記錄")
    else:
        print("  ✗ 略過儲存")
    print()


if __name__ == "__main__":
    main()
