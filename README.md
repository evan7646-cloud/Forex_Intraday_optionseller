# ⚡ 5m 純日內雙策略 × 8 大模組量化極限收租監控儀表板

> **5-Minute (5m) Pure Intraday Option Seller & Scalper Interactive Dashboard with Hourly Automated Updates**  
> 專為純日內、零隔夜（Zero-Overnight）、極低持倉時長設計的高頻外匯量化收租監控系統。

---

## 🌟 系統亮點與功能特點

1. **雙策略 8 大模組全天候天然時間對沖**：
   - 🌙 **策略一：5m 亞洲夜間極限收租 (Asian Night Scalper)**（UTC 21:00 ～ 06:00 進場，**每日 UTC 07:00 強制清倉**）：標的包含 `NZDCAD`, `AUDNZD`, `AUDCAD`, `EURGBP`。
   - ⚡ **策略二：5m 合成選擇權跨式賣方 (Synthetic Short Straddle)**（UTC 07:00 ～ 20:00 進場，**每日 UTC 21:00 強制清倉**）：標的包含 `EURCHF`, `EURGBP`, `EURUSD`, `EURJPY`。
2. **多商品動態勾選過濾與即時 KPI 重算**：
   - 支援在網頁上任意勾選/取消不同貨幣對或策略，儀表板將**即時動態重新精算總淨利、勝率、獲利因子 PF、最大回撤 MDD 與資金權益曲線**。
3. **Plotly.js 互動視覺化圖表**：
   - 📈 **組合資金權益曲線 (Combined Equity)**：根據勾選商品即時聚合繪製 $100k 本金累計成長曲線。
   - 📊 **多標的個別曲線對比 (Comparative Equity)**：各貨幣對獨立資金曲線霓虹配色對比。
   - 🕯️ **5m K 線與進出場訊號圖**：高解析 5m K 線、布林通道 (2.2σ)、RSI(14)、Z-Score，並標註所有歷史進出場買賣三角形與止盈/停損圓點。
   - 📉 **歷史回撤深度圖 (Underwater Drawdown)**。
4. **歷史交易明細表與 CSV 下載**：
   - 提供搜尋、多條件篩選（方向、勝負、標的）、分頁導航，點擊任一交易列可自動定位跳轉至 K 線圖對應標記。
5. **GitHub Actions 每小時自動更新**：
   - 平日外匯市場開盤期間每小時由 GitHub Actions 自動抓取最新 5m 報價、更新交易結算狀態並自動部署至 GitHub Pages。

---

## 🚀 如何部署至您的 GitHub Repository 與啟用 GitHub Pages

### 步驟 1：建立 GitHub 遠端倉庫並推送程式碼

在終端機（Terminal）執行以下指令：

```bash
# 1. 初始化 Git 倉庫
git init

# 2. 加入所有檔案
git add .

# 3. 提交變更
git commit -m "🚀 Initial commit: 5m Scalper & Straddle Dashboard"

# 4. 設定 main 主分支
git branch -M main

# 5. 連接至您的 GitHub 倉庫 (請替換為您的倉庫網址)
git remote add origin https://github.com/您的用戶名/FundedNext_5m_scalping.git

# 6. 推送至 GitHub
git push -u origin main
```

---

### 步驟 2：啟用 GitHub Pages 靜態網頁託管

1. 開啟您的 GitHub 倉庫頁面，點擊上方 **`Settings`**。
2. 在左側選單中點擊 **`Pages`**。
3. 在 **Build and deployment** 下方的 **Source** 選擇 **`Deploy from a branch`**。
4. Branch 選擇 **`main`**，資料夾選擇 **`/(root)`**，並點擊 **`Save`**。
5. 稍等 1～2 分鐘，您的網頁將於 `https://您的用戶名.github.io/FundedNext_5m_scalping/` 正式上線！

---

### 步驟 3：開啟 GitHub Actions 寫入權限 (重要：防止自動更新 403 錯誤)

為確保每小時定時更新工作流能夠自動提交最新的 `strategy_results.json`：

1. 在倉庫頁面點擊 **`Settings`** -> **`Actions`** -> **`General`**。
2. 滾動至最下方的 **Workflow permissions**。
3. 將權限由預設的 *Read repository contents permission* 改選為 **`Read and write permissions`**。
4. 勾選 **`Allow GitHub Actions to create and approve pull requests`**。
5. 點擊 **`Save`** 儲存設定。

---

## 📁 檔案結構說明

```text
├── index.html                           # 現代暗黑玻璃擬態儀表板首頁
├── styles.css                           # TradingView 風格深邃深黑 CSS 樣式表
├── app.js                               # 前端多商品動態重算、Plotly 圖表與表格邏輯
├── update_strategy_data.py              # 後端 5m 數據下載、策略精算與 JSON 封包引擎
├── pure_intraday_5m_comparison_engine.py# 純日內 5m 策略原始回測與圖表生成引擎
├── OPTION_SELLER_5M_STRATEGY_GUIDE.md   # 5m 純日內雙策略完整規格說明書
├── requirements.txt                     # Python 依賴套件清單
├── strategy_results.json                # 策略即時運算結果與 K 線圖表數據 (自動產生)
├── all_trades_history.csv               # 完整歷史交易明細 CSV (自動產生)
└── .github/
    └── workflows/
        └── update_data.yml              # GitHub Actions 每小時定時自動化更新工作流
```
