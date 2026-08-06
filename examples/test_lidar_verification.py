#!/usr/bin/env python3
"""
Lidar Calculation Verification Test Script

Purpose: Automatically verify the calculation logic and storage functionality of verify_lidar_calculation.py
Run: python examples/test_lidar_verification.py

Test data: 03F-040.7N
  Lane0=3800mm  Lane1=3750mm  Lane2=3800mm  Lane3=3650mm  Lane4=3400mm
  LIDAR_0: Lane0+Lane1, center=5000mm
  LIDAR_1: Lane2+Lane3, center=11300mm
  LIDAR_2: Lane4,       center=16700mm
"""

import sys
import os
import tempfile

# Allow the script to find verify_lidar_calculation from any working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_lidar_calculation import (
    calculate_lidar_results, save_result, load_records,
    MAX_RECORDS_PER_SITE, WIDTH_CONSISTENCY_WARNING_THRESHOLD, SCAN_LIMIT,
    SOPAS_MM_PER_DEGREE, SOPAS_CENTER_ANGLE,
    _print_result_tables, calculate_sopas_fields,
)
from web_ui import (
    _compute_results_from_record,
    _form_from_record,
    _group_section_titles,
    _render_group_report_sections,
    _result_status,
    OFFSET_ALERT_LIMIT,
)

# ─── Test data ───────────────────────────────────────────────────────────────

SITE_NAME = "03F-040.7N"
ALL_LANES = [(0, 3800), (1, 3750), (2, 3800), (3, 3650), (4, 3400)]
LIDAR_ASSIGNMENTS = [[0, 1], [2, 3], [4]]
LIDAR_CENTERS = [5000.0, 11300.0, 16700.0]
# Last Lidar (LIDAR_2) to outer barrier distance
# 18400 - 16700 = 1700mm → total 16700+1700=18400 vs total lane width 18400 → difference 0mm (OK)
LAST_LIDAR_OUTER_DIST = 1700.0
BACKUP_LIDAR_ASSIGNMENTS = [[0], [1, 2], [3, 4]]
BACKUP_LIDAR_CENTERS = [2100.0, 9400.0, 15500.0]
BACKUP_LAST_LIDAR_OUTER_DIST = 2900.0
NEGATIVE_LAST_LIDAR_OUTER_DIST = -300.0
NEGATIVE_BACKUP_LAST_LIDAR_OUTER_DIST = -450.0

# Expected results
# LIDAR_0: innermost → right_comp=0, left_comp=+500
#   scan_right = 5000 - 0 + 0 = 5000
#   scan_left  = 7550 - 5000 + 500 = 3050
#   offset     = 5000 - 3800 = 1200
#
# LIDAR_1: middle → right_comp=+500, left_comp=+500
#   inner=7550, outer=15000
#   scan_right = 11300 - 7550 + 500 = 4250
#   scan_left  = 15000 - 11300 + 500 = 4200
#   offset     = 11300 - 7550 - 3800 = -50
#
# LIDAR_2: outermost → right_comp=+500, left_comp=0
#   inner=15000, outer=18400
#   scan_right = 16700 - 15000 + 500 = 2200
#   scan_left  = 18400 - 16700 + 0 = 1700
#   offset     = 16700 - 15000 - 3400 = -1700
EXPECTED = [
    {"lidar": "LIDAR_0", "scan_right": 5000, "scan_left": 3050, "offset_value": 1200},
    {"lidar": "LIDAR_1", "scan_right": 4250, "scan_left": 4200, "offset_value": -50},
    {"lidar": "LIDAR_2", "scan_right": 2200, "scan_left": 1700, "offset_value": -1700},
]

# ─── Helper functions ────────────────────────────────────────────────────────

def check(label, actual, expected):
    """Return (passed, actual, expected) tuple and record the result."""
    passed = actual == expected
    return passed, actual, expected


def print_section(title):
    print()
    print("─" * 70)
    print(f"  {title}")
    print("─" * 70)


