#!/usr/bin/env python3
"""
簡易 Web UI：Lidar 有效區計算

執行:
  python examples/web_ui.py
"""

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs
import json

from verify_lidar_calculation import (
    SCAN_LIMIT,
    WIDTH_CONSISTENCY_WARNING_THRESHOLD,
    calculate_lane_coordinates,
    calculate_lidar_results,
    load_records,
    save_result,
)

MAX_BODY_SIZE = 16 * 1024

_FORM_JS = """
(function () {
  var S = FORM_INIT;
  var laneWidths = S.laneWidths.slice();
  var lidarCenters = S.lidarCenters.slice();
  var lidarLanesA = S.lidarLanesA.slice();
  var lidarLanesB = S.lidarLanesB.slice();
  var backupLidarCenters = S.backupLidarCenters.slice();
  var backupLidarLanesA = S.backupLidarLanesA.slice();
  var backupLidarLanesB = S.backupLidarLanesB.slice();
  var primaryLastOuter = S.primaryLastOuter || '';
  var backupLastOuter = S.backupLastOuter || '';
  var hasBackup = !!S.hasBackup;

  function getLaneCount() {
    return parseInt(document.getElementById('lane-count').value, 10);
  }
  function getLidarCount() {
    return parseInt(document.getElementById('lidar-count').value, 10);
  }
  function getHasBackup() {
    return !!document.getElementById('has-backup').checked;
  }
  function getPrimaryCount() {
    var total = getLidarCount();
    return getHasBackup() ? Math.floor(total / 2) : total;
  }

  function saveState() {
    var n = getLaneCount();
    var m = getPrimaryCount();
    hasBackup = getHasBackup();
    for (var i = 0; i < n; i++) {
      var el = document.getElementById('lane_width_' + i);
      if (el) laneWidths[i] = el.value;
    }
    for (var j = 0; j < m; j++) {
      var pea = document.getElementById('primary_lidar_lane_' + j + '_a');
      var peb = document.getElementById('primary_lidar_lane_' + j + '_b');
      var pec = document.getElementById('primary_lidar_center_' + j);
      if (pea) lidarLanesA[j] = parseInt(pea.value, 10);
      if (peb) lidarLanesB[j] = parseInt(peb.value, 10);
      if (pec) lidarCenters[j] = pec.value;

      var bea = document.getElementById('backup_lidar_lane_' + j + '_a');
      var beb = document.getElementById('backup_lidar_lane_' + j + '_b');
      var bec = document.getElementById('backup_lidar_center_' + j);
      if (bea) backupLidarLanesA[j] = parseInt(bea.value, 10);
      if (beb) backupLidarLanesB[j] = parseInt(beb.value, 10);
      if (bec) backupLidarCenters[j] = bec.value;
    }
    var plo = document.getElementById('primary_last_lidar_outer_dist');
    var blo = document.getElementById('backup_last_lidar_outer_dist');
    if (plo) primaryLastOuter = plo.value;
    if (blo) backupLastOuter = blo.value;
  }

  function laneOpts(n, sel) {
    var html = '';
    for (var i = 0; i < n; i++) {
      html += '<option value="' + i + '"' + (sel === i ? ' selected' : '') + '>Lane' + i + '</option>';
    }
    return html;
  }

  function laneOptsNone(n, sel) {
    var html = '<option value="-1"' + (sel === -1 ? ' selected' : '') + '>（無）</option>';
    for (var i = 0; i < n; i++) {
      html += '<option value="' + i + '"' + (sel === i ? ' selected' : '') + '>Lane' + i + '</option>';
    }
    return html;
  }

  function renderLaneWidths() {
    var n = getLaneCount();
    var html = '';
    for (var i = 0; i < n; i++) {
      var val = laneWidths[i] !== undefined ? laneWidths[i] : '';
      html += '<div class="lw-item">'
        + '<span class="lw-label">Lane' + i + '</span>'
        + '<input id="lane_width_' + i + '" name="lane_width_' + i
        + '" type="number" min="1" step="1" placeholder="mm" value="' + val + '" />'
        + '</div>';
    }
    document.getElementById('lane-widths-section').innerHTML = html;
  }

  function renderOneLidarGroup(prefix, title, laneCount, lidarCount, centers, lanesA, lanesB, lastOuterValue) {
    var html = '<div class="lidar-block">';
    html += '<div class="lidar-block-title">' + title + '</div>';
    for (var j = 0; j < lidarCount; j++) {
      var selA = lanesA[j] !== undefined ? lanesA[j] : 0;
      var selB = lanesB[j] !== undefined ? lanesB[j] : -1;
      var ctr = centers[j] !== undefined ? centers[j] : '';
      html += '<div class="lidar-group">'
        + '<div class="lidar-group-title">' + title + ' — LIDAR_' + j + '</div>'
        + '<div class="lane-selects">'
        + '<div><label>第一車道</label>'
        + '<select id="' + prefix + '_lidar_lane_' + j + '_a" name="' + prefix + '_lidar_lane_' + j + '_a">'
        + laneOpts(laneCount, selA) + '</select></div>'
        + '<div><label>第二車道</label>'
        + '<select id="' + prefix + '_lidar_lane_' + j + '_b" name="' + prefix + '_lidar_lane_' + j + '_b">'
        + laneOptsNone(laneCount, selB) + '</select></div>'
        + '</div>'
        + '<label>中心距離 (mm)</label>'
        + '<input id="' + prefix + '_lidar_center_' + j + '" name="' + prefix + '_lidar_center_' + j
        + '" type="number" min="0" step="1" placeholder="mm" value="' + ctr + '" />'
        + '</div>';
    }
    html += '<label>' + title + '最後一顆 Lidar 到外側護欄距離 (mm，可留空)</label>'
      + '<input id="' + prefix + '_last_lidar_outer_dist" name="' + prefix + '_last_lidar_outer_dist"'
      + ' type="number" min="0" step="1" placeholder="mm" value="' + lastOuterValue + '" />';
    html += '</div>';
    return html;
  }

  function syncLidarCountForBackup() {
    var select = document.getElementById('lidar-count');
    if (!getHasBackup()) return;
    var total = parseInt(select.value, 10);
    if (total % 2 === 1) {
      select.value = String(Math.min(8, total + 1));
    }
  }

  function renderLidarSection() {
    var n = getLaneCount();
    var total = getLidarCount();
    var backupEnabled = getHasBackup();
    var primaryCount = getPrimaryCount();
    var html = '';
    html += renderOneLidarGroup(
      'primary', '主要 Lidar', n, primaryCount, lidarCenters, lidarLanesA, lidarLanesB, primaryLastOuter
    );
    if (backupEnabled) {
      html += renderOneLidarGroup(
        'backup', '備援 Lidar', n, primaryCount, backupLidarCenters, backupLidarLanesA, backupLidarLanesB, backupLastOuter
      );
    }
    document.getElementById('lidar-mode-note').textContent = backupEnabled
      ? '已啟用備援：總數量 ' + total + ' 顆，主要 ' + primaryCount + ' 顆，備援 ' + primaryCount + ' 顆。'
      : '未啟用備援：目前共 ' + total + ' 顆主要 Lidar。';
    document.getElementById('lidar-section').innerHTML = html;
  }

  document.getElementById('lane-count').addEventListener('change', function () {
    saveState();
    renderLaneWidths();
    renderLidarSection();
  });

  document.getElementById('lidar-count').addEventListener('change', function () {
    saveState();
    syncLidarCountForBackup();
    renderLidarSection();
  });

  document.getElementById('has-backup').addEventListener('change', function () {
    saveState();
    syncLidarCountForBackup();
    renderLidarSection();
  });

  syncLidarCountForBackup();
  renderLaneWidths();
  renderLidarSection();
}());
"""


