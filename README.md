# 110V 電源計算

離線使用的 110 V AC 設備負載計算工具。此應用程式獨立於 `examples/` 中既有的 Lidar 範例。

## 安裝與啟動

需要 Python 3.12 以上版本。首次安裝時（需先取得 Flask 套件）：

```bash
python -m pip install .
```

安裝完成後可離線啟動，不會呼叫外部服務或載入遠端資源：

```bash
python -m power_budget
```

瀏覽器開啟 <http://127.0.0.1:5000/>。服務預設只監聽本機回環位址。也可執行 `python app.py` 啟動。

設定預設儲存在 `instance/power_budget.json`，首次啟動會載入 AC/DC 範例。可透過 `POWER_BUDGET_DATA` 環境變數指定其他本機 JSON 檔案位置。介面可新增、編輯、刪除電源、迴路及設備，並匯入或匯出含 `schema_version` 的 UTF-8 JSON。

## 計算

- DC：`W = V × A`、`A = W ÷ V`。
- AC 單相：`VA = V × A`、`W = VA × PF`；輸入實功率時以 `A = W ÷ (V × PF)` 換算。
- 使用固定 110 V AC 供電；輸入設備電壓、電流及數量，設備電壓需為 110 V。
- 設備總電流為各設備電流乘數量後加總；`VA = 110 V × 總 A`。
- 顯示的 W 以 PF=1 估算，僅供簡易參考；功率因數未知時，實際耗電 W 不一定等於 VA。
- 本工具不設定或判斷廠商提供的電源容量，也不估算 380 V 轉換損耗。

## 測試

```bash
python -m unittest discover -s tests
```