# ─── Step 1 & 2: Verify calculation results ─────────────────────────────────

print()
print("╔══════════════════════════════════════════════════════════════════════╗")
print("║         Lidar Calculation Verification Report — 03F-040.7N         ║")
print("╚══════════════════════════════════════════════════════════════════════╝")

print_section("Step 1 & 2: calculate_lidar_results() Result Verification")

results = calculate_lidar_results(ALL_LANES, LIDAR_ASSIGNMENTS, LIDAR_CENTERS)

calc_tests = []  # [(label, passed, actual, expected)]

for i, (r, exp) in enumerate(zip(results, EXPECTED)):
    for field in ("scan_right", "scan_left", "offset_value"):
        actual_val = round(r[field])
        exp_val = exp[field]
        passed, av, ev = check(f"{exp['lidar']} {field}", actual_val, exp_val)
        calc_tests.append((f"{exp['lidar']} {field}", passed, av, ev))

# Detailed calculation results table
print()
print("  [Input Info — Lanes]")
print()
print("  ┌────────┬──────────┐")
print("  │ Lane   │ Width(mm)│")
print("  ├────────┼──────────┤")
for num, width in ALL_LANES:
    print(f"  │ Lane{num}  │ {width:>8.0f} │")
print("  ├────────┼──────────┤")
print(f"  │ Total  │ {sum(w for _, w in ALL_LANES):>8.0f} │")
print("  └────────┴──────────┘")

print()
print("  [Input Info — Lidar]")
print()
print("  ┌─────────┬────────────────┬──────────────┐")
print("  │ Lidar   │ Assigned Lanes │ Center(mm)   │")
print("  ├─────────┼────────────────┼──────────────┤")
for i, (asgn, ctr) in enumerate(zip(LIDAR_ASSIGNMENTS, LIDAR_CENTERS)):
    lanes_str = "+".join(f"Lane{n}" for n in sorted(asgn))
    print(f"  │ LIDAR_{i} │ {lanes_str:<14} │ {ctr:>12.0f} │")
print("  └─────────┴────────────────┴──────────────┘")

print()
print("  [Results vs Expected]")
print()
print("  ┌─────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐")
print("  │ Lidar   │ scan_right   │ Expected     │ scan_left    │ Expected     │ Offset(mm)   │ Expected     │ Result       │")
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

# ─── Step 3: Verify storage functionality ────────────────────────────────────

print_section("Step 3: save_result() / load_records() Functionality Verification")

save_tests = []  # [(label, passed)]

with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
    tmp_path = tmp.name

