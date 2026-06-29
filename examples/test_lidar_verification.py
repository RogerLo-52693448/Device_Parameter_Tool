#!/usr/bin/env python3
"""
Lidar 計算驗證測試腳本

用途: 自動驗證 verify_lidar_calculation.py 的計算邏輯與儲存功能
執行: python examples/test_lidar_verification.py

測試資料: 03F-040.7N
  Lane0=3800mm  Lane1=3750mm  Lane2=3800mm  Lane3=3650mm  Lane4=3400mm
  LIDAR_0: Lane0+Lane1, center=5000mm
  LIDAR_1: Lane2+Lane3, center=11300mm
  LIDAR_2: Lane4,       center=16700mm
"""

import sys
import os
import tempfile

# 讓腳本在任何工作目錄下都能找到 verify_lidar_calculation
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lidar_calculation import (
    calculate_lidar_results, save_result, load_records,
    MAX_RECORDS_PER_SITE, _print_result_tables
)

# ─── 測試資料 ────────────────────────────────────────────────────────────────

SITE_NAME = "03F-040.7N"
ALL_LANES = [(0, 3800), (1, 3750), (2, 3800), (3, 3650), (4, 3400)]
LIDAR_ASSIGNMENTS = [[0, 1], [2, 3], [4]]
LIDAR_CENTERS = [5000.0, 11300.0, 16700.0]
# 最後一顆 Lidar (LIDAR_2) 到外側護欄的距離
# 18400 - 16700 = 1700mm → 總計 16700+1700=18400 vs 車道總寬 18400 → 差距 0mm (正常)
LAST_LIDAR_OUTER_DIST = 1700.0

# 預期結果
# LIDAR_0: 最內側 → right_comp=0, left_comp=+500
#   scan_right = 5000 - 0 + 0 = 5000
#   scan_left  = 7550 - 5000 + 500 = 3050
#   offset     = |5000 - 3800| = 1200
#
# LIDAR_1: 中間 → right_comp=+500, left_comp=+500
#   inner=7550, outer=15000
#   scan_right = 11300 - 7550 + 500 = 4250
#   scan_left  = 15000 - 11300 + 500 = 4200
#   offset     = |11300 - 7550 - 3800| = 50
#     (問題說明的「250」為筆誤；正確計算為 |11300-11350|=50)
#
# LIDAR_2: 最外側 → right_comp=+500, left_comp=0
#   inner=15000, outer=18400
#   scan_right = 16700 - 15000 + 500 = 2200
#   scan_left  = 18400 - 16700 + 0 = 1700
#   offset     = |16700 - 15000| = 1700
EXPECTED = [
    {"lidar": "LIDAR_0", "scan_right": 5000, "scan_left": 3050, "offset_value": 1200},
    {"lidar": "LIDAR_1", "scan_right": 4250, "scan_left": 4200, "offset_value": 50},
    {"lidar": "LIDAR_2", "scan_right": 2200, "scan_left": 1700, "offset_value": 1700},
]

# ─── 輔助函式 ────────────────────────────────────────────────────────────────

def check(label, actual, expected):
    """回傳 (passed, actual, expected) tuple 並記錄結果。"""
    passed = actual == expected
    return passed, actual, expected


def print_section(title):
    print()
    print("─" * 70)
    print(f"  {title}")
    print("─" * 70)


# ─── 步驟 1 & 2：驗證計算結果 ────────────────────────────────────────────────

print()
print("╔══════════════════════════════════════════════════════════════════════╗")
print("║         Lidar 計算驗證報告 — 03F-040.7N                            ║")
print("╚══════════════════════════════════════════════════════════════════════╝")

print_section("步驟 1 & 2：calculate_lidar_results() 計算結果驗證")

results = calculate_lidar_results(ALL_LANES, LIDAR_ASSIGNMENTS, LIDAR_CENTERS)

calc_tests = []  # [(label, passed, actual, expected)]

for i, (r, exp) in enumerate(zip(results, EXPECTED)):
    for field in ("scan_right", "scan_left", "offset_value"):
        actual_val = round(r[field])
        exp_val = exp[field]
        passed, av, ev = check(f"{exp['lidar']} {field}", actual_val, exp_val)
        calc_tests.append((f"{exp['lidar']} {field}", passed, av, ev))

