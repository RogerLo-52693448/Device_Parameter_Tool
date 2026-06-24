"""設備參數調整工具 CLI — 互動式繁體中文選單"""

import os
import sys

from src.main.python.models.device_config import (
    CameraConfig,
    LaneConfig,
    LidarUnit,
)
from src.main.python.services.config_service import ConfigService
from src.main.python.utils.validators import (
    validate_latitude,
    validate_log_level,
    validate_longitude,
    validate_non_negative_float,
    validate_non_negative_int,
    validate_orientation,
    validate_port,
    validate_positive_float,
    validate_positive_int,
    validate_transport,
)


def _validate_float(val) -> float:
    """Convert any input to float (allows negative values for offset distances)."""
    return float(val)

_DEFAULT_CONFIG = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "resources",
    "config",
    "device_params.json",
)


def _prompt(msg: str, default: str = "") -> str:
    """顯示提示並讀取使用者輸入；直接 Enter 則回傳預設值。"""
    suffix = f" (目前: {default}, 直接 Enter 保持不變)" if default != "" else ""
    user_input = input(f"{msg}{suffix}: ").strip()
    return user_input if user_input else default


def _ask(msg: str, validator=None, default=None):
    """持續詢問直到輸入合法。"""
    while True:
        raw = _prompt(msg, str(default) if default is not None else "")
        if raw == "" and default is not None:
            return default
        try:
            if validator:
                return validator(raw)
            return raw
        except (ValueError, TypeError) as e:
            print(f"  ✗ 輸入不合法: {e}")


def _separator():
    print("─" * 42)


def _header():
    print("\n╔══════════════════════════════════════════╗")
    print("║       設備參數調整工具 v1.0              ║")
    print("╚══════════════════════════════════════════╝")


# ─────────────────────────────────────────────────────────────────────────────
# Camera sub-menu
# ─────────────────────────────────────────────────────────────────────────────

def _camera_list(svc: ConfigService):
    cams = svc.config.cameras
    if not cams:
        print("  目前無相機設定。")
        return
    for cam in cams:
        rtsp_status = "已設定" if cam.rtsp_url else "未設定"
        print(f"  [{cam.camera_id}] {cam.name}  {cam.resolution} {cam.fps}fps  RTSP: {rtsp_status}")


def _camera_add(svc: ConfigService):
    print("\n【新增相機】")
    cam_id = _ask("相機 ID (例如 CAM_002)")
    if svc.get_camera(cam_id):
        print(f"  ✗ 相機 ID {cam_id} 已存在")
        return
    name = _ask("名稱")
    lat = _ask("緯度", validate_latitude)
    lon = _ask("經度", validate_longitude)
    deg = _ask("方向角度 (0~360)", validate_orientation)
    label = _ask("方向標示 (例如 N45E)")
    res = _ask("解析度 (例如 1920x1080)", default="1920x1080")
    fps = _ask("幀率 FPS", validate_positive_int, 30)
    exposure = _ask("曝光值", default="auto")
    wb = _ask("白平衡", default="auto")
    gain = _ask("增益", validate_non_negative_float, 0.0)
    shutter = _ask("快門速度 (例如 1/100)", default="1/100")
    rtsp = _ask("RTSP URL")
    cam = CameraConfig(
        camera_id=cam_id, name=name, latitude=lat, longitude=lon,
        orientation_degree=deg, orientation_label=label,
        resolution=res, fps=fps, exposure=exposure, white_balance=wb,
        gain=gain, shutter_speed=shutter, rtsp_url=rtsp,
    )
    svc.add_camera(cam)
    svc.save_config()
    print(f"  ✓ 相機 {cam_id} 已新增並存檔。")


