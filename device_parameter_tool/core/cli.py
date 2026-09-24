"""Traditional Chinese interactive CLI."""

from __future__ import annotations

from pathlib import Path

from device_parameter_tool.models.device_config import CameraConfig, DeviceConfig, HostConfig, LaneConfig, LidarConfig
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


def print_lanes(config: DeviceConfig) -> None:
    print("\n【車道列表】")
    for lane in sorted(config.lanes, key=lambda item: item.lane_number):
        print(f"- Lane{lane.lane_number}: {lane.width_mm:.0f} mm")


def print_lidars(config: DeviceConfig) -> None:
    print("\n【Lidar 列表】")
    for index, lidar in enumerate(config.lidars):
        lanes = ", ".join(f"Lane{lane}" for lane in lidar.assigned_lanes)
        print(f"- LIDAR_{index}: {lanes} / center={lidar.center_distance_mm:.0f} mm")


def edit_camera(config: DeviceConfig) -> None:
    config.camera = CameraConfig(
        latitude=prompt_float("Camera 緯度", config.camera.latitude),
        longitude=prompt_float("Camera 經度", config.camera.longitude),
        orientation_deg=prompt_float("Camera 朝向角度", config.camera.orientation_deg),
        ip=prompt_text("Camera IP", config.camera.ip),
        port=prompt_int("Camera Port", config.camera.port),
        protocol=prompt_text("Camera 協定", config.camera.protocol),
    )


def edit_host(config: DeviceConfig) -> None:
    config.host = HostConfig(
        ip=prompt_text("Host IP", config.host.ip),
        port=prompt_int("Host Port", config.host.port),
        log_level=prompt_text("Log Level", config.host.log_level),
    )


def lane_menu(config: DeviceConfig) -> None:
    while True:
        print_lanes(config)
        choice = prompt_text("車道管理：1新增 2編輯 3刪除 4返回", "4")
        if choice == "1":
            config.lanes.append(LaneConfig(prompt_int("車道編號"), prompt_float("車道寬度(mm)")))
        elif choice == "2":
            lane_number = prompt_int("要編輯的車道編號")
            lane = next((lane for lane in config.lanes if lane.lane_number == lane_number), None)
            if not lane:
                print("✗ 找不到車道")
                continue
            lane.width_mm = prompt_float("新的車道寬度(mm)", lane.width_mm)
        elif choice == "3":
            lane_number = prompt_int("要刪除的車道編號")
            config.lanes = [lane for lane in config.lanes if lane.lane_number != lane_number]
        elif choice == "4":
            return
        try:
            config.validate()
        except ValueError as exc:
            print(f"✗ {exc}")


def lidar_menu(config: DeviceConfig) -> None:
    while True:
        print_lidars(config)
        choice = prompt_text("Lidar 管理：1新增 2編輯 3刪除 4預覽計算 5返回", "5")
        if choice in {"1", "2"}:
            index = len(config.lidars) if choice == "1" else prompt_int("Lidar 索引")
            if choice == "2" and (index < 0 or index >= len(config.lidars)):
                print("✗ 找不到 Lidar")
                continue
            assigned = [int(item.strip()) for item in prompt_text("負責車道 (逗號分隔)", ",".join(str(lane) for lane in config.lidars[index].assigned_lanes) if choice == "2" else None).split(",") if item.strip()]
            center_distance = prompt_float("中心點距離(mm)", config.lidars[index].center_distance_mm if choice == "2" else None)
            lidar = LidarConfig(assigned_lanes=assigned, center_distance_mm=center_distance)
            if choice == "1":
                config.lidars.append(lidar)
            else:
                config.lidars[index] = lidar
        elif choice == "3":
            index = prompt_int("要刪除的 Lidar 索引")
            if 0 <= index < len(config.lidars):
                del config.lidars[index]
        elif choice == "4":
            show_report(config)
        elif choice == "5":
            return
        try:
            config.validate()
        except ValueError as exc:
            print(f"✗ {exc}")


def quick_setup(config: DeviceConfig) -> None:
    config.site_name = prompt_text("點位名稱", config.site_name)
    config.note = prompt_text("備註（可留空）", config.note)
    lane_count = prompt_int("車道數量")
    lidar_count = prompt_int("Lidar 數量")
    config.lanes = [LaneConfig(lane_number=index, width_mm=prompt_float(f"Lane{index} 寬度(mm)")) for index in range(lane_count)]
    config.lidars = []
    for index in range(lidar_count):
        assigned = [int(item.strip()) for item in prompt_text(f"LIDAR_{index} 負責車道 (逗號分隔，例如 0,1)").split(",") if item.strip()]
        center = prompt_float(f"LIDAR_{index} 中心點距離(mm)")
        config.lidars.append(LidarConfig(assigned_lanes=assigned, center_distance_mm=center))
    show_report(config)


def show_report(config: DeviceConfig) -> None:
    try:
        summary = calculate_for_config(config)
        print("\n" + render_text_report(config, summary))
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
            "3. Lidar CRUD\n"
            "4. 編輯 Camera\n"
            "5. 編輯 Host\n"
            "6. 預覽計算結果\n"
            "7. 讀取設定檔\n"
            "8. 儲存/匯出設定檔\n"
            "9. 離開\n"
        )
        choice = prompt_text("請選擇功能", "9")
        try:
            if choice == "1":
                quick_setup(config)
            elif choice == "2":
                lane_menu(config)
            elif choice == "3":
                lidar_menu(config)
            elif choice == "4":
                edit_camera(config)
            elif choice == "5":
                edit_host(config)
            elif choice == "6":
                show_report(config)
            elif choice == "7":
                path = Path(prompt_text("請輸入設定檔路徑", str(service.config_path)))
                config = service.load_config(path)
                print(f"✓ 已讀取 {path}")
            elif choice == "8":
                path = Path(prompt_text("請輸入輸出檔案路徑", str(service.config_path)))
                config.validate()
                service.save_config(config, path)
                print(f"✓ 已儲存 {path}（若原檔存在會同步備份 .bak）")
            elif choice == "9":
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