def _parse_float_list(raw: str, field_name: str):
    vals = [x.strip() for x in raw.split(",") if x.strip()]
    if not vals:
        raise ValueError(f"{field_name} 不能為空")
    out = []
    for v in vals:
        try:
            out.append(float(v))
        except ValueError as exc:
            raise ValueError(f"{field_name} 需為數字，收到: {v}") from exc
    return out


def _parse_assignments(raw: str):
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("Lidar 負責車道不能為空")
    assignments = []
    for i, line in enumerate(lines):
        try:
            assigned = [int(x.strip()) for x in line.split(",") if x.strip()]
        except ValueError as exc:
            raise ValueError(f"LIDAR_{i} 負責車道需為整數") from exc
        if not assigned:
            raise ValueError(f"LIDAR_{i} 至少需指定 1 個車道")
        if len(assigned) > 2:
            raise ValueError(f"LIDAR_{i} 最多指定 2 個車道")
        assignments.append(sorted(assigned))
    return assignments


def _build_warnings(results, all_lanes, lidar_centers, last_lidar_outer_dist, group_label=None):
    warnings = []
    prefix = f"{group_label}：" if group_label else ""
    for r in results:
        if r["scan_right"] > SCAN_LIMIT:
            warnings.append(
                f"{prefix}LIDAR_{r['index']} scan_right={r['scan_right']:.0f}mm 超過 {SCAN_LIMIT:.0f}mm"
            )
        if r["scan_left"] > SCAN_LIMIT:
            warnings.append(
                f"{prefix}LIDAR_{r['index']} scan_left={r['scan_left']:.0f}mm 超過 {SCAN_LIMIT:.0f}mm"
            )
        if r["scan_right"] < 0 or r["scan_left"] < 0:
            warnings.append(f"{prefix}LIDAR_{r['index']} 出現負值，請確認輸入資料")

    if last_lidar_outer_dist is not None:
        total_lanes = sum(w for _, w in all_lanes)
        measured = lidar_centers[-1] + last_lidar_outer_dist
        diff = abs(measured - total_lanes)
        if diff >= WIDTH_CONSISTENCY_WARNING_THRESHOLD:
            warnings.append(
                f"{prefix}路寬一致性警告: 實測合計={measured:.0f}mm、車道總寬={total_lanes:.0f}mm、差距={diff:.0f}mm"
            )
    return warnings


def _render_table(headers, rows):
    head_html = "".join(f"<th>{escape(h)}</th>" for h in headers)
    row_html = []
    for row in rows:
        row_html.append(
            "<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>"
        )
    return (
        "<div class='table-scroll'>"
        "<table class='report-table'>"
        f"<thead><tr>{head_html}</tr></thead>"
        f"<tbody>{''.join(row_html)}</tbody>"
        "</table>"
        "</div>"
    )


def _status_to_class(status: str):
    return {
        "正常": "status-ok",
        "警告": "status-warn",
        "錯誤": "status-error",
    }.get(status, "status-neutral")


def _render_summary_cards(items):
    cards = []
    for label, value, tone in items:
        cards.append(
            "<div class='summary-card'>"
            f"<div class='summary-label'>{escape(label)}</div>"
            f"<div class='summary-value {escape(tone)}'>{escape(value)}</div>"
            "</div>"
        )
    return "<div class='summary-grid'>" + "".join(cards) + "</div>"


def _render_result_table(results):
    row_html = []
    for r in results:
        status = "正常"
        if r["scan_right"] > SCAN_LIMIT or r["scan_left"] > SCAN_LIMIT:
            status = "警告"
        if r["scan_right"] < 0 or r["scan_left"] < 0:
            status = "錯誤"
        row_html.append(
            "<tr>"
            f"<td>LIDAR_{r['index']}</td>"
            f"<td>{escape('+'.join(f'Lane{n}' for n in r['assigned']))}</td>"
            f"<td>{r['scan_right']:.0f}</td>"
            f"<td>{r['scan_left']:.0f}</td>"
            f"<td>{r['offset_value']:.0f}</td>"
            f"<td><span class='status-pill {_status_to_class(status)}'>{escape(status)}</span></td>"
            "</tr>"
        )
    return (
        "<div class='table-scroll'>"
        "<table class='report-table result-table'>"
        "<thead><tr>"
        "<th>Lidar</th><th>負責車道</th><th>scan_right(mm)</th>"
        "<th>scan_left(mm)</th><th>偏差值(mm)</th><th>狀態</th>"
        "</tr></thead>"
        f"<tbody>{''.join(row_html)}</tbody>"
        "</table>"
        "</div>"
    )


