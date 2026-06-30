#!/usr/bin/env python3
"""
簡易 Web UI：Lidar 有效區計算

執行:
  python examples/web_ui.py
"""

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from verify_lidar_calculation import SCAN_LIMIT, calculate_lidar_results

MAX_BODY_SIZE = 16 * 1024


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


def _build_warnings(results, all_lanes, lidar_centers, last_lidar_outer_dist):
    warnings = []
    for r in results:
        if r["scan_right"] > SCAN_LIMIT:
            warnings.append(
                f"LIDAR_{r['index']} scan_right={r['scan_right']:.0f}mm 超過 {SCAN_LIMIT:.0f}mm"
            )
        if r["scan_left"] > SCAN_LIMIT:
            warnings.append(
                f"LIDAR_{r['index']} scan_left={r['scan_left']:.0f}mm 超過 {SCAN_LIMIT:.0f}mm"
            )
        if r["scan_right"] < 0 or r["scan_left"] < 0:
            warnings.append(f"LIDAR_{r['index']} 出現負值，請確認輸入資料")

    if last_lidar_outer_dist is not None:
        total_lanes = sum(w for _, w in all_lanes)
        measured = lidar_centers[-1] + last_lidar_outer_dist
        diff = abs(measured - total_lanes)
        if diff >= 500:
            warnings.append(
                f"路寬一致性警告: 實測合計={measured:.0f}mm、車道總寬={total_lanes:.0f}mm、差距={diff:.0f}mm"
            )
    return warnings


def _render_page(form=None, results=None, warnings=None, error=None):
    form = form or {
        "site_name": "03F-040.7N",
        "lane_widths": "3800,3750,3800,3650,3400",
        "lidar_assignments": "0,1\n2,3\n4",
        "lidar_centers": "5000,11300,16700",
        "last_lidar_outer_dist": "1700",
    }
    results_html = ""
    if results:
        rows = []
        for r in results:
            lanes = "+".join(f"Lane{i}" for i in r["assigned"])
            rows.append(
                "<tr>"
                f"<td>LIDAR_{r['index']}</td>"
                f"<td>{escape(lanes)}</td>"
                f"<td>{r['center']:.0f}</td>"
                f"<td>{r['scan_right']:.0f}</td>"
                f"<td>{r['scan_left']:.0f}</td>"
                f"<td>{r['offset_value']:.0f}</td>"
                "</tr>"
            )
        results_html = (
            "<h2>計算結果</h2>"
            "<table border='1' cellpadding='6' cellspacing='0'>"
            "<tr><th>Lidar</th><th>負責車道</th><th>中心距離(mm)</th>"
            "<th>scan_right(mm)</th><th>scan_left(mm)</th><th>偏差值(mm)</th></tr>"
            + "".join(rows)
            + "</table>"
        )

    warnings_html = ""
    if warnings:
        warnings_html = "<h3>警告</h3><ul>" + "".join(
            f"<li>{escape(w)}</li>" for w in warnings
        ) + "</ul>"

    error_html = f"<p style='color:red'>{escape(error)}</p>" if error else ""

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <title>Lidar 計算 Web UI</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; max-width: 960px; }}
    label {{ display: block; margin-top: 10px; font-weight: 600; }}
    input, textarea {{ width: 100%; padding: 8px; box-sizing: border-box; }}
    button {{ margin-top: 14px; padding: 8px 16px; }}
    h1, h2 {{ margin-bottom: 8px; }}
  </style>
</head>
<body>
  <h1>Lidar 有效區計算 Web UI</h1>
  <form method="post" action="/calculate">
    <label>點位名稱</label>
    <input name="site_name" value="{escape(form['site_name'])}" />

    <label>車道寬度 (mm, 逗號分隔)</label>
    <input name="lane_widths" value="{escape(form['lane_widths'])}" />

    <label>Lidar 負責車道 (每行一顆 Lidar，逗號分隔 lane index)</label>
    <textarea name="lidar_assignments" rows="4">{escape(form['lidar_assignments'])}</textarea>

    <label>Lidar 中心距離 (mm, 逗號分隔)</label>
    <input name="lidar_centers" value="{escape(form['lidar_centers'])}" />

    <label>最後一顆 Lidar 到外側護欄距離 (mm，可留空)</label>
    <input name="last_lidar_outer_dist" value="{escape(form['last_lidar_outer_dist'])}" />

    <button type="submit">計算</button>
  </form>
  {error_html}
  {results_html}
  {warnings_html}
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
        if self.path != "/calculate":
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
        raw = self.rfile.read(content_length).decode("utf-8")
        payload = parse_qs(raw)
        form = {
            "site_name": payload.get("site_name", [""])[0].strip(),
            "lane_widths": payload.get("lane_widths", [""])[0].strip(),
            "lidar_assignments": payload.get("lidar_assignments", [""])[0].strip(),
            "lidar_centers": payload.get("lidar_centers", [""])[0].strip(),
            "last_lidar_outer_dist": payload.get("last_lidar_outer_dist", [""])[0].strip(),
        }

        try:
            lane_widths = _parse_float_list(form["lane_widths"], "車道寬度")
            all_lanes = [(i, w) for i, w in enumerate(lane_widths)]
            lidar_assignments = _parse_assignments(form["lidar_assignments"])
            lidar_centers = _parse_float_list(form["lidar_centers"], "Lidar 中心距離")

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
                    raise ValueError("最後一顆 Lidar 到外側護欄距離需為數字") from exc
                if last_lidar_outer_dist < 0:
                    raise ValueError("最後一顆 Lidar 到外側護欄距離不可為負數")

            results = calculate_lidar_results(all_lanes, lidar_assignments, lidar_centers)
            warnings = _build_warnings(
                results, all_lanes, lidar_centers, last_lidar_outer_dist
            )
            self._send_html(_render_page(form=form, results=results, warnings=warnings))
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