try:
    # 3-a: Save 1 record, read back and verify
    ts1 = save_result(SITE_NAME, ALL_LANES, LIDAR_ASSIGNMENTS, LIDAR_CENTERS,
                      results, records_file=tmp_path, note="record-0",
                      last_lidar_outer_dist=LAST_LIDAR_OUTER_DIST)
    recs = load_records(SITE_NAME, records_file=tmp_path)
    passed_a = len(recs) == 1 and recs[0]["timestamp"] == ts1
    save_tests.append(("Save 1 record and read back; verify count=1 and timestamp correct", passed_a))

    # 3-a2: Verify last_lidar_outer_dist is correctly saved and loaded
    passed_outer = recs[0].get("last_lidar_outer_dist") == LAST_LIDAR_OUTER_DIST
    save_tests.append(("last_lidar_outer_dist field saved and loaded correctly", passed_outer))

    # 3-b: Save MAX_RECORDS_PER_SITE more records; verify only the latest records are retained
    ts_list = [ts1]
    for idx in range(1, MAX_RECORDS_PER_SITE + 1):
        ts = save_result(SITE_NAME, ALL_LANES, LIDAR_ASSIGNMENTS, LIDAR_CENTERS,
                         results, records_file=tmp_path, note=f"record-{idx}",
                         last_lidar_outer_dist=LAST_LIDAR_OUTER_DIST)
        ts_list.append(ts)

    recs = load_records(SITE_NAME, records_file=tmp_path)
    passed_b_count = len(recs) == MAX_RECORDS_PER_SITE
    save_tests.append((f"After saving {MAX_RECORDS_PER_SITE + 1} records, count should = {MAX_RECORDS_PER_SITE}", passed_b_count))

    # 3-c: Verify record #1 (oldest) has been deleted
    stored_timestamps = [r["timestamp"] for r in recs]
    stored_notes = [r.get("note") for r in recs]
    passed_b_oldest = "record-0" not in stored_notes
    save_tests.append(("First (oldest) record has been auto-deleted", passed_b_oldest))

    # 3-d: Verify the latest MAX_RECORDS_PER_SITE records are retained
    expected_notes = [f"record-{idx}" for idx in range(1, MAX_RECORDS_PER_SITE + 1)]
    passed_b_latest = stored_notes == expected_notes
    save_tests.append((f"Latest {MAX_RECORDS_PER_SITE} records are all retained", passed_b_latest))

    # 3-e: Loading a nonexistent site should return an empty list
    empty = load_records("nonexistent-site", records_file=tmp_path)
    save_tests.append(("Loading nonexistent site returns []", empty == []))

    print()
    print(f"  Storage file: {tmp_path} (test only, deleted after run)")
    print()
    print(f"  Remaining count after saving {MAX_RECORDS_PER_SITE + 1} records: {len(recs)}")
    print(f"  All record timestamps : {stored_timestamps}")
    print(f"  All record notes      : {stored_notes}")
    print(f"  Original record #1 ts : {ts1}")
    print(f"  Record #1 deleted     : {'Yes' if passed_b_oldest else 'No'}")

finally:
    os.unlink(tmp_path)


# ─── Step 3b: note field + load-modify logic verification ────────────────────

print_section("Step 3b: note field & load-modify logic verification")

note_tests = []

with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp2:
    tmp2_path = tmp2.name