def _camera_edit(svc: ConfigService):
    print("\n【修改相機】")
    cam_id = _ask("請輸入要修改的相機 ID")
    cam = svc.get_camera(cam_id)
    if cam is None:
        print(f"  ✗ 找不到相機 {cam_id}")
        return
    params = {}
    params["name"] = _ask("名稱", default=cam.name)
    params["latitude"] = _ask("緯度", validate_latitude, cam.latitude)
    params["longitude"] = _ask("經度", validate_longitude, cam.longitude)
    params["orientation_degree"] = _ask("方向角度", validate_orientation, cam.orientation_degree)
    params["orientation_label"] = _ask("方向標示", default=cam.orientation_label)
    params["resolution"] = _ask("解析度", default=cam.resolution)
    params["fps"] = _ask("幀率 FPS", validate_positive_int, cam.fps)
    params["exposure"] = _ask("曝光值", default=cam.exposure)
    params["white_balance"] = _ask("白平衡", default=cam.white_balance)
    params["gain"] = _ask("增益", validate_non_negative_float, cam.gain)
    params["shutter_speed"] = _ask("快門速度", default=cam.shutter_speed)
    params["rtsp_url"] = _ask("RTSP URL", default=cam.rtsp_url)
    svc.update_camera(cam_id, params)
    svc.save_config()
    print(f"  ✓ 相機 {cam_id} 已更新並存檔。")


def _camera_delete(svc: ConfigService):
    print("\n【刪除相機】")
    cam_id = _ask("請輸入要刪除的相機 ID")
    if svc.get_camera(cam_id) is None:
        print(f"  ✗ 找不到相機 {cam_id}")
        return
    confirm = input(f"  確定要刪除相機 {cam_id}？(y/N): ").strip().lower()
    if confirm == "y":
        svc.delete_camera(cam_id)
        svc.save_config()
        print(f"  ✓ 相機 {cam_id} 已刪除。")
    else:
        print("  已取消。")


def menu_camera(svc: ConfigService):
    while True:
        _separator()
        print("【相機參數設定】")
        print("  1. 列出所有相機")
        print("  2. 新增相機")
        print("  3. 修改相機")
        print("  4. 刪除相機")
        print("  0. 返回主選單")
        choice = input("請選擇 [0-4]: ").strip()
        if choice == "1":
            _camera_list(svc)
        elif choice == "2":
            _camera_add(svc)
        elif choice == "3":
            _camera_edit(svc)
        elif choice == "4":
            _camera_delete(svc)
        elif choice == "0":
            break
        else:
            print("  ✗ 無效選項，請重新輸入。")


# ─────────────────────────────────────────────────────────────────────────────
# Lane sub-menu
# ─────────────────────────────────────────────────────────────────────────────

def _lane_list(svc: ConfigService):
    lanes = svc.config.lanes
    if not lanes:
        print("  目前無車道設定。")
        return
    for lane in lanes:
        print(f"  [{lane.lane_id}] 車道{lane.lane_number}  寬度: {lane.width}mm  {lane.description}")


def _lane_add(svc: ConfigService):
    print("\n【新增車道】")
    lane_id = _ask("車道 ID (例如 LANE_003)")
    if svc.get_lane(lane_id):
        print(f"  ✗ 車道 ID {lane_id} 已存在")
        return
    number = _ask("車道編號 (由內到外，起始可為 0)", validate_non_negative_int, 0)
    width = _ask("車道寬度 (mm)", validate_positive_float)
    desc = _ask("備註說明", default="")
    lane = LaneConfig(lane_id=lane_id, lane_number=number, width=width, description=desc)
    svc.add_lane(lane)
    svc.save_config()
    print(f"  ✓ 車道 {lane_id} 已新增。")
    _ask_recalculate(svc)


def _lane_edit(svc: ConfigService):
    print("\n【修改車道】")
    lane_id = _ask("請輸入要修改的車道 ID")
    lane = svc.get_lane(lane_id)
    if lane is None:
        print(f"  ✗ 找不到車道 {lane_id}")
        return
    params = {}
    params["lane_number"] = _ask("車道編號", validate_non_negative_int, lane.lane_number)
    params["width"] = _ask("車道寬度 (mm)", validate_positive_float, lane.width)
    params["description"] = _ask("備註說明", default=lane.description)
    svc.update_lane(lane_id, params)
    svc.save_config()
    print(f"  ✓ 車道 {lane_id} 已更新。")
    _ask_recalculate(svc)


def _lane_delete(svc: ConfigService):
    print("\n【刪除車道】")
    lane_id = _ask("請輸入要刪除的車道 ID")
    if svc.get_lane(lane_id) is None:
        print(f"  ✗ 找不到車道 {lane_id}")
        return
    confirm = input(f"  確定要刪除車道 {lane_id}？(y/N): ").strip().lower()
    if confirm == "y":
        svc.delete_lane(lane_id)
        svc.save_config()
        print(f"  ✓ 車道 {lane_id} 已刪除。")
    else:
        print("  已取消。")


