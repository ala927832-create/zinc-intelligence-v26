# V2.6.2 Free-First Data Map

## 免費自動取得

| 欄位 | 免費來源 | 使用方式 / 限制 |
|---|---|---|
| LME Zinc Cash Bid/Offer | LME Zinc public Summary | 與 LME 頁面相同的公開延遲 Bid/Offer；不是即時 feed |
| LME Zinc 3M Bid/Offer | LME Zinc public Summary | 與 LME 頁面相同的公開延遲 Bid/Offer |
| LME Zinc 3M Closing | LME Zinc public Summary | 每次執行累積為 close-only 歷史 |
| Opening inventory | LME Zinc public Summary | 公開延遲資料 |
| Live warrants | LME Zinc public Summary | 公開延遲資料 |
| Cancelled warrants | LME Zinc public Summary | 公開延遲資料 |
| Cancelled ratio | 本地衍生 | Cancelled / Opening inventory |
| Zinc concentrate TC | SMM public Zinc page | 公開週度表格 fallback；需注意資料再發布授權 |
| Zinc ingot premium | SMM public Zinc page | 公開表格 fallback；需注意資料再發布授權 |
| Brent / Nat Gas / DXY / Copper / Aluminium proxy / USD-TWD / Silver | yfinance | 公開/延遲 proxy，不是 LME 官方資料 |

## 無法以「穩定、匿名、完全免費」方式取得同等品質資料

1. **真正的 LME Zinc 3M Daily OHLC 歷史 API**：LME 提供本年度 next-day delayed 免費資料，但歷史查看/下載需要 LME 帳號，沒有本專案可依賴的穩定匿名 OHLC API。
2. **LME 15m / 1H OHLC**：公開頁有至少 15 分鐘延遲的 intraday 資料，但沒有穩定匿名 OHLC feed 可供自動回測。
3. **Delivered in / delivered out**：Public Zinc Summary 不顯示；LME Stocks Breakdown 是每日兩日延遲 Excel，但網站下載/登入狀態可能影響自動抓取。
4. **可自由再發布的每日 physical premium 歷史**：SMM 公開值可作內部 fallback，但其資料有轉載/發布限制。
5. **Smelter utilization / global refined balance / China demand**：沒有單一穩定、每日、免費且品質等同商業資料商的來源，暫維持 optional/manual。

## Close-only 模式

若沒有完整 OHLC，系統不製造假 K 線。它會逐日保存 LME 公開 Summary 的真實 3M Closing，僅計算適用於收盤序列的 EMA / RSI / ROC。ATR、真實 candlestick、基於 High/Low 的停損校準與精確 MAE/MFE，仍必須等完整 OHLC。

## 使用與授權提醒

LME 與 SMM 都有市場資料授權/再發布條款。V2.6.2 會保留來源與狀態標籤。若 GitHub Pages 是公開網站，建議先確認原始行情數值的再發布權；更安全的生產架構仍是 Private Core + Public Derived Dashboard。