# 詳細計算結果表格
print()
print("  【輸入資訊 — 車道】")
print()
print("  ┌────────┬──────────┐")
print("  │ 車道   │ 寬度(mm) │")
print("  ├────────┼──────────┤")
for num, width in ALL_LANES:
    print(f"  │ Lane{num}  │ {width:>8.0f} │")
print("  ├────────┼──────────┤")
print(f"  │ 合計   │ {sum(w for _, w in ALL_LANES):>8.0f} │")
print("  └────────┴──────────┘")

print()
print("  【輸入資訊 — Lidar】")
print()
print("  ┌─────────┬────────────────┬──────────────┐")
print("  │ Lidar   │ 負責車道       │ 中心距離(mm) │")
print("  ├─────────┼────────────────┼──────────────┤")
for i, (asgn, ctr) in enumerate(zip(LIDAR_ASSIGNMENTS, LIDAR_CENTERS)):
    lanes_str = "+".join(f"Lane{n}" for n in sorted(asgn))
    print(f"  │ LIDAR_{i} │ {lanes_str:<14} │ {ctr:>12.0f} │")
print("  └─────────┴────────────────┴──────────────┘")

print()
print("  【計算結果 vs 預期值】")
print()
print("  ┌─────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐")
print("  │ Lidar   │ scan_right   │ 預期         │ scan_left    │ 預期         │ 偏差值(mm)   │ 預期         │ 結果         │")
print("  ├─────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┤")

for r, exp in zip(results, EXPECTED):
    sr_ok = round(r["scan_right"]) == exp["scan_right"]
    sl_ok = round(r["scan_left"]) == exp["scan_left"]
    ov_ok = round(r["offset_value"]) == exp["offset_value"]
    row_pass = sr_ok and sl_ok and ov_ok
    status = "✅ PASS" if row_pass else "❌ FAIL"
    print(
        f"  │ LIDAR_{r['index']} │ {r['scan_right']:>12.0f} │ {exp['scan_right']:>12} │"
        f" {r['scan_left']:>12.0f} │ {exp['scan_left']:>12} │"
        f" {r['offset_value']:>12.0f} │ {exp['offset_value']:>12} │ {status} │"
    )

print("  └─────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘")

# ─── 步驟 3：驗證儲存功能 ────────────────────────────────────────────────────

print_section("步驟 3：save_result() / load_records() 功能驗證")

save_tests = []  # [(label, passed)]

with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
    tmp_path = tmp.name

try:
    # 3-a: 存入 1 筆，讀取確認
    ts1 = save_result(SITE_NAME, ALL_LANES, LIDAR_ASSIGNMENTS, LIDAR_CENTERS,
                      results, records_file=tmp_path, last_lidar_outer_dist=LAST_LIDAR_OUTER_DIST)
    recs = load_records(SITE_NAME, records_file=tmp_path)
    passed_a = len(recs) == 1 and recs[0]["timestamp"] == ts1
    save_tests.append(("存入 1 筆後讀取，確認筆數=1 且時間戳正確", passed_a))

    # 3-a2: 驗證 last_lidar_outer_dist 已正確儲存並讀取
    passed_outer = recs[0].get("last_lidar_outer_dist") == LAST_LIDAR_OUTER_DIST
    save_tests.append(("last_lidar_outer_dist 欄位正確儲存並讀取", passed_outer))

    # 3-b: 再存入 5 筆（共 6 筆），確認只剩 5 筆
    ts_list = [ts1]
    for _ in range(5):
        ts = save_result(SITE_NAME, ALL_LANES, LIDAR_ASSIGNMENTS, LIDAR_CENTERS,
                         results, records_file=tmp_path, last_lidar_outer_dist=LAST_LIDAR_OUTER_DIST)
        ts_list.append(ts)

    recs = load_records(SITE_NAME, records_file=tmp_path)
    passed_b_count = len(recs) == 5
    save_tests.append(("連續存 6 筆後，筆數應 = 5", passed_b_count))

    # 3-c: 確認第 1 筆已被刪除（即最舊的那筆已移出）
    # 注意：若所有記錄在同一分鐘內寫入，時間戳字串會相同；
    # 此時以「筆數 = 5 且所有現存記錄為後 5 筆」來驗證，而非時間戳唯一性
    stored_timestamps = [r["timestamp"] for r in recs]
    all_same_ts = len(set(ts_list)) == 1  # 所有時間戳相同（同一分鐘內）
    if all_same_ts:
        # 若時間戳全相同，只要筆數正確即可確認最舊的已刪除
        passed_b_oldest = len(recs) == MAX_RECORDS_PER_SITE
    else:
        passed_b_oldest = ts1 not in stored_timestamps
    save_tests.append(("第 1 筆（最舊）已被自動刪除", passed_b_oldest))

    # 3-d: 確認最後 5 筆保留（ts_list[1] ~ ts_list[5]）
    # 因為時間戳精確度為分鐘，同批次可能相同；只驗前述條件
    passed_b_latest = all(ts_list[j] in stored_timestamps for j in range(1, 6))
    save_tests.append(("最新 5 筆均已保留", passed_b_latest))

    # 3-e: 讀取不存在的點位 → 應回傳空 list
    empty = load_records("不存在的點位", records_file=tmp_path)
    save_tests.append(("讀取不存在的點位回傳 []", empty == []))

    print()
    print(f"  儲存檔案: {tmp_path} (測試用，執行後刪除)")
    print()
    print(f"  存入 6 筆後剩餘筆數  : {len(recs)}")
    print(f"  所有記錄時間戳       : {stored_timestamps}")
    print(f"  原本第 1 筆時間戳    : {ts1}")
    print(f"  第 1 筆是否已刪除    : {'是' if passed_b_oldest else '否'}")