def _ask_recalculate(svc: ConfigService):
    choice = input("  是否要重新計算相關 Lidar 有效區？(y/N): ").strip().lower()
    if choice == "y":
        updated = svc.recalculate_all_lidars()
        svc.save_config()
        if updated:
            print(f"  ✓ 已重新計算: {', '.join(updated)}")
        else:
            print("  (無啟用自動計算的 Lidar)")


def menu_lane(svc: ConfigService):
    while True:
        _separator()
        print("【車道資訊設定】")
        print("  1. 列出所有車道")
        print("  2. 新增車道")
        print("  3. 修改車道")
        print("  4. 刪除車道")
        print("  0. 返回主選單")
        choice = input("請選擇 [0-4]: ").strip()
        if choice == "1":
            _lane_list(svc)
        elif choice == "2":
            _lane_add(svc)
        elif choice == "3":
            _lane_edit(svc)
        elif choice == "4":
            _lane_delete(svc)
        elif choice == "0":
            break
        else:
            print("  ✗ 無效選項，請重新輸入。")


# ─────────────────────────────────────────────────────────────────────────────
# Lidar sub-menu
# ─────────────────────────────────────────────────────────────────────────────

def _lidar_list(svc: ConfigService):
    units = svc.config.lidars.units
    if not units:
        print("  目前無 Lidar 設定。")
        return
    for unit in units:
        print(f"  [{unit.lidar_id}] 負責車道: {unit.assigned_lanes}  偏差: {unit.offset_distance}mm")
        print(f"      中心距: {unit.center_distance}mm  有效左: {unit.effective_left}mm  有效右: {unit.effective_right}mm")
        print(f"      自動計算: {'是' if unit.auto_calculate else '否'}  {unit.description}")


def _lidar_add(svc: ConfigService):
    print("\n【新增 Lidar】")
    lane_count = len(svc.config.lanes)
    lidar_count = len(svc.config.lidars.units)
    print(f"  目前車道數量: {lane_count}，目前 Lidar 數量: {lidar_count}")
    if lane_count == 0:
        print("  ✗ 尚未設定車道，請先完成車道設定。")
        return
    lidar_id = _ask("Lidar ID (例如 LIDAR_002)")
    if svc.get_lidar(lidar_id):
        print(f"  ✗ Lidar ID {lidar_id} 已存在")
        return
    center = _ask("中心點距離 (Lidar 到內路肩護欄，mm)", validate_non_negative_float, 0.0)
    lanes_input = _ask("負責車道 ID (最多 2 個，逗號分隔，例如 LANE_000,LANE_001)")
    assigned = [x.strip() for x in lanes_input.split(",") if x.strip()]
    if len(assigned) > 2:
        print("  ✗ 每個 Lidar 最多只能負責 2 個車道。")
        return
    offset = _ask("偏差距離 (mm，保留欄位)", _validate_float, 0.0)
    auto_calc = input("  是否啟用自動計算有效區？(Y/n): ").strip().lower() != "n"
    if auto_calc:
        eff_left, eff_right = 0.0, 0.0
    else:
        eff_left = _ask("往左有效區距離 (mm)", validate_non_negative_float, 0.0)
        eff_right = _ask("往右有效區距離 (mm)", validate_non_negative_float, 0.0)
    desc = _ask("備註說明", default="")
    unit = LidarUnit(
        lidar_id=lidar_id, assigned_lanes=assigned, offset_distance=offset,
        center_distance=center, effective_left=eff_left, effective_right=eff_right,
        auto_calculate=auto_calc, description=desc,
    )
    svc.add_lidar(unit)
    if auto_calc:
        try:
            svc.calculate_lidar_effective_range(lidar_id)
            calculated = svc.get_lidar(lidar_id)
            print(
                f"  計算結果: 有效左={calculated.effective_left}mm, "
                f"有效右={calculated.effective_right}mm"
            )
        except ValueError as e:
            print(f"  ⚠ 無法自動計算: {e}")
    svc.save_config()
    print(f"  ✓ Lidar {lidar_id} 已新增。")


