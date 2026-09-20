# 訂單管理系統(Vibe Coding 課堂參考實作)

淡江大學「AI 與商業數據班」單元 12–13 的完整參考解答。

## 本機執行

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python init_db.py                # 建立 orders.db 與測試資料
python app.py                    # 開啟 http://127.0.0.1:8899
```

管理後台:`admin` / `tkucsa1234`(密碼以雜湊儲存於資料庫)

## 資料表設計

| 資料表 | 說明 | 關聯 |
|---|---|---|
| `customer` | 客戶主檔,一位客戶一列 | — |
| `product` | 商品主檔,含目前售價與庫存 | — |
| `orders` | 訂單主檔 | `customer_id` FK → 客戶 **一對多** 訂單 |
| `order_item` | 訂單明細(中間表) | `(order_id, product_id)` 複合主鍵 → 訂單 **多對多** 商品 |

`order_item.unit_price` 保存**下單當時**的單價,商品改價不會竄改歷史訂單金額。

## 自動測試

```bash
pytest -v
```

## CI/CD

`.github/workflows/ci-cd.yml`:push 到 `main` → 跑 `pytest` → 測試通過才觸發 Render 部署。
需在 GitHub repo 的 Settings → Secrets → Actions 設定 `RENDER_DEPLOY_HOOK`。