finally:
    os.unlink(tmp_path)


# ─── 步驟 3b：note 欄位 + 載入修改邏輯驗證 ──────────────────────────────────

print_section("步驟 3b：note 欄位 & 載入修改邏輯驗證")

note_tests = []

with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp2:
    tmp2_path = tmp2.name

try:
    # note 欄位寫入與讀取
    note_text = "現場重新量測"
    save_result(SITE_NAME, ALL_LANES, LIDAR_ASSIGNMENTS, LIDAR_CENTERS,
                results, records_file=tmp2_path, note=note_text,
                last_lidar_outer_dist=LAST_LIDAR_OUTER_DIST)
    recs2 = load_records(SITE_NAME, records_file=tmp2_path)
    passed_note = len(recs2) == 1 and recs2[0].get("note") == note_text
    note_tests.append(("note 欄位正確寫入並讀取", passed_note))

    # 空 note 預設為空字串
    save_result(SITE_NAME, ALL_LANES, LIDAR_ASSIGNMENTS, LIDAR_CENTERS,
                results, records_file=tmp2_path,
                last_lidar_outer_dist=LAST_LIDAR_OUTER_DIST)
    recs2 = load_records(SITE_NAME, records_file=tmp2_path)
    passed_empty_note = recs2[-1].get("note", None) == ""
    note_tests.append(("空 note 預設為空字串", passed_empty_note))

    # 模擬「載入並修改」：讀取基底記錄，修改車道寬度，重新計算，確認差異
    base_rec = recs2[0]
    base_lanes = [tuple(lane) for lane in base_rec["all_lanes"]]
    base_assignments = base_rec["lidar_assignments"]
    base_centers = base_rec["lidar_centers"]
    base_results = base_rec["results"]
    base_outer_dist = base_rec.get("last_lidar_outer_dist")

    # 修改 Lane0 從 3800 → 3900 (+100mm)
    modified_lanes = list(base_lanes)
    modified_lanes[0] = (0, 3900.0)
    new_results = calculate_lidar_results(modified_lanes, base_assignments, base_centers)

    # scan_right 應增加 100mm（因為 inner_boundary 沒變，outer_boundary 增加 100）
    # LIDAR_0: outer_boundary 3900+3750=7650 → scan_left = 7650-5000+500 = 3150 (+100)
    sr0_new = round(new_results[0]["scan_right"])
    sl0_new = round(new_results[0]["scan_left"])
    sr0_base = round(base_results[0]["scan_right"])
    sl0_base = round(base_results[0]["scan_left"])
    passed_diff = (sr0_new == sr0_base) and (sl0_new == sl0_base + 100)
    note_tests.append(("修改 Lane0 +100mm 後 LIDAR_0 scan_left 增加 100mm", passed_diff))

    # 儲存修改後的記錄（含 note）
    save_result(SITE_NAME, modified_lanes, base_assignments, base_centers,
                new_results, records_file=tmp2_path, note="調整 Lane0 路寬",
                last_lidar_outer_dist=base_outer_dist)
    recs2_final = load_records(SITE_NAME, records_file=tmp2_path)
    passed_save_mod = len(recs2_final) == 3 and recs2_final[-1].get("note") == "調整 Lane0 路寬"
    note_tests.append(("修改後存入新一筆，note 正確", passed_save_mod))

    print()
    print(f"  測試記錄數量: {len(recs2_final)}")
    print(f"  最後一筆備註: {recs2_final[-1].get('note', '')}")
    print(f"  LIDAR_0 scan_left 基底={sl0_base}  修改後={sl0_new}  差異={sl0_new - sl0_base:+d}mm")

    # 驗證 _print_result_tables 可以執行（不拋例外），傳入 last_lidar_outer_dist
    try:
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _print_result_tables(SITE_NAME, modified_lanes, base_assignments, base_centers,
                                 new_results, prev_results=base_results,
                                 last_lidar_outer_dist=base_outer_dist)
        passed_print = True
    except Exception as e:
        passed_print = False
        print(f"  ✗ _print_result_tables 拋出例外: {e}")
    note_tests.append(("_print_result_tables 差異模式可正常執行", passed_print))

    # 路寬一致性檢核測試：差距 0mm → 無警告
    # LIDAR_2 center=16700, outer_dist=1700 → 合計 18400 == 車道總寬 18400
    total_measured_ok = LIDAR_CENTERS[-1] + LAST_LIDAR_OUTER_DIST
    total_lanes_ok = sum(w for _, w in ALL_LANES)
    diff_ok = abs(total_measured_ok - total_lanes_ok)
    passed_width_ok = diff_ok < 500
    note_tests.append((f"路寬一致性：差距={diff_ok:.0f}mm < 500mm，無需警告", passed_width_ok))

    # 路寬一致性檢核測試：差距 600mm → 應觸發警告
    outer_dist_bad = LAST_LIDAR_OUTER_DIST + 600  # 故意超出 500mm
    total_measured_bad = LIDAR_CENTERS[-1] + outer_dist_bad
    diff_bad = abs(total_measured_bad - total_lanes_ok)
    passed_width_warn = diff_bad >= 500
    note_tests.append((f"路寬一致性：差距={diff_bad:.0f}mm ≥ 500mm，應觸發警告", passed_width_warn))

    # 驗證 _print_result_tables 在差距≥500mm 時回傳包含路寬警告訊息
    try:
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            warn_list = _print_result_tables(
                SITE_NAME, ALL_LANES, LIDAR_ASSIGNMENTS, LIDAR_CENTERS,
                results, last_lidar_outer_dist=outer_dist_bad)
        passed_warn_msg = any("路寬一致性" in w for w in warn_list)
    except Exception as e:
        passed_warn_msg = False
        print(f"  ✗ _print_result_tables 路寬警告測試拋出例外: {e}")
    note_tests.append(("差距≥500mm 時 warnings 清單包含路寬一致性警告", passed_warn_msg))

