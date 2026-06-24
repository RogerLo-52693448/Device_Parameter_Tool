# Device_Parameter_Tool

影像設備參數與主機細部參數調整工具 — 採用 CLI 互動式介面，方便調整相機、車道、Lidar 偵測設定與主機細部參數。

## 功能簡介

| 模組 | 說明 |
|------|------|
| **相機參數** | 紀錄經緯度、方向角度、解析度、FPS、RTSP URL 等設定 |
| **車道資訊** | 定義車道寬度，自動計算 Lidar 有效區 |
| **Lidar 偵測** | 設定負責車道、偏差距離、中心點距離、左右有效區 |
| **主機參數** | MQTT、RTSP 傳輸、儲存路徑、日誌等細部設定 |

## 專案架構

```
Device_Parameter_Tool/
├── AIAgent_init.md
├── README.md
├── .gitignore
├── requirements.txt
├── src/
│   ├── main/
│   │   ├── python/
│   │   │   ├── core/          # CLI 工具
│   │   │   │   └── config_cli.py
│   │   │   ├── utils/         # 驗證器
│   │   │   │   └── validators.py
│   │   │   ├── models/        # 資料模型
│   │   │   │   └── device_config.py
│   │   │   ├── services/      # 服務層
│   │   │   │   └── config_service.py
│   │   │   └── api/           # 未來 Web GUI
│   │   └── resources/
│   │       └── config/
│   │           └── device_params.json
│   └── test/
│       └── unit/
│           ├── test_config_service.py
│           └── test_validators.py
├── docs/
├── examples/
└── output/
```

## 快速開始

### 安裝依賴

```bash
pip install -r requirements.txt
```

### 執行 CLI 工具

```bash
python -m src.main.python.core.config_cli
```

### 執行測試

```bash
python -m pytest src/test/
```

## CLI 選單

```
╔══════════════════════════════════════════╗
║       設備參數調整工具 v1.0              ║
╚══════════════════════════════════════════╝

  1. 檢視所有設定
  2. 相機參數設定
  3. 車道資訊設定
  4. Lidar 偵測設定
  5. 主機參數設定
  6. 重新計算 Lidar 有效區
  7. 匯出設定 (JSON)
  8. 匯入設定 (JSON)
  0. 離開
```

## Lidar 有效區自動計算

```
總覆蓋寬度 = sum(各負責車道的寬度)
effective_left  = (總覆蓋寬度 / 2) + offset_distance
effective_right = (總覆蓋寬度 / 2) - offset_distance
```

`offset_distance` 正值表示 Lidar 偏右，負值表示偏左。

## 設定檔說明

預設設定檔位於 `src/main/resources/config/device_params.json`，修改前會自動備份為 `.bak`。

## 未來規劃 (Web GUI)

待 CLI 功能完善後，將透過 FastAPI + HTML 提供 Web 介面：
- `src/main/python/api/` — REST API 端點
- `src/main/resources/assets/` — 靜態前端資源
