"""Flask web UI for the device parameter tool."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

from device_parameter_tool.models.device_config import DeviceConfig, LaneConfig, LidarConfig
from device_parameter_tool.services.config_service import ConfigService
from device_parameter_tool.services.lidar_calculator import calculate_lane_info, calculate_lidar_results, calculate_sopas_fields
from device_parameter_tool.utils.validators import SITE_ROUTE_OPTIONS, lane_slot_labels, physical_slots_from_inner_outer, site_route_label


def _coerce_int(value: str | None, default: int = 0) -> int:
    if value is None or str(value).strip() == "":
        return default
    return int(value)


def _coerce_float(value: str | None, default: float = 0.0) -> float:
    if value is None or str(value).strip() == "":
        return default
    return float(value)


def _coerce_bool(value: str | None) -> bool:
    return value in {"1", "true", "True", "on", "yes"}


def _parse_lane_pair(first_value: str | None, second_value: str | None) -> list[int]:
    lanes: list[int] = []
    right_lane = None if first_value is None or str(first_value).strip() == "" or str(first_value).strip().lower() == "none" else int(first_value)
    left_lane = None if second_value is None or str(second_value).strip() == "" or str(second_value).strip().lower() == "none" else int(second_value)
    for value in (right_lane, left_lane):
        if value is not None and value not in lanes:
            lanes.append(value)
    return lanes


def _traffic_mode_labels(traffic_mode: str) -> tuple[str, str]:
    return lane_slot_labels(traffic_mode)


def _require_fields(form, field_names: list[str]) -> None:
    missing = [field_name for field_name in field_names if field_name not in form]
    if missing:
        raise ValueError(f"表單缺少必要欄位: {', '.join(missing)}")


def _build_lane_rows(form, lane_count: int) -> list[LaneConfig]:
    lanes: list[LaneConfig] = []
    for index in range(lane_count):
        _require_fields(form, [f"lane_{index}_number", f"lane_{index}_width_mm"])
        lanes.append(
            LaneConfig(
                lane_number=_coerce_int(form.get(f"lane_{index}_number"), index),
                width_mm=_coerce_float(form.get(f"lane_{index}_width_mm"), 0.0),
            )
        )
    return lanes


def _build_lidar_rows(form, lidar_count: int, prefix: str = "primary") -> list[LidarConfig]:
    traffic_mode = form.get("traffic_mode", "inner_from_right")
    lidars: list[LidarConfig] = []
    for index in range(lidar_count):
        _require_fields(
            form,
            [
                f"{prefix}_lidar_{index}_lane_a",
                f"{prefix}_lidar_{index}_lane_b",
                f"{prefix}_lidar_{index}_center_distance_mm",
            ],
        )
        inner_lane = None if form.get(f"{prefix}_lidar_{index}_lane_a") in {None, "", "none"} else int(form.get(f"{prefix}_lidar_{index}_lane_a"))
        outer_lane = None if form.get(f"{prefix}_lidar_{index}_lane_b") in {None, "", "none"} else int(form.get(f"{prefix}_lidar_{index}_lane_b"))
        right_lane, left_lane = physical_slots_from_inner_outer(inner_lane, outer_lane, traffic_mode)
        lidars.append(
            LidarConfig(
                inner_lane=inner_lane,
                outer_lane=outer_lane,
                right_lane=right_lane,
                left_lane=left_lane,
                assigned_lanes=_parse_lane_pair(
                    form.get(f"{prefix}_lidar_{index}_lane_a"),
                    form.get(f"{prefix}_lidar_{index}_lane_b"),
                ),
                center_distance_mm=_coerce_float(form.get(f"{prefix}_lidar_{index}_center_distance_mm"), 0.0),
                auto_calculate=_coerce_bool(form.get(f"{prefix}_lidar_{index}_auto_calculate")),
            )
        )
    return lidars


def _config_from_form(form) -> DeviceConfig:
    lane_count = max(1, _coerce_int(form.get("lane_count"), 1))
    lidar_count = max(0, _coerce_int(form.get("primary_lidar_count"), 1))
    backup_lidar_count = max(0, _coerce_int(form.get("backup_lidar_count"), lidar_count))
    has_backup = _coerce_bool(form.get("has_backup"))
    return DeviceConfig(
        site_name=form.get("site_name", "").strip(),
        note=form.get("note", ""),
        has_backup=has_backup,
        traffic_mode=form.get("traffic_mode", "inner_from_right"),
        lidar_label_start=_coerce_int(form.get("lidar_label_start"), 0),
        lanes=_build_lane_rows(form, lane_count),
        lidars=_build_lidar_rows(form, lidar_count, prefix="primary"),
        backup_lidars=_build_lidar_rows(form, backup_lidar_count, prefix="backup") if has_backup else [],
    )


def _lidar_form_rows(lidars: list[LidarConfig]) -> list[dict]:
    return [
        {
            "lane_a": lidar.inner_lane if lidar.inner_lane is not None else "none",
            "lane_b": lidar.outer_lane if lidar.outer_lane is not None else "none",
            "center_distance_mm": lidar.center_distance_mm,
            "auto_calculate": lidar.auto_calculate,
        }
        for lidar in lidars
    ]


def _lane_options(config: DeviceConfig) -> list[dict]:
    lane_numbers = {lane.lane_number for lane in config.lanes}
    return [{"value": "none", "label": "None"}] + [
        {"value": lane_number, "label": str(lane_number)}
        for lane_number in sorted(lane_numbers)
    ]


def _form_defaults(config: DeviceConfig) -> dict:
    inner_label, outer_label = _traffic_mode_labels(config.traffic_mode)
    lane_rows = [
        {
            "lane_number": lane.lane_number,
            "width_mm": lane.width_mm,
        }
        for lane in config.lanes
    ]
    lidar_rows = _lidar_form_rows(config.lidars)
    backup_lidar_rows = _lidar_form_rows(config.backup_lidars)
    return {
        "site_name": config.site_name,
        "note": config.note,
        "has_backup": config.has_backup,
        "traffic_mode": config.traffic_mode,
        "lidar_label_start": config.lidar_label_start,
        "inner_label": inner_label,
        "outer_label": outer_label,
        "lane_count": max(1, len(lane_rows)),
        "primary_lidar_count": len(lidar_rows),
        "backup_lidar_count": len(backup_lidar_rows),
        "lanes": lane_rows or [{"lane_number": 0, "width_mm": ""}],
        "lidars": lidar_rows or [{"lane_a": 0, "lane_b": "none", "center_distance_mm": "", "auto_calculate": True}],
        "backup_lidars": backup_lidar_rows or [{"lane_a": 0, "lane_b": "none", "center_distance_mm": "", "auto_calculate": True}],
        "lane_options": _lane_options(config),
    }


def _posted_form_state(form) -> dict:
    lane_count = max(1, _coerce_int(form.get("lane_count"), 1))
    primary_lidar_count = max(0, _coerce_int(form.get("primary_lidar_count"), 1))
    backup_lidar_count = max(0, _coerce_int(form.get("backup_lidar_count"), primary_lidar_count))
    has_backup = _coerce_bool(form.get("has_backup"))
    traffic_mode = form.get("traffic_mode", "inner_from_right")
    inner_label, outer_label = _traffic_mode_labels(traffic_mode)
    lanes = [
        {
            "lane_number": form.get(f"lane_{index}_number", index),
            "width_mm": form.get(f"lane_{index}_width_mm", ""),
        }
        for index in range(lane_count)
    ]
    lidars = [
        {
            "lane_a": form.get(f"primary_lidar_{index}_lane_a", "none"),
            "lane_b": form.get(f"primary_lidar_{index}_lane_b", "none"),
            "center_distance_mm": form.get(f"primary_lidar_{index}_center_distance_mm", ""),
            "auto_calculate": _coerce_bool(form.get(f"primary_lidar_{index}_auto_calculate")),
        }
        for index in range(primary_lidar_count)
    ]
    backup_lidars = [
        {
            "lane_a": form.get(f"backup_lidar_{index}_lane_a", "none"),
            "lane_b": form.get(f"backup_lidar_{index}_lane_b", "none"),
            "center_distance_mm": form.get(f"backup_lidar_{index}_center_distance_mm", ""),
            "auto_calculate": _coerce_bool(form.get(f"backup_lidar_{index}_auto_calculate")),
        }
        for index in range(backup_lidar_count)
    ]
    lane_numbers = {str(lane["lane_number"]).strip() for lane in lanes if str(lane["lane_number"]).strip() != ""}
    return {
        "site_name": form.get("site_name", "").strip(),
        "note": form.get("note", ""),
        "has_backup": has_backup,
        "traffic_mode": traffic_mode,
        "lidar_label_start": _coerce_int(form.get("lidar_label_start"), 0),
        "inner_label": inner_label,
        "outer_label": outer_label,
        "lane_count": lane_count,
        "primary_lidar_count": primary_lidar_count,
        "backup_lidar_count": backup_lidar_count,
        "lanes": lanes,
        "lidars": lidars,
        "backup_lidars": backup_lidars,
        "lane_options": [{"value": "none", "label": "None"}] + [
            {"value": lane_number, "label": lane_number}
            for lane_number in sorted(
                lane_numbers,
                key=lambda value: (not str(value).lstrip("-").isdigit(), int(value) if str(value).lstrip("-").isdigit() else str(value)),
            )
        ],
    }


def _build_history_browser(history_records):
    indexed_records = [
        {
            "index": index,
            "record": record,
            "category": site_route_label(record.config.site_name),
            "site_name": record.config.site_name,
        }
        for index, record in enumerate(history_records)
    ]
    sites_by_category = {
        category: sorted(
            {item["site_name"] for item in indexed_records if item["category"] == category}
        )
        for category, _ in SITE_ROUTE_OPTIONS
    }
    selected_category = request.args.get("history_category", "")
    categories = [category for category, _ in SITE_ROUTE_OPTIONS]
    if selected_category not in categories:
        selected_category = categories[0] if any(sites_by_category.values()) else ""
    site_options = sites_by_category.get(selected_category, []) if selected_category else []
    selected_site = request.args.get("history_site", "")
    if selected_site not in site_options:
        selected_site = site_options[0] if site_options else ""
    recent_records = [
        item for item in indexed_records
        if item["category"] == selected_category and item["site_name"] == selected_site
    ][:3]
    return {
        "categories": categories,
        "selected_category": selected_category,
        "site_options": site_options,
        "selected_site": selected_site,
        "recent_records": recent_records,
        "route_prefixes": {category: prefix for category, prefix in SITE_ROUTE_OPTIONS},
    }


def create_app(data_dir: str | Path | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates")
    base_dir = Path(data_dir or "data")
    service = ConfigService(config_path=base_dir / "current_config.json", history_path=base_dir / "site_history.json")

    def render_page(
        config: DeviceConfig | None = None,
        message: str = "",
        error: str = "",
        form_state: dict | None = None,
        form_collapsed: bool = False,
    ):
        summaries = []
        lane_info = []
        history_records = service.load_history()
        try:
            if config and config.lanes:
                lane_info = calculate_lane_info(config.lanes)
            if config and config.lanes and config.lidars:
                summaries.append({
                    "label": "Primary Lidar Dtmod",
                    "summary": calculate_lidar_results(config.lanes, config.lidars, config.traffic_mode),
                    "fields": calculate_sopas_fields(config.lanes, config.lidars, config.traffic_mode),
                })
            if config and config.has_backup and config.lanes and config.backup_lidars:
                summaries.append({
                    "label": "Backup Lidar Dtmod",
                    "summary": calculate_lidar_results(config.lanes, config.backup_lidars, config.traffic_mode),
                    "fields": calculate_sopas_fields(config.lanes, config.backup_lidars, config.traffic_mode),
                })
        except ValueError as exc:
            error = str(exc)
        return render_template(
            "index.html",
            form=form_state or _form_defaults(config or DeviceConfig(site_name="", lanes=[LaneConfig(lane_number=0, width_mm=3500.0)])),
            summaries=summaries,
            lane_info=lane_info,
            message=message,
            error=error,
            history_browser=_build_history_browser(history_records),
            form_collapsed=form_collapsed,
        )

    @app.get("/")
    def index():
        if service.config_path.exists():
            config = service.load_config()
        else:
            config = DeviceConfig(lanes=[LaneConfig(lane_number=0, width_mm=3500.0)])
        return render_page(config)

    @app.post("/preview")
    def preview():
        try:
            config = _config_from_form(request.form)
            config.validate()
        except ValueError as exc:
            return render_page(error=str(exc), form_state=_posted_form_state(request.form))
        return render_page(config, message="已更新預覽")

    @app.post("/save")
    def save():
        try:
            config = _config_from_form(request.form)
            config.validate()
        except ValueError as exc:
            return render_page(error=str(exc), form_state=_posted_form_state(request.form))
        service.save_config(config)
        service.append_history(config, note=config.note)
        return render_page(config, message="設定已儲存，並寫入 Site History", form_collapsed=True)

    @app.get("/history/<int:index>")
    def load_history(index: int):
        history = service.load_history()
        if index < 0 or index >= len(history):
            return redirect(url_for("index"))
        record = history[index]
        config = DeviceConfig.from_dict(record.config.to_dict())
        config.note = record.note
        return render_page(config, message=f"已載入歷史紀錄：{record.saved_at}")

    return app


def main() -> None:
    create_app().run(debug=False)


if __name__ == "__main__":
    main()