try:
    # note field write and read
    note_text = "Re-measured on site"
    save_result(SITE_NAME, ALL_LANES, LIDAR_ASSIGNMENTS, LIDAR_CENTERS,
                results, records_file=tmp2_path, note=note_text,
                last_lidar_outer_dist=LAST_LIDAR_OUTER_DIST)
    recs2 = load_records(SITE_NAME, records_file=tmp2_path)
    passed_note = len(recs2) == 1 and recs2[0].get("note") == note_text
    note_tests.append(("note field saved and loaded correctly", passed_note))

    # empty note defaults to empty string
    save_result(SITE_NAME, ALL_LANES, LIDAR_ASSIGNMENTS, LIDAR_CENTERS,
                results, records_file=tmp2_path,
                last_lidar_outer_dist=LAST_LIDAR_OUTER_DIST)
    recs2 = load_records(SITE_NAME, records_file=tmp2_path)
    passed_empty_note = recs2[-1].get("note", None) == ""
    note_tests.append(("empty note defaults to empty string", passed_empty_note))

    backup_results = calculate_lidar_results(ALL_LANES, BACKUP_LIDAR_ASSIGNMENTS, BACKUP_LIDAR_CENTERS)
    save_result(
        SITE_NAME,
        ALL_LANES,
        LIDAR_ASSIGNMENTS,
        LIDAR_CENTERS,
        results,
        records_file=tmp2_path,
        note="with backup config",
        last_lidar_outer_dist=LAST_LIDAR_OUTER_DIST,
        has_backup=True,
        backup_lidar_assignments=BACKUP_LIDAR_ASSIGNMENTS,
        backup_lidar_centers=BACKUP_LIDAR_CENTERS,
        backup_results=backup_results,
        backup_last_lidar_outer_dist=BACKUP_LAST_LIDAR_OUTER_DIST,
    )
    recs2 = load_records(SITE_NAME, records_file=tmp2_path)
    backup_rec = recs2[-1]
    passed_backup_saved = (
        backup_rec.get("has_backup") is True
        and backup_rec.get("backup_lidar_assignments") == BACKUP_LIDAR_ASSIGNMENTS
        and backup_rec.get("backup_lidar_centers") == BACKUP_LIDAR_CENTERS
        and backup_rec.get("backup_last_lidar_outer_dist") == BACKUP_LAST_LIDAR_OUTER_DIST
        and backup_rec.get("backup_results") == backup_results
    )
    note_tests.append(("backup settings fields saved and loaded correctly", passed_backup_saved))

    loaded_form = _form_from_record(SITE_NAME, backup_rec)
    passed_backup_form = (
        loaded_form.get("has_backup") is True
        and loaded_form.get("lidar_count") == len(LIDAR_CENTERS) + len(BACKUP_LIDAR_CENTERS)
        and loaded_form.get("backup_lidar_centers") == ["2100", "9400", "15500"]
        and loaded_form.get("backup_lidar_lanes_a") == [0, 1, 3]
        and loaded_form.get("backup_lidar_lanes_b") == [-1, 2, 4]
        and loaded_form.get("backup_last_lidar_outer_dist") == "2900"
    )
    note_tests.append(("loading history back-fills backup fields", passed_backup_form))

    loaded_groups, loaded_lanes, loaded_warnings = _compute_results_from_record(backup_rec)
    passed_backup_groups = (
        loaded_lanes == [(0, 3800.0), (1, 3750.0), (2, 3800.0), (3, 3650.0), (4, 3400.0)]
        and loaded_groups is not None
        and len(loaded_groups) == 2
        and loaded_groups[1]["label"] == "_Backup Lidar"
        and loaded_groups[1]["lidar_assignments"] == BACKUP_LIDAR_ASSIGNMENTS
        and loaded_groups[1]["lidar_centers"] == BACKUP_LIDAR_CENTERS
        and isinstance(loaded_warnings, list)
    )
    note_tests.append(("loading history reconstructs backup Lidar data", passed_backup_groups))

    primary_titles = _group_section_titles("Primary Lidar")
    passed_primary_titles = primary_titles == (
        "Distance From Center Island_Primary Lidar",
        "Dtmod_Primary Lidar",
    )
    note_tests.append(("Primary report titles show Primary Lidar", passed_primary_titles))

    backup_titles = _group_section_titles("_Backup Lidar")
    passed_backup_titles = backup_titles == (
        "Distance From Center Island_Backup Lidar",
        "Dtmod_Backup Lidar",
    )
    note_tests.append(("Backup report titles show _Backup Lidar", passed_backup_titles))

    primary_report_html = _render_group_report_sections(
        "Primary Lidar",
        ALL_LANES,
        LIDAR_ASSIGNMENTS,
        LIDAR_CENTERS,
        results,
        LAST_LIDAR_OUTER_DIST,
    )
    passed_primary_section_titles = (
        "Calculation formula_Primary Lidar" in primary_report_html
        and "Roadway width check_Primary Lidar" in primary_report_html
    )
    note_tests.append(("Primary calculation details and width check titles are in English", passed_primary_section_titles))

    backup_report_html = _render_group_report_sections(
        "_Backup Lidar",
        ALL_LANES,
        BACKUP_LIDAR_ASSIGNMENTS,
        BACKUP_LIDAR_CENTERS,
        backup_results,
        BACKUP_LAST_LIDAR_OUTER_DIST,
    )
    passed_backup_section_titles = (
        "Calculation formula_Backup Lidar" in backup_report_html
        and "Roadway width check_Backup Lidar" in backup_report_html
    )
    note_tests.append(("Backup calculation details and width check titles are in English", passed_backup_section_titles))

    # ── SOPAS Tool Field1~Field6 calculation tests ────────────────────────────
    # Verified example (confirmed by user):
    #   Lane0=4300mm, Lane1=3800mm, center=4000mm
    #   offset_right = center - Lane0 = 4000 - 4300 = -300mm
    #   offset_left  = center - outer_boundary = 4000 - 8100 = -4100mm
    #   f1_upper=90+ceil((4300+(-300))/200)=90+20=110, f1_lower=90+floor(-300/200)=90+(-2)=88
    #   center_inner=ceil(99)=99
    #   Field2 (innermost Lidar) no extra compensation on barrier side: (97, 110)
    #   f4_lower=90+floor(-4100/200)=90+(-21)=69, center_outer=ceil((88+69)/2)=ceil(78.5)=79
    sopas_user_lanes = [(0, 4300.0), (1, 3800.0)]
    sopas_user_assignments = [[0, 1]]
    sopas_user_centers = [4000.0]
    sopas_fields_user = calculate_sopas_fields(sopas_user_lanes, sopas_user_assignments, sopas_user_centers)
    fr0 = sopas_fields_user[0]
    passed_sopas_user_example = (
        len(sopas_fields_user) == 1
        and fr0["field1"] == (88, 110)
        and fr0["center_inner"] == 99
        and fr0["field2"] == (97, 110)
        and fr0["field3"] == (86, 101)
        and fr0["field4"] == (69, 88)
        and fr0["center_outer"] == 79
        and fr0["field5"] == (77, 90)
        and fr0["field6"] == (67, 81)
    )
    note_tests.append(("SOPAS Field1~Field6 verified example calculation correct", passed_sopas_user_example))

    # Verify positive offset (offset=+1200) rounding
    # LIDAR_0: Lane0=3800, Lane1=3750, center=5000
    #   offset = 5000 - 3800 = 1200
    #   f1_upper=90+ceil((3800+1200)/200)=90+ceil(25)=115
    #   f1_lower=90+floor(1200/200)=90+6=96
    #   center_inner=ceil(105.5)=106
    sopas_fields_main = calculate_sopas_fields(ALL_LANES, LIDAR_ASSIGNMENTS, LIDAR_CENTERS)
    fr_l0 = sopas_fields_main[0]  # LIDAR_0
    passed_sopas_positive_offset = (
        fr_l0["field1"] == (96, 115)
        and fr_l0["center_inner"] == 106
        and fr_l0["field2"] == (104, 115)
        and fr_l0["field2"][1] == fr_l0["field1"][1]
        and fr_l0["field3"] == (94, 108)
        and fr_l0["field4"] is not None
    )
    note_tests.append(("SOPAS Field1~Field3 positive offset calculation correct (offset=1200)", passed_sopas_positive_offset))

    # Verify small negative offset (LIDAR_1 offset_right=-50) floor rounding
    # LIDAR_1: Lane2=3800, Lane3=3650, center=11300
    #   offset_right = 11300 - 7550 - 3800 = -50
    #   offset_left  = 11300 - 15000 = -3700
    #   f1_upper=90+ceil((3800+(-50))/200)=90+ceil(18.75)=90+19=109
    #   f1_lower=90+floor(-50/200)=90+floor(-0.25)=90+(-1)=89
    #   center_inner=ceil(99)=99
    #   f4_lower=90+floor(-3700/200)=90+floor(-18.5)=90+(-19)=71
    #   center_outer=ceil((89+71)/2)=ceil(80)=80
    fr_l1 = sopas_fields_main[1]  # LIDAR_1
    passed_sopas_small_neg_offset = (
        fr_l1["field1"] == (89, 109)
        and fr_l1["center_inner"] == 99
        and fr_l1["field2"] == (97, 111)
        and fr_l1["field2"][1] == (fr_l1["field1"][1] + 2)
        and fr_l1["field4"] == (71, 89)
        and fr_l1["center_outer"] == 80
    )
    note_tests.append(("SOPAS Field1/Field4 small negative offset calculation correct (offset=-50)", passed_sopas_small_neg_offset))

    # Verify single-lane Lidar (LIDAR_2, only Lane4) has no Field4~Field6
    # LIDAR_2: Lane4=3400, center=16700
    #   offset = 16700 - 15000 - 3400 = -1700
    #   f1_upper=90+ceil((3400+(-1700))/200)=90+ceil(8.5)=90+9=99
    #   f1_lower=90+floor(-1700/200)=90+floor(-8.5)=90+(-9)=81
    fr_l2 = sopas_fields_main[2]  # LIDAR_2 (single lane)
    passed_sopas_single_lane = (
        fr_l2["field1"] == (81, 99)
        and fr_l2["field4"] is None
        and fr_l2["field5"] is None
        and fr_l2["field6"] is None
        and fr_l2["center_outer"] is None
    )
    note_tests.append(("SOPAS single-lane Lidar has no Field4~Field6", passed_sopas_single_lane))

    # Verify SOPAS Field1~Field6 report section appears in HTML
    sopas_html = _render_group_report_sections(
        "Primary Lidar",
        ALL_LANES,
        LIDAR_ASSIGNMENTS,
        LIDAR_CENTERS,
        results,
        LAST_LIDAR_OUTER_DIST,
    )
    passed_sopas_html = (
        "SOPAS Tool_Primary Lidar" in sopas_html
        and "Field1(°)" in sopas_html
        and "Field4(°)" in sopas_html
        and "Field6(°)" in sopas_html
    )
    note_tests.append(("SOPAS Tool Field1~Field6 report section appears in Primary Lidar HTML", passed_sopas_html))

    # Verify backup Lidar also shows SOPAS section title
    auto_sopas_html = _render_group_report_sections(
        "Primary Lidar",
        ALL_LANES,
        LIDAR_ASSIGNMENTS,
        LIDAR_CENTERS,
        results,
        LAST_LIDAR_OUTER_DIST,
    )
    passed_auto_sopas_html = "SOPAS Tool_Primary Lidar" in auto_sopas_html
    note_tests.append(("SOPAS Tool section title shows correctly as Primary Lidar", passed_auto_sopas_html))

    save_result(
        SITE_NAME,
        ALL_LANES,
        LIDAR_ASSIGNMENTS,
        LIDAR_CENTERS,
        results,
        records_file=tmp2_path,
        note="Negative outer-barrier distance",
        last_lidar_outer_dist=NEGATIVE_LAST_LIDAR_OUTER_DIST,
        has_backup=True,
        backup_lidar_assignments=BACKUP_LIDAR_ASSIGNMENTS,
        backup_lidar_centers=BACKUP_LIDAR_CENTERS,
        backup_results=backup_results,
        backup_last_lidar_outer_dist=NEGATIVE_BACKUP_LAST_LIDAR_OUTER_DIST,
    )
    negative_outer_rec = load_records(SITE_NAME, records_file=tmp2_path)[-1]
    negative_outer_form = _form_from_record(SITE_NAME, negative_outer_rec)
    passed_negative_outer = (
        negative_outer_rec.get("last_lidar_outer_dist") == NEGATIVE_LAST_LIDAR_OUTER_DIST
        and negative_outer_rec.get("backup_last_lidar_outer_dist") == NEGATIVE_BACKUP_LAST_LIDAR_OUTER_DIST
        and negative_outer_form.get("last_lidar_outer_dist") == "-300"
        and negative_outer_form.get("backup_last_lidar_outer_dist") == "-450"
    )
    note_tests.append(("Primary/backup last Lidar outer distance saves and loads negative values correctly", passed_negative_outer))

    # Simulate "load and modify": read base record, adjust lane width, recalculate, check diff
    base_rec = recs2[0]
    base_lanes = [tuple(lane) for lane in base_rec["all_lanes"]]
    base_assignments = base_rec["lidar_assignments"]
    base_centers = base_rec["lidar_centers"]
    base_results = base_rec["results"]
    base_outer_dist = base_rec.get("last_lidar_outer_dist")

    # Modify Lane0 from 3800 → 3900 (+100mm)
    modified_lanes = list(base_lanes)
    modified_lanes[0] = (0, 3900.0)
    new_results = calculate_lidar_results(modified_lanes, base_assignments, base_centers)

    # scan_left should increase by 100mm (inner_boundary unchanged, outer_boundary +100)
    # LIDAR_0: outer_boundary 3900+3750=7650 → scan_left = 7650-5000+500 = 3150 (+100)
    sr0_new = round(new_results[0]["scan_right"])
    sl0_new = round(new_results[0]["scan_left"])
    sr0_base = round(base_results[0]["scan_right"])
    sl0_base = round(base_results[0]["scan_left"])
    passed_diff = (sr0_new == sr0_base) and (sl0_new == sl0_base + 100)
    note_tests.append(("Modifying Lane0 +100mm increases LIDAR_0 scan_left by 100mm", passed_diff))

    # Save modified record (with note)
    save_result(SITE_NAME, modified_lanes, base_assignments, base_centers,
                new_results, records_file=tmp2_path, note="Adjusted Lane0 width",
                last_lidar_outer_dist=base_outer_dist)
    recs2_final = load_records(SITE_NAME, records_file=tmp2_path)
    passed_save_mod = len(recs2_final) == MAX_RECORDS_PER_SITE and recs2_final[-1].get("note") == "Adjusted Lane0 width"
    note_tests.append(("Modified record saved with correct note", passed_save_mod))

    print()
    print(f"  Record count: {len(recs2_final)}")
    print(f"  Last record note: {recs2_final[-1].get('note', '')}")
    print(f"  LIDAR_0 scan_left base={sl0_base}  modified={sl0_new}  diff={sl0_new - sl0_base:+d}mm")

    # Verify _print_result_tables runs without exception (passing last_lidar_outer_dist)
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
        print(f"  ✗ _print_result_tables raised exception: {e}")
    note_tests.append(("_print_result_tables diff mode runs without exception", passed_print))

    # Lane width consistency check: diff 0mm → no warning
    # LIDAR_2 center=16700, outer_dist=1700 → total 18400 == total lane width 18400
    total_measured_ok = LIDAR_CENTERS[-1] + LAST_LIDAR_OUTER_DIST
    total_lanes_ok = sum(w for _, w in ALL_LANES)
    diff_ok = abs(total_measured_ok - total_lanes_ok)
    passed_width_ok = diff_ok < WIDTH_CONSISTENCY_WARNING_THRESHOLD
    note_tests.append((
        f"Lane width consistency: diff={diff_ok:.0f}mm < {WIDTH_CONSISTENCY_WARNING_THRESHOLD:.0f}mm, no warning needed",
        passed_width_ok
    ))

    # Lane width consistency check: diff 600mm → should trigger warning
    outer_dist_bad = LAST_LIDAR_OUTER_DIST + 600  # intentionally exceed warning threshold
    total_measured_bad = LIDAR_CENTERS[-1] + outer_dist_bad
    diff_bad = abs(total_measured_bad - total_lanes_ok)
    passed_width_warn = diff_bad >= WIDTH_CONSISTENCY_WARNING_THRESHOLD
    note_tests.append((
        f"Lane width consistency: diff={diff_bad:.0f}mm >= {WIDTH_CONSISTENCY_WARNING_THRESHOLD:.0f}mm, warning expected",
        passed_width_warn
    ))

    # Verify _print_result_tables returns width warning message when diff >= 500mm
    try:
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            warn_list = _print_result_tables(
                SITE_NAME, ALL_LANES, LIDAR_ASSIGNMENTS, LIDAR_CENTERS,
                results, last_lidar_outer_dist=outer_dist_bad)
        passed_warn_msg = any("Lane width consistency" in w for w in warn_list)
    except Exception as e:
        passed_warn_msg = False
        print(f"  ✗ _print_result_tables width warning test raised exception: {e}")
    note_tests.append(("diff >= 500mm: warnings list contains lane width consistency warning", passed_warn_msg))

    base_status_result = {"scan_right": 5000.0, "scan_left": 3050.0, "offset_value": 0.0, "index": 0, "assigned": [0, 1]}
    status_threshold_tests = [
        ({**base_status_result, "offset_value": OFFSET_ALERT_LIMIT - 1}, "OK"),
        ({**base_status_result, "offset_value": OFFSET_ALERT_LIMIT}, "OK"),
        ({**base_status_result, "offset_value": -(OFFSET_ALERT_LIMIT - 1)}, "OK"),
        ({**base_status_result, "offset_value": -OFFSET_ALERT_LIMIT}, "OK"),
        ({**base_status_result, "scan_right": SCAN_LIMIT, "offset_value": 0.0}, "OK"),
        ({**base_status_result, "scan_left": SCAN_LIMIT, "offset_value": 0.0}, "OK"),
        ({**base_status_result, "scan_right": SCAN_LIMIT + 1, "offset_value": 0.0}, "Warning"),
        ({**base_status_result, "scan_left": SCAN_LIMIT + 1, "offset_value": 0.0}, "Warning"),
        ({**base_status_result, "offset_value": OFFSET_ALERT_LIMIT + 1}, "Error"),
        ({**base_status_result, "offset_value": -(OFFSET_ALERT_LIMIT + 1)}, "Error"),
        ({**base_status_result, "scan_right": -1.0, "offset_value": 0.0}, "OK"),
        ({**base_status_result, "scan_left": -1.0, "offset_value": 0.0}, "OK"),
    ]
    passed_status_threshold = all(
        _result_status(result, total_results=3) == expected
        for result, expected in status_threshold_tests
    )
    exempt_last_single = _result_status(
        {"scan_right": 1000.0, "scan_left": 1000.0, "offset_value": OFFSET_ALERT_LIMIT + 800, "index": 2, "assigned": [4]},
        total_results=3,
    ) == "OK"
    exempt_not_last = _result_status(
        {"scan_right": 1000.0, "scan_left": 1000.0, "offset_value": OFFSET_ALERT_LIMIT + 800, "index": 1, "assigned": [3]},
        total_results=3,
    ) == "Error"
    last_multi_lane_should_error = _result_status(
        {"scan_right": 1000.0, "scan_left": 1000.0, "offset_value": OFFSET_ALERT_LIMIT + 800, "index": 2, "assigned": [3, 4]},
        total_results=3,
    ) == "Error"
    note_tests.append(("Offset exceeding ±1500 triggers Error", passed_status_threshold))
    note_tests.append((
        "Last single-lane Lidar offset does not trigger Error",
        exempt_last_single and exempt_not_last and last_multi_lane_should_error,
    ))

finally:
    os.unlink(tmp2_path)

# ─── Step 4: Output complete verification report ─────────────────────────────

print_section("Step 4: Complete Verification Report")

all_tests = []

# Calculation tests
for label, passed, actual, expected in calc_tests:
    all_tests.append((label, passed, f"actual={actual}", f"expected={expected}"))

# Save tests
for label, passed in save_tests:
    all_tests.append((label, passed, "", ""))

# note + load-modify tests
for label, passed in note_tests:
    all_tests.append((label, passed, "", ""))

print()
col_w = 46
print(f"  ┌─{'─'*col_w}─┬──────────┬──────────────────────────────────────┐")
print(f"  │ {'Test Item':<{col_w}} │ Result   │ Description                          │")
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
print(f"  Total: {total}  ✅ PASS: {pass_count}  ❌ FAIL: {fail_count}")

if fail_count == 0:
    print()
    print("  🎉 All tests passed! Calculation logic and storage functions are working correctly.")
else:
    print()
    print("  ⚠️  Some tests failed. Please check the FAIL items above.")

print()