def _result_status(result):
    status = "正常"
    if result["scan_right"] > SCAN_LIMIT or result["scan_left"] > SCAN_LIMIT:
        status = "警告"
    if result["scan_right"] < 0 or result["scan_left"] < 0:
        status = "錯誤"
    return status


def _collect_status_counts(results):
    counts = {"正常": 0, "警告": 0, "錯誤": 0}
    for result in results:
        counts[_result_status(result)] += 1
    return counts


def _render_group_report_sections(
    group_label, all_lanes, lidar_assignments, lidar_centers, results, last_lidar_outer_dist
):
    lidar_rows = []
    for i, (assigned, center) in enumerate(zip(lidar_assignments, lidar_centers)):
        lidar_rows.append([f"LIDAR_{i}", "+".join(f"Lane{n}" for n in assigned), f"{center:.0f}"])

    detail_cards = []
    for r in results:
        lanes_str = "+".join(f"Lane{n}" for n in r["assigned"])
        detail_cards.append(
            "<div class='detail-card'>"
            "<div class='detail-card-header'>"
            f"<h3>{escape(group_label)} — LIDAR_{r['index']} ({escape(lanes_str)})</h3>"
            f"<span class='detail-center'>CENTER {r['center']:.0f} mm</span>"
            "</div>"
            "<div class='detail-lines'>"
            f"<p><span>負責車道邊界</span><strong>{r['inner_boundary']:.0f} mm ~ {r['outer_boundary']:.0f} mm</strong></p>"
            f"<p><span>補償值</span><strong>右 +{r['right_compensation']:.0f} mm / 左 +{r['left_compensation']:.0f} mm</strong></p>"
            f"<p><span>scan_right</span><code>{r['center']:.0f} - {r['inner_boundary']:.0f} + {r['right_compensation']:.0f} = {r['scan_right']:.0f} mm</code></p>"
            f"<p><span>scan_left</span><code>{r['outer_boundary']:.0f} - {r['center']:.0f} + {r['left_compensation']:.0f} = {r['scan_left']:.0f} mm</code></p>"
            f"<p><span>偏差值</span><code>{escape(r['offset_formula'])} = {r['offset_value']:.0f} mm</code></p>"
            "</div>"
            "</div>"
        )

    width_check_html = ""
    if last_lidar_outer_dist is not None:
        total_measured = lidar_centers[-1] + last_lidar_outer_dist
        total_lanes = sum(w for _, w in all_lanes)
        diff = abs(total_measured - total_lanes)
        status = "正常" if diff < WIDTH_CONSISTENCY_WARNING_THRESHOLD else "警告"
        width_rows = [
            [f"最後一顆{group_label}中心距離", f"{lidar_centers[-1]:.0f} mm"],
            [f"最後一顆{group_label}到外側護欄距離", f"{last_lidar_outer_dist:.0f} mm"],
            ["實測合計", f"{total_measured:.0f} mm"],
            ["所有車道寬度加總", f"{total_lanes:.0f} mm"],
            ["差距", f"{diff:.0f} mm"],
            ["狀態", status],
        ]
        width_check_html = (
            "<section class='report-section'>"
            f"<div class='section-heading'><span class='section-tag'>CHECK</span><h2>路寬一致性檢核 — {escape(group_label)}</h2></div>"
            + _render_table(["項目", "數值"], width_rows)
            + "</section>"
        )

    return (
        "<section class='report-section'>"
        + f"<div class='section-heading'><span class='section-tag'>INPUT</span><h2>輸入資訊 — {escape(group_label)}</h2></div>"
        + _render_table(["Lidar", "負責車道", "中心距離(mm)"], lidar_rows)
        + "</section>"
        + "<section class='report-section'>"
        + f"<div class='section-heading'><span class='section-tag'>RESULT</span><h2>計算結果 — {escape(group_label)}</h2></div>"
        + _render_result_table(results)
        + "</section>"
        + "<section class='report-section'>"
        + f"<div class='section-heading'><span class='section-tag'>DETAIL</span><h2>詳細計算過程 — {escape(group_label)}</h2></div>"
        + "<div class='detail-grid'>"
        + "".join(detail_cards)
        + "</div>"
        + "</section>"
        + width_check_html
    )


def _render_results_sections(site_name, all_lanes, lidar_groups, total_lidar_count, has_backup):
    lane_coords = calculate_lane_coordinates(all_lanes)
    lane_coords_map = {num: (start, end) for num, start, end in lane_coords}
    lane_rows = [
        [f"Lane{num}", f"{width:.0f}", f"{lane_coords_map[num][0]:.0f} ~ {lane_coords_map[num][1]:.0f}"]
        for num, width in all_lanes
    ]
    lane_rows.append(["合計", f"{sum(w for _, w in all_lanes):.0f}", ""])

    overall_counts = {"正常": 0, "警告": 0, "錯誤": 0}
    for group in lidar_groups:
        counts = _collect_status_counts(group["results"])
        for key in overall_counts:
            overall_counts[key] += counts[key]

    summary_items = [
        ("點位", site_name, "tone-neutral"),
        ("車道數", str(len(all_lanes)), "tone-neutral"),
        ("總 Lidar 數", str(total_lidar_count), "tone-neutral"),
        ("備援模式", "有" if has_backup else "無", "tone-neutral"),
        ("主要數量", str(len(lidar_groups[0]["results"])), "tone-neutral"),
    ]
    if has_backup and len(lidar_groups) > 1:
        summary_items.append(("備援數量", str(len(lidar_groups[1]["results"])), "tone-neutral"))
    summary_items.extend([
        ("正常", str(overall_counts["正常"]), "tone-ok"),
        ("警告", str(overall_counts["警告"]), "tone-warn"),
        ("錯誤", str(overall_counts["錯誤"]), "tone-error"),
    ])

    sections = [
        "<section class='report-section hero-section'>"
        "<div class='report-banner'>"
        "<div>"
        "<div class='report-kicker'>LIDAR TEST REPORT</div>"
        f"<h2>計算結果 — {escape(site_name)}</h2>"
        + ("<p>已啟用備援模式，以下分別列出主要與備援 Lidar 的輸入與計算結果。</p>" if has_backup
           else "<p>以下內容以測試報表版型整理輸入資料、驗證結果與計算明細。</p>")
        + "</div>"
        "<div class='report-stamp'>VERIFIED</div>"
        "</div>"
        + _render_summary_cards(summary_items)
        + "</section>",
        "<section class='report-section'>"
        "<div class='section-heading'><span class='section-tag'>INPUT</span><h2>輸入資訊 — 車道</h2></div>"
        + _render_table(["車道", "寬度(mm)", "座標範圍(mm)"], lane_rows)
        + "</section>",
    ]

    for group in lidar_groups:
        sections.append(
            _render_group_report_sections(
                group["label"],
                all_lanes,
                group["lidar_assignments"],
                group["lidar_centers"],
                group["results"],
                group["last_lidar_outer_dist"],
            )
        )
    return "".join(sections)


