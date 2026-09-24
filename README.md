# Device Parameter Tool

一個從 `main` 重新設計與實作的設備參數工具，提供：
- **繁體中文 CLI**：管理 Camera / Lane / Lidar / Host 設定、快速設定、預覽計算、JSON 匯入匯出
- **簡易 Web UI**：表單編輯、即時預覽、UTF-8 備註欄位、Site History 載入歷史設定
- **可測試核心模組**：Lidar 有效偵測範圍計算邏輯、資料模型、驗證器、設定檔存讀

> `examples/verify_lidar_calculation.py` 會保留作為已驗證的獨立參考腳本；正式程式邏輯已抽出至 `device_parameter_tool/services/lidar_calculator.py`。

## 為什麼選 Flask？

本專案 Web UI 選用 **Flask**，原因是：
- 體積小、依賴少，適合這類內部工具
- 內建測試 client，方便用 `pytest` 驗證表單、歷史紀錄與 UTF-8 備註流程
- 不需要額外前端建置流程，能保持專案結構簡潔

## 專案結構

```text
Device_Parameter_Tool/
├── device_parameter_tool/
│   ├── core/cli.py                 # CLI 主程式
│   ├── models/device_config.py     # Camera / Lane / Lidar / Host / DeviceConfig
│   ├── services/config_service.py  # JSON 存讀、備份、Site History
│   ├── services/lidar_calculator.py# Lidar 核心公式與報表輸出
│   ├── utils/validators.py         # 驗證器
│   └── web/
│       ├── app.py                  # Flask app
│       └── templates/index.html    # Web UI
├── examples/verify_lidar_calculation.py
├── tests/
└── pyproject.toml
```

## 安裝

### macOS / Linux / PowerShell

```bash
python -m pip install -e '.[dev]'
```

### Windows CMD

```bat
python -m pip install -e ".[dev]"
```

> 說明：Windows `cmd.exe` 不會像 Bash / PowerShell 一樣處理單引號，若使用 `'.[dev]'`，pip 會把單引號一起當成路徑字串，導致安裝失敗。

## CLI 使用方式

```bash
device-parameter-cli
```

或：

```bash
python -m device_parameter_tool.core.cli
```

CLI 提供：
- 車道 CRUD
- Lidar CRUD（含負責車道、中心點距離、預覽有效偵測範圍）
- Camera / Host 編輯
- 設定檔讀取與儲存
- 快速設定流程

### 設定檔存檔/匯出

- 設定檔格式為 JSON
- 若目標檔案已存在，存檔時會自動備份為 `*.bak`

## Web UI 使用方式

```bash
device-parameter-web
```

或：

```bash
python -m device_parameter_tool.web.app
```

預設會在本機啟動 Flask 開發伺服器。

### Web UI 功能

- 表單輸入/編輯 Camera、Lane、Lidar、Host
- 使用同一套 `lidar_calculator` 邏輯即時預覽結果
- 支援 `note` 備註欄位，使用 UTF-8 儲存與顯示中文
- `Site History` 會保存每次儲存的設定與備註，可重新載入

### Web 表單格式

目前為簡潔設計：
- `Lanes` 文字區：每行 `lane_number,width_mm`
- `Lidars` 文字區：每行 `lane1[,lane2]:center_distance_mm`

例如：

```text
0,3500
1,3300
2,3200
```

```text
0,1:3600
2:7100
```

## Device Config 資料模型

`DeviceConfig` 可 `to_dict()` / `from_dict()`，適合匯入/匯出 JSON：

```json
{
  "site_name": "03F-040.7N",
  "note": "夜間測試點位",
  "camera": {
    "latitude": 25.1,
    "longitude": 121.6,
    "orientation_deg": 90.0,
    "ip": "192.168.0.10",
    "port": 554,
    "protocol": "rtsp"
  },
  "lanes": [
    {"lane_number": 0, "width_mm": 3500.0},
    {"lane_number": 1, "width_mm": 3300.0}
  ],
  "lidars": [
    {"assigned_lanes": [0, 1], "center_distance_mm": 3600.0}
  ],
  "host": {
    "ip": "192.168.0.20",
    "port": 8080,
    "log_level": "INFO"
  }
}
```

## Lidar 有效偵測範圍公式

本專案採用 `examples/verify_lidar_calculation.py` 已驗證的公式，**不使用舊的對稱式 `total_width/2 ± offset` 算法**。

### 計算原則

- 基準點：**內路肩護欄**
- 車道依 `lane_number` 排序
- 每個 Lidar 最多負責 2 個車道
- 對負責車道範圍求得：
  - `inner_boundary`
  - `outer_boundary`
- 若不是最內側/最外側邊界，需做 `500mm` 跨車道補償

### 公式

```text
scan_right = center_distance - inner_boundary + (0 if is_innermost else 500)
scan_left  = outer_boundary - center_distance + (0 if is_outermost else 500)
```

### 偏差值（offset）

偏差值為 `center_distance` 與以下值的差之絕對值：
- 此 Lidar **之前所有 Lidar 負責車道總寬**
- 若此 Lidar 負責 2 個車道，再加上 **本 Lidar 右側車道寬**

### 錯誤與警告

- 若 `scan_right` 或 `scan_left` 超過 `5500mm`，會顯示警告並建議拆分車道、增加 Lidar
- 若 `scan_right` 或 `scan_left` 為負值，視為設定錯誤

## 測試

```bash
pytest -q tests
```

目前測試覆蓋：
- `DeviceConfig` 序列化/反序列化
- validators
- `.bak` 備份存檔
- Lidar 核心公式（最內側 / 中間 / 最外側 / 500mm 補償 / 超限警告 / 負值錯誤）
- Web UI 的儲存、歷史紀錄、中文備註 round-trip
