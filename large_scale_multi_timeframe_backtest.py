import os  # 導入作業系統模組
import sys  # 導入系統模組
import time  # 導入時間模組
import signal  # 導入信號處理模組
import datetime  # 導入日期時間模組
import numpy as np  # 導入數值運算庫
import pandas as pd  # 導入數據表格處理庫
import matplotlib.pyplot as plt  # 導入專業繪圖庫
from tvDatafeed import TvDatafeed, Interval  # 導入 TradingView 數據介面
import yfinance as yf  # 導入 Yahoo Finance 備援介面

def _timeout_handler(signum, frame):  # 定義超時例外處理器
    raise TimeoutError("請求超時 (20 秒)")  # 拋出超時異常

class LargeScaleMultiTFBacktestEngine:  # 定義大規模多週期全品種量化回測引擎
    def __init__(self):  # 初始化
        self.tv = None  # 延遲初始化連線物件
        # 28 款主要與交叉外匯全幣別清單
        self.symbols = [
            "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "USDJPY",
            "EURGBP", "EURJPY", "EURAUD", "EURNZD", "EURCAD", "EURCHF",
            "GBPJPY", "GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD",
            "AUDCAD", "AUDNZD", "AUDJPY", "AUDCHF",
            "NZDCAD", "NZDJPY", "NZDCHF",
            "CADJPY", "CADCHF", "CHFJPY"
        ]
        # 4 大回測時間週期
        self.timeframes = {
            "M5":  {"tv": Interval.in_5_minute,  "yf": "5m",  "bars": 5000, "tp_pips": 5.0,  "sl_pips": 35.0},
            "M15": {"tv": Interval.in_15_minute, "yf": "15m", "bars": 5000, "tp_pips": 10.0, "sl_pips": 50.0},
            "M30": {"tv": Interval.in_30_minute, "yf": "30m", "bars": 5000, "tp_pips": 15.0, "sl_pips": 70.0},
            "H1":  {"tv": Interval.in_1_hour,    "yf": "1h",  "bars": 5000, "tp_pips": 25.0, "sl_pips": 100.0}
        }

    def _get_tv(self):  # 安全建立 TradingView 連線
        if self.tv is None:  # 尚未建立
            try:  # 嘗試連線
                signal.signal(signal.SIGALRM, _timeout_handler)  # 設定信號
                signal.alarm(10)  # 10 秒超時
                self.tv = TvDatafeed()  # 建立客戶端
                signal.alarm(0)  # 取消計時器
            except Exception as e:  # 捕捉異常
                signal.alarm(0)  # 取消計時
                print(f"[!] TvDatafeed 連線失敗: {e}")  # 輸出錯誤
                self.tv = None  # 設為 None
        return self.tv  # 回傳物件

    def get_pip_size(self, symbol: str) -> float:  # 取得 1 pip 價格單位
        return 0.01 if "JPY" in symbol else 0.0001  # JPY 貨幣對為 0.01, 其餘為 0.0001

    def get_pip_value_usd(self, symbol: str, lot_size: float = 1.0) -> float:  # 精確計算每 pip 在 USD 的真實價值
        quote_rates = {  # 報價幣對美金匯率對照表
            "USD": 1.0,          # USD 計價: $10.00 / pip
            "CAD": 1.0 / 1.37,   # CAD 計價: $7.30 / pip
            "CHF": 1.0 / 0.88,   # CHF 計價: $11.36 / pip
            "JPY": 1.0 / 148.0,  # JPY 計價: $6.76 / pip (1000 JPY / 148)
            "GBP": 1.30,         # GBP 計價: $13.00 / pip
            "NZD": 0.60,         # NZD 計價: $6.00 / pip
            "AUD": 0.66          # AUD 計價: $6.60 / pip
        }
        quote_curr = symbol[-3:]  # 取後三碼計價幣別
        conversion = quote_rates.get(quote_curr, 1.0)  # 取得匯率轉換係數
        base_pip = 100000.0 * self.get_pip_size(symbol)  # 1 手 1 pip 在計價幣金額
        return base_pip * conversion * lot_size  # 回傳每 pip 美金價值

    def fetch_data(self, symbol: str, tf_key: str) -> pd.DataFrame:  # 抓取指定標的與週期的數據
        tf_cfg = self.timeframes[tf_key]  # 取得週期配置
        n_bars = tf_cfg["bars"]  # 目標 K 棒數
        df = None  # 初始化資料表
        tv = self._get_tv()  # 取得連線
        
        if tv is not None:  # 若連線可用
            try:  # 嘗試 TradingView
                signal.signal(signal.SIGALRM, _timeout_handler)  # 設定信號
                signal.alarm(15)  # 15 秒超時
                df = tv.get_hist(symbol=symbol, exchange="OANDA", interval=tf_cfg["tv"], n_bars=n_bars)  # 抓取
                signal.alarm(0)  # 取消計時
            except Exception:  # 忽略例外
                signal.alarm(0)  # 取消計時
                df = None  # 重設為 None

        if df is not None and len(df) > 100:  # 驗證數據
            df = df.reset_index()  # 重設索引
            df['datetime'] = pd.to_datetime(df['datetime']).dt.tz_localize(None) - pd.Timedelta(hours=8)  # 校準為 UTC 時間
            df.set_index('datetime', inplace=True)  # 設為索引
            return df[['open', 'high', 'low', 'close', 'volume']][~df.index.duplicated(keep='first')]  # 回傳去重表

        # Yahoo Finance 備援下載
        ticker = f"{symbol}=X"  # 設定 yf 標的代碼
        try:  # 嘗試 yf 下載
            period_str = "60d" if tf_key in ["M5", "M15", "M30"] else "730d"  # 設定天數
            df_yf = yf.download(ticker, period=period_str, interval=tf_cfg["yf"], progress=False)  # 下載
            if isinstance(df_yf.columns, pd.MultiIndex): df_yf.columns = df_yf.columns.get_level_values(0)  # 展平欄位
            df_yf = df_yf.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})  # 統一名稱
            if df_yf.index.tz is not None: df_yf.index = pd.to_datetime(df_yf.index).tz_localize(None)  # 去時區
            else: df_yf.index = pd.to_datetime(df_yf.index)  # 格式化
            return df_yf[['open', 'high', 'low', 'close', 'volume']].dropna()  # 回傳清理後數據
        except Exception:  # 異常處理
            return pd.DataFrame()  # 回傳空表

    def run_scalper(self, symbol: str, tf_key: str, df_raw: pd.DataFrame, lot_size: float = 1.0) -> dict:  # 策略 1: Asian Night Scalper (真實結算)
        df = df_raw.copy()  # 複製表
        df['MA'] = df['close'].rolling(20).mean()  # 20 週期均線
        df['STD'] = df['close'].rolling(20).std()  # 20 週期標準差
        df['UB'] = df['MA'] + 2.2 * df['STD']  # 上軌 (2.2σ)
        df['LB'] = df['MA'] - 2.2 * df['STD']  # 下軌 (2.2σ)
        
        delta = df['close'].diff()  # 價差
        gain = delta.where(delta > 0, 0).rolling(14).mean()  # 漲幅
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()  # 跌幅
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))  # RSI
        
        # 亞盤夜間時段 (UTC 21:00 ~ 06:00)
        is_night = (df.index.hour >= 21) | (df.index.hour <= 6)  # 夜間開倉時段
        pos = 0  # 倉位
        entry_p = 0.0  # 進場價
        cum_pnl = 0.0  # 累積淨利
        wins, losses = 0, 0  # 勝負次數
        win_usd, loss_usd = 0.0, 0.0  # 盈虧美金
        cost = 5.0 * lot_size  # 手續費
        pip_size = self.get_pip_size(symbol)  # pip 單位
        pip_val = self.get_pip_value_usd(symbol, lot_size)  # pip 美金價值
        tp_dist = self.timeframes[tf_key]["tp_pips"] * pip_size  # 止盈距離
        sl_dist = self.timeframes[tf_key]["sl_pips"] * pip_size  # 停損距離
        equity_curve = [0.0]  # 權益曲線 ($0 起計)
        trades_list = []  # 交易記錄

        for i in range(30, len(df)):  # 遍歷 K 棒
            c, h, l = float(df['close'].iloc[i]), float(df['high'].iloc[i]), float(df['low'].iloc[i])  # 價格
            hr = df.index[i].hour  # 當前 UTC 小時
            is_force = (hr == 7)  # UTC 07:00 強制清倉

            if pos != 0:  # 持倉管理
                exit_p = 0.0  # 出場價
                is_closed = False  # 平倉標記

                if pos == 1:  # 多單
                    if h >= entry_p + tp_dist: exit_p = entry_p + tp_dist; is_closed = True  # TP 止盈
                    elif c >= df['MA'].iloc[i]: exit_p = c; is_closed = True  # 中軌平倉
                    elif l <= entry_p - sl_dist: exit_p = entry_p - sl_dist; is_closed = True  # 硬停損
                    elif is_force: exit_p = c; is_closed = True  # 時間強平
                    
                    if is_closed:  # 執行真實結算
                        pips = (exit_p - entry_p) / pip_size  # 點數
                        pnl = pips * pip_val - cost  # 淨損益
                        cum_pnl += pnl  # 更新
                        if pnl > 0: wins += 1; win_usd += pnl  # 獲利
                        else: losses += 1; loss_usd += abs(pnl)  # 虧損
                        trades_list.append(pnl)  # 記錄
                        pos = 0  # 空手

                elif pos == -1:  # 空單
                    if l <= entry_p - tp_dist: exit_p = entry_p - tp_dist; is_closed = True  # TP 止盈
                    elif c <= df['MA'].iloc[i]: exit_p = c; is_closed = True  # 中軌平倉
                    elif h >= entry_p + sl_dist: exit_p = entry_p + sl_dist; is_closed = True  # 硬停損
                    elif is_force: exit_p = c; is_closed = True  # 時間強平
                    
                    if is_closed:  # 執行真實結算
                        pips = (entry_p - exit_p) / pip_size  # 點數
                        pnl = pips * pip_val - cost  # 淨損益
                        cum_pnl += pnl  # 更新
                        if pnl > 0: wins += 1; win_usd += pnl  # 獲利
                        else: losses += 1; loss_usd += abs(pnl)  # 虧損
                        trades_list.append(pnl)  # 記錄
                        pos = 0  # 空手

            if pos == 0 and is_night[i] and not is_force:  # 開倉訊號
                if c <= df['LB'].iloc[i] and df['RSI'].iloc[i] <= 35: pos, entry_p = 1, c  # 買多
                elif c >= df['UB'].iloc[i] and df['RSI'].iloc[i] >= 65: pos, entry_p = -1, c  # 賣空

            equity_curve.append(cum_pnl)  # 記錄累積損益

        tot = wins + losses  # 總筆數
        win_rate = (wins / tot * 100) if tot > 0 else 0.0  # 勝率
        pf = (win_usd / (loss_usd + 1e-9)) if loss_usd > 0 else (99.0 if wins > 0 else 0.0)  # 獲利因子
        eq_ser = pd.Series(equity_curve)  # Series
        bal_ser = eq_ser + 100000.0  # 換算 $100k
        mdd = ((bal_ser - bal_ser.cummax()) / bal_ser.cummax() * 100).min()  # 最大回撤
        ev = (cum_pnl / tot) if tot > 0 else 0.0  # 每筆期望值
        sharpe = (np.mean(trades_list) / (np.std(trades_list) + 1e-9) * np.sqrt(len(trades_list))) if len(trades_list) > 1 else 0.0  # 夏普評分
        
        return {
            "Symbol": symbol, "Timeframe": tf_key, "Strategy": "Asian Scalper",
            "Trades": tot, "WinRate": round(win_rate, 1), "Profit": round(cum_pnl, 1),
            "PF": round(pf, 2), "MDD": round(mdd, 2), "EV": round(ev, 2), "Sharpe": round(sharpe, 2),
            "Equity": eq_ser
        }

    def run_straddle(self, symbol: str, tf_key: str, df_raw: pd.DataFrame, lot_size: float = 1.0) -> dict:  # 策略 2: Synthetic Short Straddle (真實結算)
        df = df_raw.copy()  # 複製表
        df['MA'] = df['close'].rolling(30).mean()  # 均值
        df['STD'] = df['close'].rolling(30).std()  # 標準差
        df['Z'] = (df['close'] - df['MA']) / (df['STD'] + 1e-9)  # Z 值

        pos = 0  # 倉位
        entry_p = 0.0  # 進場價
        cum_pnl = 0.0  # 累積損益
        wins, losses = 0, 0  # 勝負
        win_usd, loss_usd = 0.0, 0.0  # 盈虧美金
        cost = 5.0 * lot_size  # 手續費
        pip_size = self.get_pip_size(symbol)  # pip 單位
        pip_val = self.get_pip_value_usd(symbol, lot_size)  # pip 美金價值
        tp_dist = self.timeframes[tf_key]["tp_pips"] * pip_size  # 止盈距離
        sl_dist = self.timeframes[tf_key]["sl_pips"] * pip_size  # 停損距離
        equity_curve = [0.0]  # 權益曲線 ($0 起計)
        trades_list = []  # 交易記錄

        for i in range(35, len(df)):  # 遍歷 K 棒
            c, h, l = float(df['close'].iloc[i]), float(df['high'].iloc[i]), float(df['low'].iloc[i])  # 價格
            z = float(df['Z'].iloc[i])  # Z 值
            hr = df.index[i].hour  # 小時 (UTC)
            is_force = (hr == 21)  # UTC 21:00 強平

            if pos != 0:  # 持倉管理
                exit_p = 0.0  # 出場價
                is_closed = False  # 平倉標記

                if pos == 1:  # 多單
                    if z >= -0.2: exit_p = c; is_closed = True  # 均值回歸
                    elif h >= entry_p + tp_dist: exit_p = entry_p + tp_dist; is_closed = True  # TP 止盈
                    elif z <= -3.8: exit_p = c; is_closed = True  # Z 停損
                    elif l <= entry_p - sl_dist: exit_p = entry_p - sl_dist; is_closed = True  # 硬停損
                    elif is_force: exit_p = c; is_closed = True  # 時間強平
                    
                    if is_closed:  # 執行真實結算
                        pips = (exit_p - entry_p) / pip_size  # 點數
                        pnl = pips * pip_val - cost  # 淨損益
                        cum_pnl += pnl  # 更新
                        if pnl > 0: wins += 1; win_usd += pnl  # 獲利
                        else: losses += 1; loss_usd += abs(pnl)  # 虧損
                        trades_list.append(pnl)  # 記錄
                        pos = 0  # 空手

                elif pos == -1:  # 空單
                    if z <= 0.2: exit_p = c; is_closed = True  # 均值回歸
                    elif l <= entry_p - tp_dist: exit_p = entry_p - tp_dist; is_closed = True  # TP 止盈
                    elif z >= 3.8: exit_p = c; is_closed = True  # Z 停損
                    elif h >= entry_p + sl_dist: exit_p = entry_p + sl_dist; is_closed = True  # 硬停損
                    elif is_force: exit_p = c; is_closed = True  # 時間強平
                    
                    if is_closed:  # 執行真實結算
                        pips = (entry_p - exit_p) / pip_size  # 點數
                        pnl = pips * pip_val - cost  # 淨損益
                        cum_pnl += pnl  # 更新
                        if pnl > 0: wins += 1; win_usd += pnl  # 獲利
                        else: losses += 1; loss_usd += abs(pnl)  # 虧損
                        trades_list.append(pnl)  # 記錄
                        pos = 0  # 空手

            if pos == 0 and (7 <= hr <= 20) and not is_force:  # 開倉訊號
                if z <= -2.1: pos, entry_p = 1, c  # 買多
                elif z >= 2.1: pos, entry_p = -1, c  # 賣空

            equity_curve.append(cum_pnl)  # 記錄累積損益

        tot = wins + losses  # 總筆數
        win_rate = (wins / tot * 100) if tot > 0 else 0.0  # 勝率
        pf = (win_usd / (loss_usd + 1e-9)) if loss_usd > 0 else (99.0 if wins > 0 else 0.0)  # 獲利因子
        eq_ser = pd.Series(equity_curve)  # Series
        bal_ser = eq_ser + 100000.0  # 換算 $100k
        mdd = ((bal_ser - bal_ser.cummax()) / bal_ser.cummax() * 100).min()  # 最大回撤
        ev = (cum_pnl / tot) if tot > 0 else 0.0  # 每筆期望值
        sharpe = (np.mean(trades_list) / (np.std(trades_list) + 1e-9) * np.sqrt(len(trades_list))) if len(trades_list) > 1 else 0.0  # 夏普評分
        
        return {
            "Symbol": symbol, "Timeframe": tf_key, "Strategy": "Short Straddle",
            "Trades": tot, "WinRate": round(win_rate, 1), "Profit": round(cum_pnl, 1),
            "PF": round(pf, 2), "MDD": round(mdd, 2), "EV": round(ev, 2), "Sharpe": round(sharpe, 2),
            "Equity": eq_ser
        }

    def execute_large_scale_screening(self):  # 執行全矩陣掃描與篩選
        print("=" * 80)  # 標頭
        print("   大規模多週期 (M5, M15, M30, H1) × 28 大外匯商品真實物理結算全矩陣量化回測   ")  # 標題
        print("=" * 80 + "\n")  # 分隔線

        results = []  # 儲存所有回測指標
        equity_dict = {}  # 儲存所有曲線

        total_tasks = len(self.symbols) * len(self.timeframes)  # 總下載任務數
        current_task = 0  # 當前進度

        for sym in self.symbols:  # 遍歷 28 大貨幣對
            for tf in ["M5", "M15", "M30", "H1"]:  # 遍歷 4 大週期
                current_task += 1  # 累計進度
                print(f"[{current_task}/{total_tasks}] 正在處理: [{sym}] [{tf}] ...", end="", flush=True)  # 日誌
                df = self.fetch_data(sym, tf)  # 抓取數據
                
                if df.empty or len(df) < 200:  # 檢查數據有效性
                    print(" ❌ 無法獲取數據")  # 輸出失敗
                    continue  # 跳過

                print(f" ✅ 獲取 {len(df)} 根 K線", end="", flush=True)  # 成功日誌
                
                # 執行策略 1: Asian Scalper
                res_scalper = self.run_scalper(sym, tf, df, lot_size=1.0)  # 回測
                if res_scalper["Trades"] >= 15:  # 過濾樣本過少
                    results.append(res_scalper)  # 加入
                    equity_dict[f"Scalper_{sym}_{tf}"] = res_scalper["Equity"]  # 儲存曲線

                # 執行策略 2: Short Straddle
                res_straddle = self.run_straddle(sym, tf, df, lot_size=1.0)  # 回測
                if res_straddle["Trades"] >= 15:  # 過濾樣本過少
                    results.append(res_straddle)  # 加入
                    equity_dict[f"Straddle_{sym}_{tf}"] = res_straddle["Equity"]  # 儲存曲線

                print(" -> 回測完成")  # 完成提示

        # 轉為 DataFrame 進行排序與評級
        df_res = pd.DataFrame(results)  # 建立 DataFrame
        df_res_clean = df_res.drop(columns=['Equity'])  # 移除曲線欄位以便輸出

        # 輸出完整 224 組回測結果至 CSV
        csv_path = "multi_tf_all_results.csv"  # CSV 路徑
        df_res_clean.to_csv(csv_path, index=False)  # 輸出
        print(f"\n[+] 全 28 標的 × 4 週期完整回測結果已輸出至: {csv_path}")  # 日誌

        # 篩選「FTMO 1-Step 黃金組合」條件:
        # 1. 獲利因子 PF >= 1.30
        # 2. 勝率 WinRate >= 65.0%
        # 3. 最大回撤 MDD >= -1.50% (即回撤不超過 1.5%)
        # 4. 總交易次數 Trades >= 25
        # 5. 總淨利 Profit > 0
        golden_filter = (
            (df_res_clean["PF"] >= 1.30) &
            (df_res_clean["WinRate"] >= 65.0) &
            (df_res_clean["MDD"] >= -1.50) &
            (df_res_clean["Trades"] >= 25) &
            (df_res_clean["Profit"] > 0)
        )
        df_golden = df_res_clean[golden_filter].sort_values(by=["PF", "Profit"], ascending=[False, False])  # 排序

        golden_csv_path = "golden_portfolio_matrix.csv"  # 黃金組合 CSV
        df_golden.to_csv(golden_csv_path, index=False)  # 輸出
        print(f"[+] FTMO 1-Step 黃金首選標的組合已輸出至: {golden_csv_path}")  # 日誌

        print("\n" + "=" * 90)  # 標頭
        print("               🏆 FTMO 1-Step 黃金首選標的排行榜 (PF >= 1.30, 勝率 >= 65%, MDD <= 1.5%)              ")  # 標題
        print("=" * 90)  # 標頭
        print(df_golden.to_string(index=False))  # 格式化輸出
        print("=" * 90 + "\n")  # 結尾

        # 繪製各週期頂級標的累積損益曲線圖
        self.plot_golden_portfolio_chart(df_golden, equity_dict)  # 繪圖

    def plot_golden_portfolio_chart(self, df_golden: pd.DataFrame, equity_dict: dict):  # 繪製黃金組合多子圖對比
        if df_golden.empty:  # 若無符合標的
            print("[!] 無符合黃金條件之標的，繪圖跳過。")  # 提示
            return  # 返回

        top_scalper = df_golden[df_golden["Strategy"] == "Asian Scalper"].head(5)  # 取前 5 名 Scalper
        top_straddle = df_golden[df_golden["Strategy"] == "Short Straddle"].head(5)  # 取前 5 名 Straddle

        plt.style.use('dark_background')  # 深色主題
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 11), sharex=False)  # 雙子圖
        fig.patch.set_facecolor('#0d1117')  # 畫布背景
        ax1.set_facecolor('#161b22')  # 子圖 1 背景
        ax2.set_facecolor('#161b22')  # 子圖 2 背景

        # 配色表
        palette = ["#58a6ff", "#3fb950", "#d2a8ff", "#f0883e", "#f85149", "#79c0ff", "#56d364"]  # 配色清單

        # 子圖 1: Top Asian Night Scalper
        for idx, row in top_scalper.reset_index().iterrows():  # 遍歷
            k = f"Scalper_{row['Symbol']}_{row['Timeframe']}"  # 鍵名
            if k in equity_dict:  # 若曲線存在
                eq = equity_dict[k]  # 取得曲線
                lbl = f"{row['Symbol']} [{row['Timeframe']}] (PF: {row['PF']}, WR: {row['WinRate']}%, PnL: +${row['Profit']})"  # 標籤
                ax1.plot(eq.values, label=lbl, color=palette[idx % len(palette)], linewidth=2.2)  # 繪線

        ax1.axhline(0, color='#8b949e', linestyle='--', linewidth=1.2, alpha=0.6, label='$0 Baseline')  # 基準線
        ax1.set_title('🏆 Top 5 Asian Night Scalper Combinations (Zero-Overnight, 1.0 Lot, $0 PnL Baseline)', fontsize=13, fontweight='bold', color='#f0f6fc')  # 標題
        ax1.set_ylabel('Cumulative Net Profit ($)', fontsize=11, color='#8b949e')  # Y 軸
        ax1.grid(True, linestyle=':', alpha=0.3, color='#30363d')  # 網格
        ax1.legend(loc='upper left', fontsize=9.5, facecolor='#21262d', edgecolor='#30363d')  # 圖例

        # 子圖 2: Top Synthetic Short Straddle
        for idx, row in top_straddle.reset_index().iterrows():  # 遍歷
            k = f"Straddle_{row['Symbol']}_{row['Timeframe']}"  # 鍵名
            if k in equity_dict:  # 若曲線存在
                eq = equity_dict[k]  # 取得曲線
                lbl = f"{row['Symbol']} [{row['Timeframe']}] (PF: {row['PF']}, WR: {row['WinRate']}%, PnL: +${row['Profit']})"  # 標籤
                ax2.plot(eq.values, label=lbl, color=palette[idx % len(palette)], linewidth=2.2)  # 繪線

        ax2.axhline(0, color='#8b949e', linestyle='--', linewidth=1.2, alpha=0.6, label='$0 Baseline')  # 基準線
        ax2.set_title('🏆 Top 5 Synthetic Short Straddle Combinations (Zero-Overnight, 1.0 Lot, $0 PnL Baseline)', fontsize=13, fontweight='bold', color='#f0f6fc')  # 標題
        ax2.set_ylabel('Cumulative Net Profit ($)', fontsize=11, color='#8b949e')  # Y 軸
        ax2.set_xlabel('Simulated Bar Steps', fontsize=11, color='#8b949e')  # X 軸
        ax2.grid(True, linestyle=':', alpha=0.3, color='#30363d')  # 網格
        ax2.legend(loc='upper left', fontsize=9.5, facecolor='#21262d', edgecolor='#30363d')  # 圖例

        plt.tight_layout()  # 自動排版
        out_chart = "multi_tf_best_portfolio.png"  # 圖名
        plt.savefig(out_chart, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')  # 存檔
        print(f"[+] 多週期黃金組合對比圖表已輸出至: {out_chart}")  # 日誌

if __name__ == "__main__":  # 執行入口
    engine = LargeScaleMultiTFBacktestEngine()  # 實例化
    engine.execute_large_scale_screening()  # 啟動大規模回測