def _render_notice_block(title, items, tone):
    if not items:
        return ""
    return (
        f"<section class='notice-block {escape(tone)}'>"
        f"<h3>{escape(title)}</h3>"
        "<ul>"
        + "".join(f"<li>{escape(item)}</li>" for item in items)
        + "</ul>"
        + "</section>"
    )


def _render_error_block(message):
    if not message:
        return ""
    return (
        "<section class='notice-block error'>"
        "<h3>輸入錯誤</h3>"
        f"<p>{escape(message)}</p>"
        "</section>"
    )


def _default_form():
    return {
        "site_name": "03F-040.7N",
        "lane_count": 5,
        "lidar_count": 3,
        "has_backup": False,
        "lane_widths": ["3800", "3750", "3800", "3650", "3400"],
        "lidar_centers": ["5000", "11300", "16700"],
        "lidar_lanes_a": [0, 2, 4],
        "lidar_lanes_b": [1, 3, -1],
        "last_lidar_outer_dist": "1700",
        "backup_lidar_centers": [],
        "backup_lidar_lanes_a": [],
        "backup_lidar_lanes_b": [],
        "backup_last_lidar_outer_dist": "",
    }


def _render_history_table(site_name, records):
    rows = []
    for idx, rec in reversed(list(enumerate(records))):
        ts = rec.get("timestamp", "")
        note = rec.get("note", "")
        all_lanes = rec.get("all_lanes", [])
        centers = rec.get("lidar_centers", [])
        lane_count = len(all_lanes)
        lidar_count = len(centers)
        total_width = sum(float(lane[1]) for lane in all_lanes) if all_lanes else 0.0
        rows.append(
            "<tr>"
            f"<td>{idx + 1}</td>"
            f"<td>{escape(str(ts))}</td>"
            f"<td>{escape(str(note))}</td>"
            f"<td>{lane_count}</td>"
            f"<td>{lidar_count}</td>"
            f"<td>{total_width:.0f}</td>"
            "<td>"
            "<form method='post' action='/load-site-record'>"
            f"<input type='hidden' name='site_name' value='{escape(site_name)}' />"
            f"<input type='hidden' name='record_index' value='{idx}' />"
            "<button class='mini-btn' type='submit'>載入這筆設定</button>"
            "</form>"
            "</td>"
            "</tr>"
        )
    return (
        "<section class='report-section'>"
        "<div class='section-heading'><span class='section-tag'>HISTORY</span><h2>歷史點位設定</h2></div>"
        f"<p>點位：{escape(site_name)}（共 {len(records)} 筆）</p>"
        "<table class='report-table'>"
        "<thead><tr><th>編號</th><th>時間戳記</th><th>備註</th><th>車道數</th><th>Lidar 數</th><th>車道總寬(mm)</th><th>操作</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</section>"
    )


def _compute_results_from_record(record):
    """從歷史記錄計算 lidar_groups 與 all_lanes，供載入時直接輸出結果。"""
    raw_lanes = record.get("all_lanes", [])
    lidar_assignments = [list(a) for a in record.get("lidar_assignments", [])]
    lidar_centers = [float(c) for c in record.get("lidar_centers", [])]
    if not raw_lanes or not lidar_assignments or not lidar_centers:
        return None, None, []
    all_lanes = [(int(lane[0]), float(lane[1])) for lane in raw_lanes]
    last_outer_raw = record.get("last_lidar_outer_dist")
    last_lidar_outer_dist = float(last_outer_raw) if last_outer_raw is not None else None
    results = calculate_lidar_results(all_lanes, lidar_assignments, lidar_centers)
    warnings = _build_warnings(results, all_lanes, lidar_centers, last_lidar_outer_dist)
    lidar_groups = [{
        "label": "主要 Lidar",
        "lidar_assignments": lidar_assignments,
        "lidar_centers": lidar_centers,
        "results": results,
        "last_lidar_outer_dist": last_lidar_outer_dist,
    }]
    return lidar_groups, all_lanes, warnings


def _form_from_record(site_name, record):
    def _format_number_for_input(value):
        num = float(value)
        if num.is_integer():
            return str(int(num))
        return format(num, ".15g")

    all_lanes = record.get("all_lanes", [])
    lidar_centers = record.get("lidar_centers", [])
    lidar_assignments = record.get("lidar_assignments", [])
    lane_widths = [_format_number_for_input(lane[1]) for lane in all_lanes]
    centers = [_format_number_for_input(c) for c in lidar_centers]
    lanes_a = [int(assigned[0]) if assigned else 0 for assigned in lidar_assignments]
    lanes_b = [int(assigned[1]) if len(assigned) > 1 else -1 for assigned in lidar_assignments]
    last_outer = record.get("last_lidar_outer_dist")
    return {
        "site_name": site_name,
        "lane_count": max(1, min(8, len(lane_widths))) if lane_widths else 1,
        "lidar_count": max(1, min(8, len(centers))) if centers else 1,
        "has_backup": False,
        "lane_widths": lane_widths or [""],
        "lidar_centers": centers or [""],
        "lidar_lanes_a": lanes_a or [0],
        "lidar_lanes_b": lanes_b or [-1],
        "last_lidar_outer_dist": "" if last_outer is None else _format_number_for_input(last_outer),
        "backup_lidar_centers": [],
        "backup_lidar_lanes_a": [],
        "backup_lidar_lanes_b": [],
        "backup_last_lidar_outer_dist": "",
    }


