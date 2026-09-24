"""Traditional Chinese interactive CLI."""

from __future__ import annotations

from pathlib import Path

from device_parameter_tool.models.device_config import DeviceConfig, LaneConfig, LidarConfig
from device_parameter_tool.services.config_service import ConfigService
from device_parameter_tool.services.lidar_calculator import calculate_for_config, render_text_report


def prompt_text(message: str, default: str | None = None) -> str:
    raw = input(f"{message}{f' [{default}]' if default is not None else ''}: ").strip()
    return raw if raw else (default or "")


def prompt_int(message: str, default: int | None = None) -> int:
    while True:
        raw = prompt_text(message, str(default) if default is not None else None)
        try:
            return int(raw)
        except ValueError:
            print("✗ 請輸入整數")


def prompt_float(message: str, default: float | None = None) -> float:
    while True:
        raw = prompt_text(message, f"{default}" if default is not None else None)
        try:
            return float(raw)
        except ValueError:
            print("✗ 請輸入數字")


def prompt_bool(message: str, default: bool = True) -> bool:
    default_text = "Y" if default else "N"
    while True:
        raw = prompt_text(f"{message} (Y/N)", default_text).strip().lower()
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("✗ 請輸入 Y 或 N")


def config_clone(config: DeviceConfig) -> DeviceConfig:
    return DeviceConfig.from_dict(config.to_dict())


def print_lanes(config: DeviceConfig) -> None:
    print("\n【車道列表】")
    for lane in sorted(config.lanes, key=lambda item: item.lane_number):
        print(f"- Lane{lane.lane_number} / width={lane.width_mm:.0f} mm")


def print_lidars(config: DeviceConfig, label: str, lidars: list[LidarConfig]) -> None:
    print(f"\n【{label} 列表】")
    for index, lidar in enumerate(lidars):
        lanes = ", ".join(f"Lane{lane}" for lane in lidar.assigned_lanes)
        print(
            f"- LIDAR_{index} / lanes={lanes or 'None'} / "
            f"center={lidar.center_distance_mm:.0f} mm / auto={'Y' if lidar.auto_calculate else 'N'}"
        )


def build_lane(existing: LaneConfig | None = None, default_number: int = 0) -> LaneConfig:
    existing = existing or LaneConfig(lane_number=default_number, width_mm=3500.0)
    return LaneConfig(
        lane_number=prompt_int("車道編號", existing.lane_number),
        width_mm=prompt_float("車道寬度(mm)", existing.width_mm),
    )


def prompt_lane_option(message: str, available_lane_numbers: list[int], default: int | None = None) -> int | None:
    default_text = "None" if default is None else str(default)
    option_text = ", ".join([str(lane) for lane in available_lane_numbers]) or "無可用車道"
    while True:
        raw = prompt_text(f"{message} (None/{option_text})", default_text).strip()
        if not raw or raw.lower() == "none":
            return None
        normalized = raw.lower().replace("lane", "")
        try:
            lane = int(normalized)
        except ValueError:
            print(f"✗ 請輸入 None 或 {option_text}")
            continue
        if lane in available_lane_numbers:
            return lane
        print(f"✗ 請輸入 None 或 {option_text}")


def build_lidar(available_lane_numbers: list[int], existing: LidarConfig | None = None) -> LidarConfig:
    existing = existing or LidarConfig(assigned_lanes=[0], center_distance_mm=0.0)
    default_first = existing.assigned_lanes[0] if existing.assigned_lanes else None
    default_second = existing.assigned_lanes[1] if len(existing.assigned_lanes) > 1 else None
    lane_a = prompt_lane_option("右(Lane1)", available_lane_numbers, default_first)
    lane_b = prompt_lane_option("左(Lane2)", available_lane_numbers, default_second)
    assigned = [lane for lane in [lane_a, lane_b] if lane is not None]
    return LidarConfig(
        assigned_lanes=assigned,
        center_distance_mm=prompt_float("中心點距離(mm)", existing.center_distance_mm),
        auto_calculate=prompt_bool("自動計算有效偵測範圍", existing.auto_calculate),
    )


def lane_menu(config: DeviceConfig) -> None:
    while True:
        print_lanes(config)
        choice = prompt_text("車道管理：1新增 2編輯 3刪除 4返回", "4")
        snapshot = config_clone(config)
        if choice == "1":
            config.lanes.append(build_lane(default_number=len(config.lanes)))
        elif choice == "2":
            lane_number = prompt_int("要編輯的車道編號")
            lane = next((lane for lane in config.lanes if lane.lane_number == lane_number), None)
            if not lane:
                print("✗ 找不到車道")
                continue
            index = config.lanes.index(lane)
            config.lanes[index] = build_lane(existing=lane)
        elif choice == "3":
            lane_number = prompt_int("要刪除的車道編號")
            config.lanes = [lane for lane in config.lanes if lane.lane_number != lane_number]
        elif choice == "4":
            return
        try:
            config.validate()
        except ValueError as exc:
            config.lanes = snapshot.lanes
            config.lidars = snapshot.lidars
            config.backup_lidars = snapshot.backup_lidars
            config.has_backup = snapshot.has_backup
            print(f"✗ {exc}")