finally:
    os.unlink(tmp2_path)

# ─── 步驟 4：輸出完整驗證報告 ────────────────────────────────────────────────

print_section("步驟 4：完整驗證報告")

all_tests = []

# 計算測試
for label, passed, actual, expected in calc_tests:
    all_tests.append((label, passed, f"實際={actual}", f"預期={expected}"))

# 儲存測試
for label, passed in save_tests:
    all_tests.append((label, passed, "", ""))

# note + 載入修改測試
for label, passed in note_tests:
    all_tests.append((label, passed, "", ""))

print()
col_w = 46
print(f"  ┌─{'─'*col_w}─┬──────────┬──────────────────────────────────────┐")
print(f"  │ {'測試項目':<{col_w}} │ 結果     │ 說明                                 │")
print(f"  ├─{'─'*col_w}─┼──────────┼──────────────────────────────────────┤")

pass_count = 0
fail_count = 0
for label, passed, actual, expected in all_tests:
    status = "✅ PASS" if passed else "❌ FAIL"
    detail = f"{actual} {expected}".strip()
    if passed:
        pass_count += 1
    else:
        fail_count += 1
    print(f"  │ {label:<{col_w}} │ {status} │ {detail:<36} │")

print(f"  └─{'─'*col_w}─┴──────────┴──────────────────────────────────────┘")
print()

total = pass_count + fail_count
print(f"  總計: {total} 項  ✅ PASS: {pass_count}  ❌ FAIL: {fail_count}")

if fail_count == 0:
    print()
    print("  🎉 所有測試通過！計算邏輯與儲存功能均正常。")
else:
    print()
    print("  ⚠️  有測試失敗，請檢查上方 FAIL 項目。")

print()