def _lidar_edit(svc: ConfigService):
    print("\n【修改 Lidar】")
    lidar_id = _ask("請輸入要修改的 Lidar ID")
    unit = svc.get_lidar(lidar_id)
    if unit is None:
        print(f"  ✗ 找不到 Lidar {lidar_id}")
        return
    params = {}
    params["center_distance"] = _ask(
        "中心點距離 (Lidar 到內路肩護欄，mm)",
        validate_non_negative_float,
        unit.center_distance,
    )
    lanes_input = _ask(
        "負責車道 ID (最多 2 個，逗號分隔)",
        default=",".join(unit.assigned_lanes),
    )
    assigned = [x.strip() for x in lanes_input.split(",") if x.strip()]
    if len(assigned) > 2:
        print("  ✗ 每個 Lidar 最多只能負責 2 個車道。")
        return
    params["assigned_lanes"] = assigned
    params["offset_distance"] = _ask("偏差距離 (mm，保留欄位)", _validate_float, unit.offset_distance)
    auto_str = input(f"  目前自動計算: {'是' if unit.auto_calculate else '否'}  啟用自動計算？(y/n/Enter 保持不變): ").strip().lower()
    if auto_str == "y":
        params["auto_calculate"] = True
    elif auto_str == "n":
        params["auto_calculate"] = False
    params["description"] = _ask("備註說明", default=unit.description)
    svc.update_lidar(lidar_id, params)
    if svc.get_lidar(lidar_id).auto_calculate:
        try:
            svc.calculate_lidar_effective_range(lidar_id)
            calculated = svc.get_lidar(lidar_id)
            print(
                f"  計算結果: 有效左={calculated.effective_left}mm, "
                f"有效右={calculated.effective_right}mm"
            )
        except ValueError as e:
            print(f"  ⚠ 無法自動計算: {e}")
    else:
        eff_left = _ask("往左有效區距離 (mm)", validate_non_negative_float, unit.effective_left)
        eff_right = _ask("往右有效區距離 (mm)", validate_non_negative_float, unit.effective_right)
        svc.update_lidar(lidar_id, {"effective_left": eff_left, "effective_right": eff_right})
    svc.save_config()
    print(f"  ✓ Lidar {lidar_id} 已更新。")


def _lidar_delete(svc: ConfigService):
    print("\n【刪除 Lidar】")
    lidar_id = _ask("請輸入要刪除的 Lidar ID")
    if svc.get_lidar(lidar_id) is None:
        print(f"  ✗ 找不到 Lidar {lidar_id}")
        return
    confirm = input(f"  確定要刪除 Lidar {lidar_id}？(y/N): ").strip().lower()
    if confirm == "y":
        svc.delete_lidar(lidar_id)
        svc.save_config()
        print(f"  ✓ Lidar {lidar_id} 已刪除。")
    else:
        print("  已取消。")


def _lidar_quick_setup(svc: ConfigService):
    print("\n【Lidar 快速設定】")
    lane_group_name = _ask("車道群組名稱", default=svc.config.lane_group_name)
    new_lane_count = _ask("車道數量", validate_positive_int)
    new_lidar_count = _ask("Lidar 數量", validate_positive_int)

    lanes = []
    for idx in range(new_lane_count):
        width = _ask(f"Lane{idx} 寬度 (mm)", validate_positive_float)
        lanes.append(
            LaneConfig(
                lane_id=f"LANE_{idx:03d}",
                lane_number=idx,
                width=width,
                description=f"Lane{idx}",
            )
        )

    units = []
    print("\n  請輸入每個 Lidar 的中心距離與負責車道（最多 2 個）")
    for idx in range(new_lidar_count):
        lidar_id = f"LIDAR_{idx:03d}"
        center_distance = _ask(f"{lidar_id} 中心點距離 (mm)", validate_non_negative_float)
        lane_numbers_raw = _ask(
            f"{lidar_id} 負責車道編號 (逗號分隔，例如 0,1)"
        )
        lane_numbers = [x.strip() for x in lane_numbers_raw.split(",") if x.strip()]
        if not lane_numbers or len(lane_numbers) > 2:
            print("  ✗ 每個 Lidar 必須指定 1~2 個車道。")
            return
        assigned_lanes = []
        for lane_num in lane_numbers:
            lane_idx = validate_non_negative_int(lane_num)
            if lane_idx >= new_lane_count:
                print(f"  ✗ Lane{lane_idx} 不存在。")
                return
            assigned_lanes.append(f"LANE_{lane_idx:03d}")
        units.append(
            LidarUnit(
                lidar_id=lidar_id,
                assigned_lanes=assigned_lanes,
                offset_distance=0.0,
                center_distance=center_distance,
                effective_left=0.0,
                effective_right=0.0,
                auto_calculate=True,
                description=f"快速設定 {lidar_id}",
            )
        )

    old_group_name = svc.config.lane_group_name
    old_lanes = svc.config.lanes
    old_units = svc.config.lidars.units
    svc.config.lane_group_name = lane_group_name
    svc.config.lanes = lanes
    svc.config.lidars.units = units

    try:
        for unit in units:
            svc.calculate_lidar_effective_range(unit.lidar_id)
    except ValueError as e:
        svc.config.lane_group_name = old_group_name
        svc.config.lanes = old_lanes
        svc.config.lidars.units = old_units
        print(f"  ✗ 快速設定失敗: {e}")
        return

    print("\n  計算結果預覽:")
    _lidar_list(svc)
    if input("  確認套用並存檔？(y/N): ").strip().lower() == "y":
        svc.save_config()
        print("  ✓ 快速設定已完成。")
    else:
        svc.config.lane_group_name = old_group_name
        svc.config.lanes = old_lanes
        svc.config.lidars.units = old_units
        print("  已取消，未套用變更。")