def _render_page(
    form=None,
    lidar_groups=None,
    warnings=None,
    info=None,
    error=None,
    history_table=None,
    all_lanes=None,
):
    form = form or _default_form()
    results_html = ""
    if lidar_groups and all_lanes:
        results_html = _render_results_sections(
            form["site_name"],
            all_lanes,
            lidar_groups,
            int(form["lidar_count"]),
            bool(form.get("has_backup")),
        )

    warnings_html = _render_notice_block("警告", warnings or [], "warning")
    info_html = _render_notice_block("訊息", info or [], "info")
    error_html = _render_error_block(error)

    lane_count_opts = "".join(
        f'<option value="{i}"{" selected" if i == form["lane_count"] else ""}>{i}</option>'
        for i in range(1, 9)
    )
    lidar_count_opts = "".join(
        f'<option value="{i}"{" selected" if i == form["lidar_count"] else ""}>{i}</option>'
        for i in range(1, 9)
    )
    form_init_json = json.dumps({
        "laneCount": int(form["lane_count"]),
        "lidarCount": int(form["lidar_count"]),
        "hasBackup": bool(form.get("has_backup")),
        "laneWidths": [str(w) for w in form["lane_widths"]],
        "lidarCenters": [str(c) for c in form["lidar_centers"]],
        "lidarLanesA": [int(a) for a in form["lidar_lanes_a"]],
        "lidarLanesB": [int(b) for b in form["lidar_lanes_b"]],
        "backupLidarCenters": [str(c) for c in form.get("backup_lidar_centers", [])],
        "backupLidarLanesA": [int(a) for a in form.get("backup_lidar_lanes_a", [])],
        "backupLidarLanesB": [int(b) for b in form.get("backup_lidar_lanes_b", [])],
        "primaryLastOuter": str(form["last_lidar_outer_dist"]),
        "backupLastOuter": str(form.get("backup_last_lidar_outer_dist", "")),
    })

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <title>Lidar 計算 Web UI</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #eef3f8;
      --panel: #ffffff;
      --panel-alt: #f7f9fc;
      --ink: #122033;
      --muted: #5b6b82;
      --line: #c8d3e1;
      --line-strong: #93a6bf;
      --accent: #173b67;
      --accent-soft: #dfe9f7;
      --ok: #18794e;
      --ok-soft: #dff5e8;
      --warn: #a86500;
      --warn-soft: #fff0d6;
      --error: #b42318;
      --error-soft: #fde8e7;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      color: var(--ink);
      background:
        linear-gradient(180deg, #d8e3f1 0, #d8e3f1 220px, var(--bg) 220px, var(--bg) 100%);
    }}
    .page {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 24px 48px;
    }}
    .app-header {{
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 24px;
      color: #fff;
      margin-bottom: 24px;
    }}
    .app-header h1 {{ margin: 6px 0 8px; font-size: 2rem; }}
    .eyebrow {{
      font-size: 0.82rem;
      letter-spacing: 0.18em;
      font-weight: 700;
      opacity: 0.9;
    }}
    .header-note {{
      margin: 0;
      color: rgba(255, 255, 255, 0.86);
    }}
    .header-badge {{
      padding: 10px 14px;
      border: 1px solid rgba(255, 255, 255, 0.35);
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.12em;
      white-space: nowrap;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(360px, 460px) minmax(0, 1fr);
      gap: 24px;
      align-items: start;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: 0 14px 32px rgba(16, 38, 66, 0.08);
      overflow: hidden;
    }}
    .panel-body {{ padding: 22px; }}
    .form-panel {{
      position: sticky;
      top: 24px;
      max-height: calc(100vh - 48px);
      overflow-y: auto;
    }}
    .panel-title {{
      margin: 0 0 4px;
      font-size: 1.2rem;
    }}
    .panel-subtitle {{
      margin: 0 0 18px;
      color: var(--muted);
      font-size: 0.95rem;
      line-height: 1.5;
    }}
    label {{
      display: block;
      margin-top: 14px;
      margin-bottom: 6px;
      font-weight: 700;
      color: var(--accent);
    }}
    input, textarea, select {{
      width: 100%;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--panel-alt);
      color: var(--ink);
      font: inherit;
    }}
    textarea {{ resize: vertical; min-height: 120px; }}
    select {{ cursor: pointer; }}
    button {{
      width: 100%;
      margin-top: 18px;
      padding: 12px 16px;
      border: 0;
      border-radius: 12px;
      background: var(--accent);
      color: #fff;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    .results-stack {{
      display: flex;
      flex-direction: column;
      gap: 18px;
    }}
    .notice-block {{
      border-radius: 18px;
      border: 1px solid var(--line);
      padding: 18px 20px;
      background: var(--panel);
      box-shadow: 0 10px 24px rgba(16, 38, 66, 0.06);
    }}
    .notice-block h3 {{
      margin: 0 0 10px;
      font-size: 1.05rem;
    }}
    .notice-block ul, .notice-block p {{
      margin: 0;
      padding-left: 18px;
      line-height: 1.6;
    }}
    .notice-block p {{ padding-left: 0; }}
    .notice-block.warning {{
      border-color: #f2c66d;
      background: var(--warn-soft);
    }}
    .notice-block.error {{
      border-color: #f1a3a0;
      background: var(--error-soft);
    }}
    .notice-block.info {{
      border-color: #b9d5f6;
      background: #edf5ff;
    }}
    .empty-state {{
      padding: 36px 28px;
      text-align: center;
      color: var(--muted);
    }}
    .empty-state strong {{
      display: block;
      margin-bottom: 8px;
      color: var(--accent);
      font-size: 1.05rem;
    }}
    .report-section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 22px;
      box-shadow: 0 10px 24px rgba(16, 38, 66, 0.06);
    }}
    .hero-section {{
      background: linear-gradient(135deg, #132f53, #1f4d82 72%, #3568a0);
      color: #fff;
      border-color: transparent;
    }}
    .report-banner {{
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: start;
    }}
    .report-kicker {{
      font-size: 0.8rem;
      font-weight: 700;
      letter-spacing: 0.16em;
      opacity: 0.82;
    }}
    .report-banner h2 {{
      margin: 8px 0 8px;
      font-size: 1.8rem;
    }}
    .report-banner p {{
      margin: 0;
      max-width: 560px;
      color: rgba(255, 255, 255, 0.82);
      line-height: 1.6;
    }}
    .report-stamp {{
      border: 2px solid rgba(255, 255, 255, 0.55);
      border-radius: 999px;
      padding: 12px 18px;
      font-weight: 800;
      letter-spacing: 0.18em;
      align-self: center;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: 12px;
      margin-top: 22px;
    }}
    .summary-card {{
      padding: 14px 16px;
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.12);
      border: 1px solid rgba(255, 255, 255, 0.14);
    }}
    .summary-label {{
      font-size: 0.78rem;
      letter-spacing: 0.06em;
      opacity: 0.8;
    }}
    .summary-value {{
      margin-top: 8px;
      font-size: 1.35rem;
      font-weight: 800;
    }}
    .tone-ok {{ color: #bdf7d0; }}
    .tone-warn {{ color: #ffe4a8; }}
    .tone-error {{ color: #ffd0cc; }}
    .tone-neutral {{ color: #fff; }}
    .section-heading {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 14px;
    }}
    .section-tag {{
      padding: 4px 8px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 0.75rem;
      font-weight: 800;
      letter-spacing: 0.08em;
    }}
    .section-heading h2 {{
      margin: 0;
      font-size: 1.1rem;
    }}
    .report-table {{
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border-radius: 14px;
      margin-top: 12px;
      font-size: 0.96rem;
    }}
    .table-scroll {{
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
    }}
    .btn-secondary {{
      background: #4d5f78;
      margin-top: 10px;
    }}
    .mini-btn {{
      width: auto;
      margin-top: 0;
      padding: 8px 12px;
      border-radius: 8px;
      background: var(--accent);
      font-size: 0.84rem;
    }}
    .report-table th,
    .report-table td {{
      padding: 12px 14px;
      border: 1px solid var(--line);
      text-align: left;
    }}
    .report-table th {{
      background: #ecf2f9;
      color: var(--accent);
      font-weight: 800;
    }}
    .report-table tbody tr:nth-child(even) td {{
      background: #fbfcfe;
    }}
    .result-table td:nth-child(3),
    .result-table td:nth-child(4),
    .result-table td:nth-child(5) {{
      font-family: "Consolas", "Courier New", monospace;
      font-weight: 700;
    }}
    .status-pill {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 64px;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 0.84rem;
      font-weight: 800;
    }}
    .status-ok {{
      background: var(--ok-soft);
      color: var(--ok);
    }}
    .status-warn {{
      background: var(--warn-soft);
      color: var(--warn);
    }}
    .status-error {{
      background: var(--error-soft);
      color: var(--error);
    }}
    .status-neutral {{
      background: #e9eef5;
      color: var(--muted);
    }}
    .detail-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
    }}
    .detail-card {{
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px;
      background: var(--panel-alt);
    }}
    .detail-card-header {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      margin-bottom: 12px;
    }}
    .detail-card-header h3 {{
      margin: 0;
      font-size: 1rem;
    }}
    .detail-center {{
      padding: 4px 8px;
      border-radius: 999px;
      background: #e3ebf8;
      color: var(--accent);
      font-size: 0.75rem;
      font-weight: 800;
      white-space: nowrap;
    }}
    .detail-lines {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .detail-lines p {{
      margin: 0;
      display: flex;
      flex-direction: column;
      gap: 4px;
      line-height: 1.5;
    }}
    .detail-lines span {{
      color: var(--muted);
      font-size: 0.88rem;
      font-weight: 700;
    }}
    .detail-lines code {{
      display: block;
      padding: 10px 12px;
      border-radius: 10px;
      background: #0f2239;
      color: #edf4ff;
      font-family: "Consolas", "Courier New", monospace;
      font-size: 0.88rem;
      white-space: normal;
      word-break: break-word;
    }}
    @media (max-width: 980px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .form-panel {{ position: static; max-height: none; }}
    }}
    @media (max-width: 700px) {{
      .page {{ padding: 24px 16px 36px; }}
      .app-header,
      .report-banner,
      .detail-card-header {{
        flex-direction: column;
        align-items: start;
      }}
      .lane-selects {{ grid-template-columns: 1fr; }}
    }}
    .lw-item {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 10px;
    }}
    .lw-label {{
      width: 56px;
      flex-shrink: 0;
      font-weight: 700;
      font-size: 0.88rem;
      color: var(--accent);
    }}
    .lw-item input {{
      margin-top: 0;
    }}
    .lidar-group {{
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px 14px;
      margin-top: 14px;
    }}
    .lidar-group-title {{
      font-weight: 800;
      color: var(--accent);
      font-size: 0.9rem;
      margin-bottom: 4px;
    }}
    .lane-selects {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }}
    .lidar-group label {{
      margin-top: 10px;
      font-size: 0.88rem;
    }}
    .lidar-block {{
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      margin-top: 14px;
      background: #fcfdff;
    }}
    .lidar-block-title {{
      font-weight: 800;
      color: var(--accent);
      margin-bottom: 4px;
    }}
    .config-note {{
      margin: 8px 0 0;
      color: var(--muted);
      line-height: 1.5;
    }}
    .checkbox-row {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 14px;
    }}
    .checkbox-row input {{
      width: auto;
      margin: 0;
    }}
    .checkbox-label {{
      margin: 0;
      font-weight: 700;
      color: var(--accent);
    }}
  </style>
