import os  # 導入作業系統模組
import sys  # 導入系統模組
import numpy as np  # 導入數值計算庫
import pandas as pd  # 導入數據分析庫
import yfinance as yf  # 導入金融行情介面
import matplotlib.pyplot as plt  # 導入繪圖庫

# 設定繁體中文字型
plt.rcParams['font.sans-serif'] = ['Hiragino Sans TC', 'PingFang HK', 'Hiragino Sans GB', 'Arial Unicode MS', 'DejaVu Sans', 'sans-serif']  # 設定中文字型
plt.rcParams['axes.unicode_minus'] = False  # 正常顯示負號

class AsianNightScalperDeepResearch:  # 定義亞洲夜間剝頭皮深度量化研究引擎
    def __init__(self):  # 初始化
        self.symbols = [  # 28 大主要與交叉貨幣對清單
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
            "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD",
            "GBPJPY", "GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD",
            "AUDJPY", "AUDCAD", "AUDNZD", "AUDCHF",
            "NZDCAD", "NZDJPY", "NZDCHF",
            "CADJPY", "CADCHF", "CHFJPY"
        ]  # 清單結束
        
        # 實盤平均點差 (Pips)
        self.spreads = {  # 點差表
            "EURUSD": 0.8, "USDJPY": 0.9, "GBPUSD": 1.0, "AUDUSD": 1.0, "USDCAD": 1.2, "USDCHF": 1.2, "NZDUSD": 1.2,
            "EURGBP": 1.3, "EURJPY": 1.3, "EURCHF": 1.5, "EURCAD": 1.8, "EURAUD": 2.0, "EURNZD": 2.5,
            "GBPJPY": 1.6, "GBPCAD": 2.2, "GBPCHF": 2.2, "GBPAUD": 2.5, "GBPNZD": 3.0,
            "AUDCAD": 1.5, "AUDNZD": 1.6, "AUDJPY": 1.5, "AUDCHF": 1.6,
            "NZDCAD": 1.8, "NZDJPY": 1.8, "NZDCHF": 1.8,
            "CADJPY": 1.5, "CADCHF": 1.8, "CHFJPY": 1.8
        }  # 結束

    def get_pip_size(self, symbol: str) -> float:  # 取得 pip 價格單位
        return 0.01 if "JPY" in symbol else 0.0001  # JPY 貨幣對 0.01, 其餘 0.0001

    def get_pip_val_usd(self, symbol: str, lot_size: float = 1.0) -> float:  # 取得每 pip 美金價值
        rates = {"USD": 1.0, "CAD": 1.0/1.37, "CHF": 1.0/0.88, "JPY": 1.0/148.0, "GBP": 1.30, "NZD": 0.60, "AUD": 0.66}  # 匯率表
        conv = rates.get(symbol[-3:], 1.0)  # 轉換係數
        return 100000.0 * self.get_pip_size(symbol) * conv * lot_size  # 回傳美金

    def fetch_data(self, symbol: str, tf_str: str, period_str: str) -> pd.DataFrame:  # 下載歷史數據
        ticker = f"{symbol}=X"  # 設定 yf 標的
        try:  # 嘗試下載
            df = yf.download(ticker, period=period_str, interval=tf_str, progress=False)  # 執行下載
            if df.empty: return pd.DataFrame()  # 空檢查
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)  # 展平欄位
            df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}).dropna()  # 整理欄位
            if df.index.tz is not None: df.index = pd.to_datetime(df.index).tz_localize(None)  # 去時區
            else: df.index = pd.to_datetime(df.index)  # 格式化
            return df[['open', 'high', 'low', 'close', 'volume']]  # 回傳有效欄位
        except Exception:  # 異常處理
            return pd.DataFrame()  # 空表

    def run_scalper_config(self, symbol: str, df_raw: pd.DataFrame, tf_name: str, 
                           start_hr: int, end_hr: int, tp_pips: float, sl_pips: float,
                           bb_period: int = 20, bb_dev: float = 2.2, rsi_period: int = 14) -> dict:  # 回測函數
        df = df_raw.copy()  # 複製表
        pip_size = self.get_pip_size(symbol)  # pip 單位
        pip_val = self.get_pip_val_usd(symbol, 1.0)  # 1 手美金
        sp_pips = self.spreads.get(symbol, 1.5)  # 該品種實盤點差
        sp_dist = sp_pips * pip_size  # 點差距離

        # 計算布林通道與 RSI
        df['MA'] = df['close'].rolling(bb_period).mean()  # 均線
        df['STD'] = df['close'].rolling(bb_period).std()  # 標準差
        df['UB'] = df['MA'] + bb_dev * df['STD']  # 上軌
        df['LB'] = df['MA'] - bb_dev * df['STD']  # 下軌
        
        delta = df['close'].diff()  # 差分
        gain = delta.where(delta > 0, 0).rolling(rsi_period).mean()  # 漲幅
        loss = (-delta.where(delta < 0, 0)).rolling(rsi_period).mean()  # 跌幅
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))  # RSI

        pos = 0  # 倉位
        entry_p = 0.0  # 進場價
        cum_pnl = 0.0  # 累計損益
        wins, losses = 0, 0  # 勝負次數
        win_usd, loss_usd = 0.0, 0.0  # 盈虧美金
        trades_pnl = []  # 交易盈虧列表
        equity_curve = [0.0]  # 權益曲線
        cost = 5.0  # 扣手續費 $5

        tp_dist = tp_pips * pip_size  # 止盈距離
        sl_dist = sl_pips * pip_size  # 停損距離

        for i in range(30, len(df)):  # 遍歷 K 棒
            c, h, l = float(df['close'].iloc[i]), float(df['high'].iloc[i]), float(df['low'].iloc[i])  # 取價
            hr = df.index[i].hour  # UTC 小時
            is_force_exit = (hr == 7)  # UTC 07:00 歐盤前強平

            if pos != 0:  # 持倉管理
                closed = False  # 平倉標記
                exit_p = 0.0  # 出場價

                if pos == 1:  # 多單 (Bid 賣出)
                    if h >= entry_p + tp_dist: exit_p = entry_p + tp_dist - sp_dist; closed = True  # 止盈
                    elif c >= df['MA'].iloc[i] and c > entry_p: exit_p = c - sp_dist; closed = True  # 獲利回歸中軌平倉
                    elif l <= entry_p - sl_dist: exit_p = entry_p - sl_dist - sp_dist; closed = True  # 停損
                    elif is_force_exit: exit_p = c - sp_dist; closed = True  # 強平

                    if closed:  # 結算
                        pips = (exit_p - entry_p) / pip_size  # 淨點數
                        pnl = pips * pip_val - cost  # 美金
                        cum_pnl += pnl  # 累計
                        if pnl > 0: wins += 1; win_usd += pnl  # 贏
                        else: losses += 1; loss_usd += abs(pnl)  # 輸
                        trades_pnl.append(pnl)  # 記錄
                        pos = 0  # 清倉

                elif pos == -1:  # 空單 (Ask 買回)
                    if l <= entry_p - tp_dist: exit_p = entry_p - tp_dist + sp_dist; closed = True  # 止盈
                    elif c <= df['MA'].iloc[i] and c < entry_p: exit_p = c + sp_dist; closed = True  # 獲利回歸中軌平倉
                    elif h >= entry_p + sl_dist: exit_p = entry_p + sl_dist + sp_dist; closed = True  # 停損
                    elif is_force_exit: exit_p = c + sp_dist; closed = True  # 強平

                    if closed:  # 結算
                        pips = (entry_p - exit_p) / pip_size  # 淨點數
                        pnl = pips * pip_val - cost  # 美金
                        cum_pnl += pnl  # 累計
                        if pnl > 0: wins += 1; win_usd += pnl  # 贏
                        else: losses += 1; loss_usd += abs(pnl)  # 輸
                        trades_pnl.append(pnl)  # 記錄
                        pos = 0  # 清倉

            # 開倉判定
            is_entry_hr = (hr >= start_hr or hr <= end_hr) if start_hr > end_hr else (start_hr <= hr <= end_hr)  # 時段
            if pos == 0 and is_entry_hr and not is_force_exit:  # 開倉
                if c <= df['LB'].iloc[i] and df['RSI'].iloc[i] <= 35: pos = 1; entry_p = c + sp_dist  # 買多 (Ask)
                elif c >= df['UB'].iloc[i] and df['RSI'].iloc[i] >= 65: pos = -1; entry_p = c  # 賣空 (Bid)

            equity_curve.append(cum_pnl)  # 記錄

        tot = wins + losses  # 總筆數
        win_rate = (wins / tot * 100) if tot > 0 else 0.0  # 勝率
        pf = (win_usd / (loss_usd + 1e-9)) if loss_usd > 0 else (99.0 if wins > 0 else 0.0)  # PF
        eq_ser = pd.Series(equity_curve)  # Series
        bal_ser = eq_ser + 100000.0  # 換算 $100k
        mdd = ((bal_ser - bal_ser.cummax()) / bal_ser.cummax() * 100).min()  # MDD

        # 計算平時資金曲線線性度 (R-squared of Equity Curve)
        if len(trades_pnl) > 5:  # 交易數足夠
            cum_trades = np.cumsum(trades_pnl)  # 交易累計
            x = np.arange(len(cum_trades))  # 步數
            slope, intercept = np.polyfit(x, cum_trades, 1)  # 線性回歸
            fit_line = slope * x + intercept  # 擬合線
            ss_res = np.sum((cum_trades - fit_line) ** 2)  # 殘差
            ss_tot = np.sum((cum_trades - np.mean(cum_trades)) ** 2) + 1e-9  # 總變異
            r2 = max(0.0, 1.0 - (ss_res / ss_tot))  # R2 線性度
        else:  # 樣本過少
            r2 = 0.0  # 設為 0

        # 計算最長連勝次數 (Max Consecutive Wins)
        max_streak = 0  # 初始化
        curr_streak = 0  # 當前連勝
        for p in trades_pnl:  # 遍歷
            if p > 0: curr_streak += 1; max_streak = max(max_streak, curr_streak)  # 連勝
            else: curr_streak = 0  # 中斷

        return {
            "Symbol": symbol, "Timeframe": tf_name, "Session": f"UTC {start_hr:02d}-{end_hr:02d}",
            "TP_SL": f"{tp_pips}/{sl_pips}p", "Spread": sp_pips,
            "Trades": tot, "WinRate": round(win_rate, 1), "Max_Streak": max_streak,
            "R2_Smoothness": round(r2, 2), "Profit": round(cum_pnl, 1),
            "PF": round(pf, 2), "MDD": round(mdd, 2), "Equity": eq_ser, "TradesPnL": trades_pnl
        }

    def run_exhaustive_study(self):  # 執行全矩陣研究
        print("=" * 90)  # 標頭
        print("  🔬 亞洲夜間剝頭皮 (Asian Night Scalper) 全品種 × 多週期 × 參數極致勝率深度研究  ")  # 標題
        print("=" * 90 + "\n")  # 標頭

        # 探索的週期與參數組合
        test_matrix = [  # 測試矩陣
            # 1. M5 週期探索 (傳統超短線)
            {"tf": "M5", "yf_tf": "5m", "period": "60d", "start": 0, "end": 5, "tp": 6.0, "sl": 35.0},   # M5 避開換匯
            {"tf": "M5", "yf_tf": "5m", "period": "60d", "start": 22, "end": 5, "tp": 8.0, "sl": 40.0},  # M5 擴大空間
            # 2. M15 週期探索 (黃金過渡週期)
            {"tf": "M15", "yf_tf": "15m", "period": "60d", "start": 0, "end": 5, "tp": 10.0, "sl": 30.0}, # M15 標準
            {"tf": "M15", "yf_tf": "15m", "period": "60d", "start": 23, "end": 6, "tp": 12.0, "sl": 35.0}, # M15 寬時段
            {"tf": "M15", "yf_tf": "15m", "period": "60d", "start": 0, "end": 5, "tp": 15.0, "sl": 35.0}, # M15 大止盈
            # 3. M30 週期探索 (穩健震盪週期)
            {"tf": "M30", "yf_tf": "30m", "period": "60d", "start": 0, "end": 6, "tp": 15.0, "sl": 40.0}, # M30 標準
            {"tf": "M30", "yf_tf": "30m", "period": "60d", "start": 22, "end": 6, "tp": 20.0, "sl": 50.0}, # M30 寬幅
            # 4. H1 週期探索 (大空間震盪)
            {"tf": "H1", "yf_tf": "1h", "period": "730d", "start": 21, "end": 6, "tp": 25.0, "sl": 60.0}  # H1 跨日
        ]  # 矩陣結束

        all_results = []  # 儲存指標
        equity_dict = {}  # 儲存曲線

        for sym in self.symbols:  # 遍歷 28 大品種
            print(f"[*] 正在分析商品: [{sym:6s}] ...", end="", flush=True)  # 日誌
            # 緩存下載各週期數據
            data_cache = {}  # 數據快取
            for cfg in test_matrix:  # 遍歷配置
                k = (cfg["yf_tf"], cfg["period"])  # 鍵名
                if k not in data_cache:  # 未下載
                    data_cache[k] = self.fetch_data(sym, cfg["yf_tf"], cfg["period"])  # 下載

            for cfg in test_matrix:  # 遍歷測試
                df = data_cache.get((cfg["yf_tf"], cfg["period"]))  # 取得數據
                if df is None or df.empty or len(df) < 100: continue  # 檢查

                res = self.run_scalper_config(  # 回測
                    symbol=sym, df_raw=df, tf_name=cfg["tf"],
                    start_hr=cfg["start"], end_hr=cfg["end"],
                    tp_pips=cfg["tp"], sl_pips=cfg["sl"]
                )
                if res["Trades"] >= 15:  # 過濾樣本過少
                    all_results.append(res)  # 記錄
                    equity_dict[f"{sym}_{cfg['tf']}_{res['TP_SL']}_{res['Session']}"] = res["Equity"]  # 存曲線

            print(" 完成!")  # 完成

        df_all = pd.DataFrame(all_results)  # 轉 DataFrame
        df_clean = df_all.drop(columns=['Equity', 'TradesPnL'])  # 清理
        df_clean.to_csv("asian_scalper_deep_research.csv", index=False)  # 存檔

        # 排序：以「極致勝率 (WinRate >= 75%) + 曲線平穩度 (R2 >= 0.70) + 總利潤」排序
        df_high_wr = df_clean[df_clean["WinRate"] >= 70.0].sort_values(by=["WinRate", "R2_Smoothness", "Profit"], ascending=[False, False, False])  # 篩選
        
        print("\n" + "=" * 105)  # 標頭
        print("       🏆 亞洲夜間剝頭皮【極致勝率 & 平時階梯式平穩向上 Top 15 組合榜】 (已扣真實點差與手續費)       ")  # 標題
        print("=" * 105)  # 標頭
        print(df_high_wr.head(15).to_string(index=False))  # 輸出
        print("=" * 105 + "\n")  # 結尾

        # 繪製 Top 6 極致勝率與階梯式向上曲線圖
        self.plot_top_curves(df_high_wr.head(6), equity_dict)  # 繪圖

    def plot_top_curves(self, df_top: pd.DataFrame, equity_dict: dict):  # 繪圖函數
        if df_top.empty: return  # 檢查
        fig, axes = plt.subplots(3, 2, figsize=(18, 14), sharex=False)  # 3x2 子圖
        fig.patch.set_facecolor('#0d1117')  # 畫布背景色
        axes_flat = axes.flatten()  # 展平
        colors = ["#3fb950", "#58a6ff", "#d2a8ff", "#00e676", "#f0883e", "#79c0ff"]  # 配色

        for idx, (_, row) in enumerate(df_top.iterrows()):  # 遍歷
            ax = axes_flat[idx]  # 子圖
            ax.set_facecolor('#161b22')  # 背景色
            key = f"{row['Symbol']}_{row['Timeframe']}_{row['TP_SL']}_{row['Session']}"  # 鍵名
            if key in equity_dict:  # 若曲線存在
                eq = equity_dict[key]  # 取得曲線
                c = colors[idx % len(colors)]  # 顏色
                ax.plot(eq.values, color=c, linewidth=2.4, label=f"{row['Symbol']} [{row['Timeframe']}]")  # 畫線
                ax.fill_between(range(len(eq)), eq.values, 0, color=c, alpha=0.15)  # 填充
                ax.axhline(0, color='#8b949e', linestyle='--', linewidth=1.0, alpha=0.6)  # 基準線

                ax.set_title(f"Rank {idx+1}: {row['Symbol']} [{row['Timeframe']}] ({row['Session']}) - 勝率: {row['WinRate']}% | 純利: +${row['Profit']:,.1f}", fontsize=12.0, fontweight='bold', color='#f0f6fc')  # 標題
                ax.set_ylabel('實質損益 ($)', fontsize=10.5, color='#8b949e')  # Y 軸
                ax.grid(True, linestyle=':', alpha=0.25, color='#30363d')  # 網格

                info = (  # 資訊方塊
                    f"品種: {row['Symbol']} ({row['Timeframe']})\n"
                    f"時段: {row['Session']} (Zero-Overnight)\n"
                    f"止盈/停損: {row['TP_SL']}\n"
                    f"勝率: {row['WinRate']}%\n"
                    f"最大連勝: {row['Max_Streak']} 連勝\n"
                    f"平時階梯線性度 (R²): {row['R2_Smoothness']}\n"
                    f"獲利因子 (PF): {row['PF']}\n"
                    f"已扣實盤點差: {row['Spread']} pips"
                )
                ax.text(0.03, 0.93, info, transform=ax.transAxes, fontsize=9.5,
                        verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', facecolor='#21262d', edgecolor=c, alpha=0.85), color='#f0f6fc')  # 資訊框
                ax.tick_params(colors='#8b949e', labelsize=9)  # 刻度
                ax.set_xlabel("K 線步數", fontsize=9.5, color='#8b949e')  # X 軸

        plt.tight_layout()  # 自動排版
        chart_file = "asian_scalper_best_smooth_curves.png"  # 檔名
        plt.savefig(chart_file, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')  # 存檔
        print(f"[+] 亞洲夜間極致勝率平穩階梯圖已輸出至: {chart_file}")  # 日誌

if __name__ == "__main__":  # 主入口
    research = AsianNightScalperDeepResearch()  # 實例化
    research.run_exhaustive_study()  # 啟動全矩陣深度研究