def lidar_menu(config: DeviceConfig, label: str, target_attr: str) -> None:
    while True:
        lidars = getattr(config, target_attr)
        print_lidars(config, label, lidars)
        choice = prompt_text(f"{label} 管理：1新增 2編輯 3刪除 4預覽計算 5返回", "5")
        snapshot = config_clone(config)
        available_lane_numbers = sorted(lane.lane_number for lane in config.lanes)
        if choice == "1":
            lidars.append(build_lidar(available_lane_numbers))
        elif choice == "2":
            index = prompt_int("Lidar 索引")
            if index < 0 or index >= len(lidars):
                print("✗ 找不到 Lidar")
                continue
            lidars[index] = build_lidar(available_lane_numbers, existing=lidars[index])
        elif choice == "3":
            index = prompt_int("要刪除的 Lidar 索引")
            if 0 <= index < len(lidars):
                del lidars[index]
        elif choice == "4":
            show_report(config)
        elif choice == "5":
            return
        try:
            config.validate()
        except ValueError as exc:
            config.lanes = snapshot.lanes
            config.lidars = snapshot.lidars
            config.backup_lidars = snapshot.backup_lidars
            config.has_backup = snapshot.has_backup
            print(f"✗ {exc}")


def quick_setup(config: DeviceConfig) -> None:
    site_name = prompt_text("點位名稱", config.site_name)
    note = prompt_text("備註（可留空）", config.note)
    has_backup = prompt_bool("是否啟用備援 Lidar", config.has_backup)
    lane_count = prompt_int("車道數量")
    lidar_count = prompt_int("主 Lidar 數量")
    backup_lidar_count = prompt_int("備援 Lidar 數量") if has_backup else 0
    lanes = [build_lane(default_number=index) for index in range(lane_count)]
    available_lane_numbers = sorted(lane.lane_number for lane in lanes)
    lidars = [build_lidar(available_lane_numbers) for _ in range(lidar_count)]
    backup_lidars = [build_lidar(available_lane_numbers) for _ in range(backup_lidar_count)] if has_backup else []
    candidate = DeviceConfig(
        site_name=site_name,
        note=note,
        has_backup=has_backup,
        lanes=lanes,
        lidars=lidars,
        backup_lidars=backup_lidars,
    )
    try:
        candidate.validate()
    except ValueError as exc:
        print(f"✗ {exc}")
        return
    config.site_name = candidate.site_name
    config.note = candidate.note
    config.has_backup = candidate.has_backup
    config.lanes = candidate.lanes
    config.lidars = candidate.lidars
    config.backup_lidars = candidate.backup_lidars
    show_report(config)


def show_report(config: DeviceConfig) -> None:
    try:
        primary_summary = calculate_for_config(config)
        print("\n【主 Lidar】")
        print(render_text_report(config, primary_summary))
        if config.has_backup and config.backup_lidars:
            backup_config = DeviceConfig.from_dict(config.to_dict())
            backup_config.lidars = [LidarConfig.from_dict(lidar.to_dict()) for lidar in config.backup_lidars]
            backup_config.has_backup = False
            backup_config.backup_lidars = []
            backup_summary = calculate_for_config(backup_config)
            print("\n【備援 Lidar】")
            print(render_text_report(backup_config, backup_summary))
    except ValueError as exc:
        print(f"✗ {exc}")


def main() -> None:
    service = ConfigService()
    config = DeviceConfig(lanes=[LaneConfig(lane_number=0, width_mm=3500.0)])
    print("\n╔══════════════════════════════════════════════╗")
    print("║       Device Parameter Tool (CLI)          ║")
    print("╚══════════════════════════════════════════════╝")
    while True:
        print(
            "\n主選單\n"
            "1. 快速設定\n"
            "2. 車道 CRUD\n"
            "3. 主 Lidar CRUD\n"
            "4. 備援開關 / 備援 Lidar CRUD\n"
            "5. 預覽計算結果\n"
            "6. 讀取設定檔\n"
            "7. 儲存/匯出設定檔\n"
            "8. 離開\n"
        )
        choice = prompt_text("請選擇功能", "8")
        try:
            if choice == "1":
                quick_setup(config)
            elif choice == "2":
                lane_menu(config)
            elif choice == "3":
                lidar_menu(config, "主 Lidar", "lidars")
            elif choice == "4":
                config.has_backup = prompt_bool("是否啟用備援 Lidar", config.has_backup)
                if not config.has_backup:
                    config.backup_lidars = []
                else:
                    if not config.backup_lidars:
                        default_lane = config.lanes[0].lane_number if config.lanes else 0
                        config.backup_lidars = [
                            LidarConfig(assigned_lanes=[default_lane], center_distance_mm=0.0)
                            for _ in range(max(1, len(config.lidars)))
                        ]
                    lidar_menu(config, "備援 Lidar", "backup_lidars")
            elif choice == "5":
                show_report(config)
            elif choice == "6":
                path = Path(prompt_text("請輸入設定檔路徑", str(service.config_path)))
                config = service.load_config(path)
                print(f"✓ 已讀取 {path}")
            elif choice == "7":
                path = Path(prompt_text("請輸入輸出檔案路徑", str(service.config_path)))
                config.validate()
                service.save_config(config, path)
                print(f"✓ 已儲存 {path}（若原檔存在會同步備份 .bak）")
            elif choice == "8":
                print("再見！")
                return
            else:
                print("✗ 無效選項")
        except ValueError as exc:
            print(f"✗ {exc}")
        except FileNotFoundError:
            print("✗ 找不到指定檔案")


if __name__ == "__main__":
    main()