</head>
<body>
  <div class="page">
    <header class="app-header">
      <div>
        <div class="eyebrow">DEVICE PARAMETER TOOL</div>
        <h1>Lidar 有效區計算 Web UI</h1>
        <p class="header-note">將輸入設定、結果摘要與計算明細整理成更接近測試報表的閱讀方式。</p>
      </div>
      <div class="header-badge">WEB TEST REPORT MODE</div>
    </header>
    <div class="layout">
      <aside class="panel form-panel">
        <div class="panel-body">
          <h2 class="panel-title">測試輸入設定</h2>
          <p class="panel-subtitle">輸入點位、車道與 Lidar 參數後，即可在右側產出報表式結果畫面。</p>
          <form method="post" action="/calculate">
            <label>點位名稱</label>
            <input name="site_name" value="{escape(form['site_name'])}" />
            <button type="submit" formaction="/query-site-history" class="btn-secondary">查詢點位歷史設定</button>
            <label>車道數</label>
            <select name="lane_count" id="lane-count">{lane_count_opts}</select>
            <div class="checkbox-row">
              <input id="has-backup" name="has_backup" type="checkbox" value="1" aria-label="啟用備援 Lidar" {"checked" if form.get("has_backup") else ""} />
              <label for="has-backup" class="checkbox-label">啟用備援 Lidar</label>
            </div>
            <label>Lidar 總數量</label>
            <select name="lidar_count" id="lidar-count">{lidar_count_opts}</select>
            <label>車道寬度 (mm)</label>
            <div id="lane-widths-section"></div>
            <label>Lidar 設定</label>
            <p class="config-note" id="lidar-mode-note"></p>
            <div id="lidar-section"></div>
            <button type="submit">產生測試報表</button>
          </form>
        </div>
      </aside>
      <main class="results-stack">
        {error_html}
        {info_html}
        {warnings_html}
        {history_table or ""}
        {results_html or "<section class='panel'><div class='empty-state'><strong>尚未產生報表</strong><span>請填寫左側測試參數並按下「產生測試報表」。</span></div></section>"}
      </main>
    </div>
  </div>
  <script>var FORM_INIT = {form_init_json};</script>
  <script>{_FORM_JS}</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send_html(self, content):
        data = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send_html(_render_page())

    def do_POST(self):
        if self.path not in ("/calculate", "/query-site-history", "/load-site-record"):
            self.send_error(404, "Not Found")
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_html(_render_page(error="請求格式錯誤：Content-Length 無效"))
            return
        if content_length < 0 or content_length > MAX_BODY_SIZE:
            self._send_html(_render_page(error=f"請求內容過大，限制 {MAX_BODY_SIZE} bytes"))
            return
        try:
            raw = self.rfile.read(content_length).decode("utf-8")
        except UnicodeDecodeError:
            self._send_html(_render_page(error="請求格式錯誤：內容需為 UTF-8 編碼"))
            return
        payload = parse_qs(raw)
        site_name = payload.get("site_name", [""])[0].strip()

        if self.path == "/query-site-history":
            form = _default_form()
            form["site_name"] = site_name
            if not site_name:
                self._send_html(_render_page(form=form, error="請先輸入點位名稱"))
                return
            records = load_records(site_name)
            if not records:
                self._send_html(_render_page(form=form, error=f"找不到點位「{site_name}」的歷史記錄"))
                return
            self._send_html(
                _render_page(
                    form=form,
                    history_table=_render_history_table(site_name, records),
                    info=[f"已查詢到點位「{site_name}」的歷史設定，可直接載入。"],
                )
            )
            return

        if self.path == "/load-site-record":
            if not site_name:
                self._send_html(_render_page(error="請先輸入點位名稱"))
                return
            records = load_records(site_name)
            if not records:
                self._send_html(_render_page(error=f"找不到點位「{site_name}」的歷史記錄"))
                return
            try:
                record_index = int(payload.get("record_index", ["-1"])[0])
            except ValueError:
                self._send_html(_render_page(error="記錄編號格式錯誤"))
                return
            if record_index < 0 or record_index >= len(records):
                self._send_html(_render_page(error="記錄編號超出範圍"))
                return
            form = _form_from_record(site_name, records[record_index])
            lidar_groups, all_lanes, calc_warnings = _compute_results_from_record(records[record_index])
            self._send_html(
                _render_page(
                    form=form,
                    lidar_groups=lidar_groups,
                    warnings=calc_warnings or [],
                    all_lanes=all_lanes,
                    history_table=_render_history_table(site_name, records),
                    info=[f"已載入第 {record_index + 1} 筆歷史設定，請確認後可直接產生報表。"],
                )
            )
            return

        has_backup = payload.get("has_backup", [""])[0] in ("1", "true", "on", "yes")
        try:
            lane_count = int(payload.get("lane_count", ["0"])[0])
            lidar_count = int(payload.get("lidar_count", ["0"])[0])
            if not (1 <= lane_count <= 8):
                raise ValueError("車道數需在 1~8 之間")
            if not (1 <= lidar_count <= 8):
                raise ValueError("Lidar 數量需在 1~8 之間")
            if has_backup and lidar_count % 2 != 0:
                raise ValueError("啟用備援時，Lidar 總數量需為偶數")
        except ValueError as e:
            self._send_html(_render_page(error=str(e)))
            return
        primary_count = lidar_count // 2 if has_backup else lidar_count
        lane_width_parts = [
            payload.get(f"lane_width_{i}", [""])[0].strip() for i in range(lane_count)
        ]
        lidar_center_parts = [
            payload.get(f"primary_lidar_center_{j}", [""])[0].strip() for j in range(primary_count)
        ]
        lidar_lanes_a = [
            int(payload.get(f"primary_lidar_lane_{j}_a", ["0"])[0]) for j in range(primary_count)
        ]
        lidar_lanes_b = [
            int(payload.get(f"primary_lidar_lane_{j}_b", ["-1"])[0]) for j in range(primary_count)
        ]
        lidar_assign_parts = [
            f"{lidar_lanes_a[j]},{lidar_lanes_b[j]}" if lidar_lanes_b[j] >= 0
            else str(lidar_lanes_a[j])
            for j in range(primary_count)
        ]
        last_outer = payload.get("primary_last_lidar_outer_dist", [""])[0].strip()
        backup_lidar_center_parts = [
            payload.get(f"backup_lidar_center_{j}", [""])[0].strip() for j in range(primary_count)
        ] if has_backup else []
        backup_lidar_lanes_a = [
            int(payload.get(f"backup_lidar_lane_{j}_a", ["0"])[0]) for j in range(primary_count)
        ] if has_backup else []
        backup_lidar_lanes_b = [
            int(payload.get(f"backup_lidar_lane_{j}_b", ["-1"])[0]) for j in range(primary_count)
        ] if has_backup else []
        backup_lidar_assign_parts = [
            f"{backup_lidar_lanes_a[j]},{backup_lidar_lanes_b[j]}" if backup_lidar_lanes_b[j] >= 0
            else str(backup_lidar_lanes_a[j])
            for j in range(primary_count)
        ] if has_backup else []
        backup_last_outer = payload.get("backup_last_lidar_outer_dist", [""])[0].strip() if has_backup else ""
        form = {
            "site_name": site_name,
            "lane_count": lane_count,
            "lidar_count": lidar_count,
            "has_backup": has_backup,
            "lane_widths": lane_width_parts,
            "lidar_centers": lidar_center_parts,
            "lidar_lanes_a": lidar_lanes_a,
            "lidar_lanes_b": lidar_lanes_b,
            "last_lidar_outer_dist": last_outer,
            "backup_lidar_centers": backup_lidar_center_parts,
            "backup_lidar_lanes_a": backup_lidar_lanes_a,
            "backup_lidar_lanes_b": backup_lidar_lanes_b,
            "backup_last_lidar_outer_dist": backup_last_outer,
        }
        lane_widths_str = ",".join(lane_width_parts)
        lidar_assignments_str = "\n".join(lidar_assign_parts)
        lidar_centers_str = ",".join(lidar_center_parts)
        backup_lidar_assignments_str = "\n".join(backup_lidar_assign_parts)
        backup_lidar_centers_str = ",".join(backup_lidar_center_parts)

        try:
            lane_widths = _parse_float_list(lane_widths_str, "車道寬度")
            all_lanes = [(i, w) for i, w in enumerate(lane_widths)]
            lidar_assignments = _parse_assignments(lidar_assignments_str)
            lidar_centers = _parse_float_list(lidar_centers_str, "Lidar 中心距離")

            if len(lidar_assignments) != len(lidar_centers):
                raise ValueError("Lidar 負責車道行數需與 Lidar 中心距離數量相同")

            lane_count = len(all_lanes)
            for i, assigned in enumerate(lidar_assignments):
                for lane_idx in assigned:
                    if lane_idx < 0 or lane_idx >= lane_count:
                        raise ValueError(
                            f"LIDAR_{i} 指定的 Lane{lane_idx} 超出範圍 (0~{lane_count - 1})"
                        )

            for c in lidar_centers:
                if c < 0:
                    raise ValueError("Lidar 中心距離不可為負數")

            last_lidar_outer_dist = None
            if form["last_lidar_outer_dist"]:
                try:
                    last_lidar_outer_dist = float(form["last_lidar_outer_dist"])
                except ValueError as exc:
                    raise ValueError("主要 Lidar 最後一顆到外側護欄距離需為數字") from exc
                if last_lidar_outer_dist < 0:
                    raise ValueError("主要 Lidar 最後一顆到外側護欄距離不可為負數")

            results = calculate_lidar_results(all_lanes, lidar_assignments, lidar_centers)
            warnings = _build_warnings(
                results, all_lanes, lidar_centers, last_lidar_outer_dist, "主要 Lidar" if has_backup else None
            )
            lidar_groups = [{
                "label": "主要 Lidar",
                "lidar_assignments": lidar_assignments,
                "lidar_centers": lidar_centers,
                "results": results,
                "last_lidar_outer_dist": last_lidar_outer_dist,
            }]

            if has_backup:
                backup_lidar_assignments = _parse_assignments(backup_lidar_assignments_str)
                backup_lidar_centers = _parse_float_list(backup_lidar_centers_str, "備援 Lidar 中心距離")
                if len(backup_lidar_assignments) != len(backup_lidar_centers):
                    raise ValueError("備援 Lidar 負責車道行數需與備援 Lidar 中心距離數量相同")
                for i, assigned in enumerate(backup_lidar_assignments):
                    for lane_idx in assigned:
                        if lane_idx < 0 or lane_idx >= lane_count:
                            raise ValueError(
                                f"備援 LIDAR_{i} 指定的 Lane{lane_idx} 超出範圍 (0~{lane_count - 1})"
                            )
                for c in backup_lidar_centers:
                    if c < 0:
                        raise ValueError("備援 Lidar 中心距離不可為負數")

                backup_last_lidar_outer_dist = None
                if form["backup_last_lidar_outer_dist"]:
                    try:
                        backup_last_lidar_outer_dist = float(form["backup_last_lidar_outer_dist"])
                    except ValueError as exc:
                        raise ValueError("備援 Lidar 最後一顆到外側護欄距離需為數字") from exc
                    if backup_last_lidar_outer_dist < 0:
                        raise ValueError("備援 Lidar 最後一顆到外側護欄距離不可為負數")

                backup_results = calculate_lidar_results(
                    all_lanes, backup_lidar_assignments, backup_lidar_centers
                )
                warnings.extend(
                    _build_warnings(
                        backup_results,
                        all_lanes,
                        backup_lidar_centers,
                        backup_last_lidar_outer_dist,
                        "備援 Lidar",
                    )
                )
                lidar_groups.append({
                    "label": "備援 Lidar",
                    "lidar_assignments": backup_lidar_assignments,
                    "lidar_centers": backup_lidar_centers,
                    "results": backup_results,
                    "last_lidar_outer_dist": backup_last_lidar_outer_dist,
                })

            info_messages = []
            history_table = None
            if site_name:
                note = "Web UI 產生測試報表（含備援）" if has_backup else "Web UI 產生測試報表"
                try:
                    save_result(
                        site_name,
                        all_lanes,
                        lidar_assignments,
                        lidar_centers,
                        results,
                        note=note,
                        last_lidar_outer_dist=last_lidar_outer_dist,
                    )
                    records = load_records(site_name)
                    history_table = _render_history_table(site_name, records)
                    info_messages.append(
                        f"已儲存點位「{site_name}」歷史設定（共 {len(records)} 筆）。"
                    )
                except OSError as exc:
                    warnings.append(f"歷史設定儲存失敗：{exc}")
            else:
                info_messages.append("未填寫點位名稱，本次結果不會寫入歷史設定。")

            self._send_html(
                _render_page(
                    form=form,
                    lidar_groups=lidar_groups,
                    warnings=warnings,
                    info=info_messages,
                    history_table=history_table,
                    all_lanes=all_lanes,
                )
            )
        except ValueError as e:
            self._send_html(_render_page(form=form, error=str(e)))


def main():
    host = "127.0.0.1"
    port = 8000
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Web UI 啟動中: http://{host}:{port}")
    print("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
