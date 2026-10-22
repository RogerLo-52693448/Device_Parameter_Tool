# 電力計算

離線使用的 AC/DC 電力預算與配線圖工具。此應用程式獨立於 `examples/` 中既有的 Lidar 範例。

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
- 設備額定值按數量累加至所屬迴路，再累加至電源；電源及迴路各自檢查設定的電流與瓦特上限。
- 電壓必須大於零；容量上限（若有設定）必須大於零；設備類型及電壓必須符合連接的迴路。功率因數範圍為 `0 < PF ≤ 1`。

## 測試

```bash
python -m unittest discover -s tests
```