def menu_lidar(svc: ConfigService):
    while True:
        _separator()
        print("【Lidar 偵測設定】")
        print("  1. 列出所有 Lidar")
        print("  2. 新增 Lidar")
        print("  3. 修改 Lidar")
        print("  4. 刪除 Lidar")
        print("  5. 重新計算指定 Lidar 有效區")
        print("  6. 快速設定 (車道 + Lidar)")
        print("  0. 返回主選單")
        choice = input("請選擇 [0-6]: ").strip()
        if choice == "1":
            _lidar_list(svc)
        elif choice == "2":
            _lidar_add(svc)
        elif choice == "3":
            _lidar_edit(svc)
        elif choice == "4":
            _lidar_delete(svc)
        elif choice == "5":
            lidar_id = _ask("請輸入 Lidar ID")
            try:
                svc.calculate_lidar_effective_range(lidar_id)
                svc.save_config()
                unit = svc.get_lidar(lidar_id)
                print(f"  ✓ 計算完成  有效左: {unit.effective_left}mm  有效右: {unit.effective_right}mm")
            except ValueError as e:
                print(f"  ✗ {e}")
        elif choice == "6":
            _lidar_quick_setup(svc)
        elif choice == "0":
            break
        else:
            print("  ✗ 無效選項，請重新輸入。")


# ─────────────────────────────────────────────────────────────────────────────
# Host sub-menu
# ─────────────────────────────────────────────────────────────────────────────

def _host_view(svc: ConfigService):
    host = svc.config.host
    if host is None:
        print("  主機設定不存在。")
        return
    print(f"  MQTT IP       : {host.mqtt_ip}")
    print(f"  MQTT Port     : {host.mqtt_port}")
    print(f"  MQTT Timeout  : {host.mqtt_timeout}s")
    print(f"  RTSP 傳輸方式 : {host.rtsp_transport}")
    print(f"  儲存根路徑    : {host.save_root}")
    print(f"  緩衝區大小    : {host.buffer_seconds}s")
    print(f"  最大重試次數  : {host.max_retries}")
    print(f"  日誌等級      : {host.log_level}")
    print(f"  日誌路徑      : {host.log_dir}")
    print(f"  觸發主題      : {host.trigger_topic}")
    tc = host.trigger_conditions
    print(f"  觸發條件      : topic_contains={tc.topic_contains}, source={tc.source}, state={tc.state}")


def _host_edit(svc: ConfigService):
    host = svc.config.host
    if host is None:
        print("  主機設定不存在。")
        return
    params = {}
    params["mqtt_ip"] = _ask("MQTT IP", default=host.mqtt_ip)
    params["mqtt_port"] = _ask("MQTT Port", validate_port, host.mqtt_port)
    params["mqtt_timeout"] = _ask("MQTT Timeout (秒)", validate_positive_int, host.mqtt_timeout)
    params["rtsp_transport"] = _ask("RTSP 傳輸方式 (tcp/udp)", validate_transport, host.rtsp_transport)
    params["save_root"] = _ask("儲存根路徑", default=host.save_root)
    params["buffer_seconds"] = _ask("緩衝區大小 (秒)", validate_positive_float, host.buffer_seconds)
    params["max_retries"] = _ask("最大重試次數", validate_positive_int, host.max_retries)
    params["log_level"] = _ask("日誌等級 (DEBUG/INFO/WARNING/ERROR)", validate_log_level, host.log_level)
    params["log_dir"] = _ask("日誌路徑", default=host.log_dir)
    params["trigger_topic"] = _ask("觸發主題", default=host.trigger_topic)
    tc = host.trigger_conditions
    params["trigger_conditions"] = {
        "topic_contains": _ask("觸發條件 topic_contains", default=tc.topic_contains),
        "source": _ask("觸發條件 source", default=tc.source),
        "state": _ask("觸發條件 state", default=tc.state),
    }
    svc.update_host(params)
    svc.save_config()
    print("  ✓ 主機設定已更新並存檔。")


def menu_host(svc: ConfigService):
    while True:
        _separator()
        print("【主機參數設定】")
        print("  1. 檢視主機設定")
        print("  2. 修改主機設定")
        print("  0. 返回主選單")
        choice = input("請選擇 [0-2]: ").strip()
        if choice == "1":
            _host_view(svc)
        elif choice == "2":
            _host_edit(svc)
        elif choice == "0":
            break
        else:
            print("  ✗ 無效選項，請重新輸入。")


# ─────────────────────────────────────────────────────────────────────────────
# View all
# ─────────────────────────────────────────────────────────────────────────────

def _view_all(svc: ConfigService):
    print("\n【所有設定概覽】")
    _separator()
    print("▶ 相機設定")
    _camera_list(svc)
    _separator()
    print("▶ 車道設定")
    _lane_list(svc)
    _separator()
    print("▶ Lidar 設定")
    _lidar_list(svc)
    _separator()
    print("▶ 主機設定")
    _host_view(svc)


# ─────────────────────────────────────────────────────────────────────────────
# Main menu
# ─────────────────────────────────────────────────────────────────────────────

def main():
    config_path = os.path.abspath(_DEFAULT_CONFIG)
    svc = ConfigService(config_path)

    if not os.path.exists(config_path):
        print(f"⚠ 找不到設定檔: {config_path}")
        print("  請先確認 device_params.json 存在，或從範本複製。")
        sys.exit(1)

    svc.load_config()

    while True:
        _header()
        print()
        print("  1. 檢視所有設定")
        print("  2. 相機參數設定")
        print("  3. 車道資訊設定")
        print("  4. Lidar 偵測設定")
        print("  5. 主機參數設定")
        print("  6. 重新計算 Lidar 有效區")
        print("  7. 匯出設定 (JSON)")
        print("  8. 匯入設定 (JSON)")
        print("  0. 離開")
        print()
        choice = input("請選擇功能 [0-8]: ").strip()

        if choice == "1":
            _view_all(svc)
        elif choice == "2":
            menu_camera(svc)
        elif choice == "3":
            menu_lane(svc)
        elif choice == "4":
            menu_lidar(svc)
        elif choice == "5":
            menu_host(svc)
        elif choice == "6":
            updated = svc.recalculate_all_lidars()
            svc.save_config()
            if updated:
                print(f"  ✓ 已重新計算 Lidar: {', '.join(updated)}")
            else:
                print("  (無啟用自動計算的 Lidar)")
        elif choice == "7":
            path = _ask("請輸入匯出路徑 (例如 output/config_export.json)",
                        default="output/config_export.json")
            try:
                svc.export_config(path)
                print(f"  ✓ 已匯出至 {path}")
            except Exception as e:
                print(f"  ✗ 匯出失敗: {e}")
        elif choice == "8":
            path = _ask("請輸入匯入路徑")
            try:
                svc.import_config(path)
                svc.save_config()
                print(f"  ✓ 已匯入並存檔")
            except Exception as e:
                print(f"  ✗ 匯入失敗: {e}")
        elif choice == "0":
            print("  再見！")
            break
        else:
            print("  ✗ 無效選項，請重新輸入。")


if __name__ == "__main__":
    main()
