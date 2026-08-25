import os  # 導入作業系統模組
import json  # 導入 JSON 資料處理模組
import datetime  # 導入日期時間處理模組
import numpy as np  # 導入數值運算庫
import pandas as pd  # 導入資料表格分析庫
import warnings  # 導入警告控制模組

warnings.filterwarnings("ignore")  # 忽略無害警告

class MultiTimeframeMultiAssetEngine:  # 定義全天候跨週期多品種量化旗艦引擎 (PEPPERSTONE 數據源)
    def __init__(self):  # 初始化引擎
        self.data_dir = os.path.join(os.path.dirname(__file__), "data_pepperstone")  # 數據目錄
        
        # 13 大實盤品種點差 (Pips)
        self.spreads = {  # 點差對照表
            "EURUSD": 0.2, "GBPUSD": 0.6, "USDJPY": 0.3, "USDCAD": 0.4, "USDCHF": 0.4,  # 主要貨幣對
            "AUDUSD": 0.4, "NZDUSD": 0.7, "AUDCAD": 1.1, "AUDCHF": 0.8, "EURCHF": 0.6,  # 交叉貨幣對
            "GBPJPY": 1.2, "EURJPY": 0.8, "XAUUSD": 1.5                                  # 貴金屬與日圓交叉
        }  # 點差結束

        self.quote_rates = {  # 匯率對照表
            "USD": 1.0, "CAD": 1.0/1.38, "CHF": 1.0/0.80, "JPY": 1.0/159.0,  # 匯率
            "GBP": 1.36, "NZD": 0.60, "AUD": 0.71                            # 匯率
        }  # 匯率結束

        # 模組組合配置清單 (雙引擎架構: 引擎 A 亞盤 M15 震盪收租 + 引擎 B 歐美 1H 趨勢動量)
        self.module_configs = [  # 模組清單
            # 引擎 A: 亞盤夜間 M15 震盪收租 (含 ADX 趨勢防暴衝過濾)
            {"module_id": "M15_Night_USDCAD", "engine": "Engine A (夜間 M15 收租)", "symbol": "USDCAD", "tf": "15m", "type": "Mean_Reversion"},  # USDCAD
            {"module_id": "M15_Night_EURCHF", "engine": "Engine A (夜間 M15 收租)", "symbol": "EURCHF", "tf": "15m", "type": "Mean_Reversion"},  # EURCHF
            {"module_id": "M15_Night_AUDCAD", "engine": "Engine A (夜間 M15 收租)", "symbol": "AUDCAD", "tf": "15m", "type": "Mean_Reversion"},  # AUDCAD
            {"module_id": "M15_Night_USDCHF", "engine": "Engine A (夜間 M15 收租)", "symbol": "USDCHF", "tf": "15m", "type": "Mean_Reversion"},  # USDCHF
            {"module_id": "M15_Night_AUDCHF", "engine": "Engine A (夜間 M15 收租)", "symbol": "AUDCHF", "tf": "15m", "type": "Mean_Reversion"},  # AUDCHF
            {"module_id": "M15_Night_EURUSD", "engine": "Engine A (夜間 M15 收租)", "symbol": "EURUSD", "tf": "15m", "type": "Mean_Reversion"},  # EURUSD
            
            # 引擎 B: 歐美盤 1H 趨勢動量波段 (黃金 XAUUSD + 主流高波動貨幣對)
            {"module_id": "H1_Trend_XAUUSD", "engine": "Engine B (趨勢 1H 波段)", "symbol": "XAUUSD", "tf": "1h", "type": "Trend_Momentum"},     # 黃金現貨
            {"module_id": "H1_Trend_EURUSD", "engine": "Engine B (趨勢 1H 波段)", "symbol": "EURUSD", "tf": "1h", "type": "Trend_Momentum"},     # 歐美趨勢
            {"module_id": "H1_Trend_GBPJPY", "engine": "Engine B (趨勢 1H 波段)", "symbol": "GBPJPY", "tf": "1h", "type": "Trend_Momentum"}      # 鎊日趨勢
        ]  # 清單結束

    def get_pip_specs(self, symbol: str):  # 計算每 Pip 價值與單位
        if symbol == "XAUUSD":  # 黃金
            return 0.1, 10.0  # 0.1 點為 $10 (100 oz)
        if "JPY" in symbol:  # 日圓
            return 0.01, 100000.0 * 0.01 * self.quote_rates["JPY"]  # JPY
        return 0.0001, 100000.0 * 0.0001 * self.quote_rates.get(symbol[-3:], 1.0)  # 外匯

    def load_data(self, symbol: str, tf: str) -> pd.DataFrame:  # 讀取本機 PEPPERSTONE CSV
        f = os.path.join(self.data_dir, f"pepperstone_{symbol.lower()}_{tf}.csv")  # 檔案路徑
        if os.path.exists(f):  # 檔案存在
            df = pd.read_csv(f)  # 讀取
            df["mt5_time"] = pd.to_datetime(df["timestamp_mt5"])  # 轉 MT5 時間
            df = df.set_index("mt5_time")  # 設為索引
            return df  # 回傳
        return pd.DataFrame()  # 回傳空

    def run_engine_a_night(self, df_raw: pd.DataFrame, symbol: str, lot_size: float = 1.0) -> dict:  # 執行引擎 A: M15 亞盤收租
        df = df_raw.copy()  # 複製
        pip_size, pip_val = self.get_pip_specs(symbol)  # 取得規格
        sp_dist = self.spreads.get(symbol, 0.8) * pip_size  # 點差
        cost_per_trade = 5.0 * lot_size  # 手續費 $5
        
        df["MA20"] = df["close"].rolling(20).mean()  # 20 SMA
        df["STD20"] = df["close"].rolling(20).std()  # 20 STD
        df["UB"] = df["MA20"] + 2.2 * df["STD20"]  # 上軌
        df["LB"] = df["MA20"] - 2.2 * df["STD20"]  # 下軌
        
        tr = np.maximum(df["high"] - df["low"], np.maximum(abs(df["high"] - df["close"].shift(1)), abs(df["low"] - df["close"].shift(1))))  # TR
        df["ATR"] = tr.rolling(14).mean()  # ATR
        
        # ADX 趨勢強度濾網
        plus_dm = (df["high"] - df["high"].shift(1)).clip(lower=0)  # +DM
        minus_dm = (df["low"].shift(1) - df["low"]).clip(lower=0)  # -DM
        plus_di = 100 * (plus_dm.ewm(span=14).mean() / (df["ATR"] + 1e-9))  # +DI
        minus_di = 100 * (minus_dm.ewm(span=14).mean() / (df["ATR"] + 1e-9))  # -DI
        dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9))  # DX
        df["ADX"] = dx.ewm(span=14).mean()  # ADX
        
        # RSI 14
        delta = df["close"].diff()  # 差分
        gain = delta.where(delta > 0, 0).rolling(14).mean()  # 漲幅
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()  # 跌幅
        df["RSI"] = 100 - (100 / (1 + (gain / (loss + 1e-9))))  # RSI
        
        pos = 0  # 倉位
        trades = []  # 交易記錄
        balance = 100000.0  # 初始本金
        entry_p = 0.0  # 進場價
        entry_time = None  # 進場時間
        entry_bar_idx = 0  # 進場索引
        equity_records = []  # 權益紀錄
        
        for i in range(35, len(df)):  # 遍歷
            dt = df.index[i]  # 時間
            hr = dt.hour  # MT5 小時
            c = float(df["close"].iloc[i])  # 收盤
            h = float(df["high"].iloc[i])  # 最高
            l = float(df["low"].iloc[i])  # 最低
            atr = float(df["ATR"].iloc[i])  # ATR
            adx = float(df["ADX"].iloc[i])  # ADX
            is_force = (hr == 9)  # 歐盤前夕強制全平
            
            if pos != 0:  # 持倉
                closed = False  # 平倉標記
                exit_price = 0.0  # 出場價
                exit_reason = ""  # 原因
                
                if pos == 1:  # 多單
                    if c >= df["MA20"].iloc[i] and c > entry_p:  # 中軌止盈
                        exit_price = c - sp_dist  # 扣點差
                        exit_reason = "BB Middle (Mean Reversion)"  # 中軌
                        closed = True  # 平倉
                    elif l <= entry_p - 1.5 * atr or is_force:  # 停損或清倉
                        exit_price = (entry_p - 1.5 * atr - sp_dist) if l <= entry_p - 1.5 * atr else (c - sp_dist)  # 出場價
                        exit_reason = "SL (-1.5 ATR)" if l <= entry_p - 1.5 * atr else "Zero-Overnight (MT5 09:00)"  # 原因
                        closed = True  # 平倉
                        
                    if closed:  # 結算
                        pnl_pips = (exit_price - entry_p)/pip_size  # 點數
                        pnl_usd = pnl_pips * pip_val - cost_per_trade  # 美金
                        balance += pnl_usd  # 餘額
                        trades.append({  # 記錄
                            "strategy": "M15 亞盤收租 (Engine A)", "symbol": symbol, "type": "Buy", "lot_size": lot_size,
                            "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'), "entry_price": round(entry_p, 5),
                            "exit_time": dt.strftime('%Y-%m-%d %H:%M:%S'), "exit_price": round(exit_price, 5),
                            "pnl_usd": round(pnl_usd, 2), "pnl_pips": round(pnl_pips, 1), "exit_reason": exit_reason,
                            "duration_mins": (i - entry_bar_idx) * 15, "win": pnl_usd > 0
                        })  # 結束
                        pos = 0  # 重設
                        
                elif pos == -1:  # 空單
                    if c <= df["MA20"].iloc[i] and c < entry_p:  # 中軌止盈
                        exit_price = c + sp_dist  # 扣點差
                        exit_reason = "BB Middle (Mean Reversion)"  # 中軌
                        closed = True  # 平倉
                    elif h >= entry_p + 1.5 * atr or is_force:  # 停損或清倉
                        exit_price = (entry_p + 1.5 * atr + sp_dist) if h >= entry_p + 1.5 * atr else (c + sp_dist)  # 出場價
                        exit_reason = "SL (-1.5 ATR)" if h >= entry_p + 1.5 * atr else "Zero-Overnight (MT5 09:00)"  # 原因
                        closed = True  # 平倉
                        
                    if closed:  # 結算
                        pnl_pips = (entry_p - exit_price)/pip_size  # 點數
                        pnl_usd = pnl_pips * pip_val - cost_per_trade  # 美金
                        balance += pnl_usd  # 餘額
                        trades.append({  # 記錄
                            "strategy": "M15 亞盤收租 (Engine A)", "symbol": symbol, "type": "Sell", "lot_size": lot_size,
                            "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'), "entry_price": round(entry_p, 5),
                            "exit_time": dt.strftime('%Y-%m-%d %H:%M:%S'), "exit_price": round(exit_price, 5),
                            "pnl_usd": round(pnl_usd, 2), "pnl_pips": round(pnl_pips, 1), "exit_reason": exit_reason,
                            "duration_mins": (i - entry_bar_idx) * 15, "win": pnl_usd > 0
                        })  # 結束
                        pos = 0  # 重設
                        
            # 開倉檢查 (MT5 00:00 ~ 07:00 且 ADX < 24 非單邊盤)
            is_entry = (hr == 0 or 1 <= hr <= 7) and adx < 24 and not is_force  # 條件
            if pos == 0 and is_entry:  # 符合
                if c <= df["LB"].iloc[i] and df["RSI"].iloc[i] <= 32:  # 觸及下軌
                    pos = 1  # 買多
                    entry_p = c + sp_dist  # 買價
                    entry_time = dt  # 時間
                    entry_bar_idx = i  # 索引
                elif c >= df["UB"].iloc[i] and df["RSI"].iloc[i] >= 68:  # 觸及上軌
                    pos = -1  # 賣空
                    entry_p = c  # 賣價
                    entry_time = dt  # 時間
                    entry_bar_idx = i  # 索引
                    
            equity_records.append({"time": dt.strftime('%Y-%m-%d %H:%M:%S'), "balance": round(balance, 2)})  # 權益
            
        tot = len(trades)  # 筆數
        wins = sum(1 for t in trades if t["win"])  # 勝場
        wr = round(wins/tot*100, 1) if tot > 0 else 0.0  # 勝率
        pnl = round(sum(t["pnl_usd"] for t in trades), 2)  # 淨利
        win_d = sum(t["pnl_usd"] for t in trades if t["pnl_usd"] > 0)  # 毛利
        loss_d = sum(abs(t["pnl_usd"]) for t in trades if t["pnl_usd"] < 0)  # 毛損
        pf = round(win_d / (loss_d + 1e-9), 2) if loss_d > 0 else (99.0 if wins > 0 else 0.0)  # PF
        
        return {"symbol": symbol, "strategy": "M15 亞盤收租 (Engine A)", "trades": trades, "metrics": {"total_trades": tot, "wins": wins, "losses": tot-wins, "win_rate": wr, "total_pnl_usd": pnl, "profit_factor": pf}}

    def run_engine_b_trend(self, df_raw: pd.DataFrame, symbol: str, lot_size: float = 1.0) -> dict:  # 執行引擎 B: 1H 趨勢動量波段
        df = df_raw.copy()  # 複製
        pip_size, pip_val = self.get_pip_specs(symbol)  # 規格
        sp_dist = self.spreads.get(symbol, 1.0) * pip_size  # 點差
        cost_per_trade = 5.0 * lot_size  # 手續費
        
        df["EMA20"] = df["close"].ewm(span=20).mean()  # 20 EMA
        df["EMA50"] = df["close"].ewm(span=50).mean()  # 50 EMA
        df["EMA200"] = df["close"].ewm(span=200).mean()  # 200 EMA
        tr = np.maximum(df["high"] - df["low"], np.maximum(abs(df["high"] - df["close"].shift(1)), abs(df["low"] - df["close"].shift(1))))  # TR
        df["ATR"] = tr.rolling(14).mean()  # ATR
        
        pos = 0  # 倉位
        trades = []  # 交易記錄
        balance = 100000.0  # 初始本金
        entry_p = 0.0  # 進場價
        entry_time = None  # 時間
        entry_bar_idx = 0  # 索引
        equity_records = []  # 權益
        
        for i in range(200, len(df)):  # 遍歷
            dt = df.index[i]  # 時間
            c = float(df["close"].iloc[i])  # 收盤
            h = float(df["high"].iloc[i])  # 最高
            l = float(df["low"].iloc[i])  # 最低
            atr = float(df["ATR"].iloc[i])  # ATR
            if np.isnan(atr) or atr <= 0: continue  # 檢查
            
            if pos != 0:  # 持倉
                closed = False  # 標記
                exit_price = 0.0  # 出場價
                exit_reason = ""  # 原因
                
                if pos == 1:  # 多單
                    if h >= entry_p + 2.5 * atr:  # 止盈 2.5 ATR
                        exit_price = entry_p + 2.5 * atr - sp_dist  # 扣點差
                        exit_reason = "TP (+2.5 ATR Trend Target)"  # 止盈
                        closed = True  # 平倉
                    elif c < df["EMA20"].iloc[i] or l <= entry_p - 1.2 * atr:  # 跌破 EMA20 追蹤或硬停損
                        exit_price = (entry_p - 1.2 * atr - sp_dist) if l <= entry_p - 1.2 * atr else (c - sp_dist)  # 出場價
                        exit_reason = "SL (-1.2 ATR)" if l <= entry_p - 1.2 * atr else "Trailing Stop (EMA20 Breakdown)"  # 原因
                        closed = True  # 平倉
                        
                    if closed:  # 結算
                        pnl_pips = (exit_price - entry_p)/pip_size  # 點數
                        pnl_usd = pnl_pips * pip_val - cost_per_trade  # 美金
                        balance += pnl_usd  # 餘額
                        trades.append({  # 記錄
                            "strategy": "1H 趨勢動量 (Engine B)", "symbol": symbol, "type": "Buy", "lot_size": lot_size,
                            "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'), "entry_price": round(entry_p, 5),
                            "exit_time": dt.strftime('%Y-%m-%d %H:%M:%S'), "exit_price": round(exit_price, 5),
                            "pnl_usd": round(pnl_usd, 2), "pnl_pips": round(pnl_pips, 1), "exit_reason": exit_reason,
                            "duration_mins": (i - entry_bar_idx) * 60, "win": pnl_usd > 0
                        })  # 結束
                        pos = 0  # 重設
                        
                elif pos == -1:  # 空單
                    if l <= entry_p - 2.5 * atr:  # 止盈 2.5 ATR
                        exit_price = entry_p - 2.5 * atr + sp_dist  # 扣點差
                        exit_reason = "TP (+2.5 ATR Trend Target)"  # 止盈
                        closed = True  # 平倉
                    elif c > df["EMA20"].iloc[i] or h >= entry_p + 1.2 * atr:  # 突破 EMA20 追蹤或硬停損
                        exit_price = (entry_p + 1.2 * atr + sp_dist) if h >= entry_p + 1.2 * atr else (c + sp_dist)  # 出場價
                        exit_reason = "SL (-1.2 ATR)" if h >= entry_p + 1.2 * atr else "Trailing Stop (EMA20 Breakout)"  # 原因
                        closed = True  # 平倉
                        
                    if closed:  # 結算
                        pnl_pips = (entry_p - exit_price)/pip_size  # 點數
                        pnl_usd = pnl_pips * pip_val - cost_per_trade  # 美金
                        balance += pnl_usd  # 餘額
                        trades.append({  # 記錄
                            "strategy": "1H 趨勢動量 (Engine B)", "symbol": symbol, "type": "Sell", "lot_size": lot_size,
                            "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'), "entry_price": round(entry_p, 5),
                            "exit_time": dt.strftime('%Y-%m-%d %H:%M:%S'), "exit_price": round(exit_price, 5),
                            "pnl_usd": round(pnl_usd, 2), "pnl_pips": round(pnl_pips, 1), "exit_reason": exit_reason,
                            "duration_mins": (i - entry_bar_idx) * 60, "win": pnl_usd > 0
                        })  # 結束
                        pos = 0  # 重設
                        
            # 多空強勢排列突破開倉
            if pos == 0:  # 空手
                if df["EMA20"].iloc[i] > df["EMA50"].iloc[i] > df["EMA200"].iloc[i] and c > df["high"].iloc[i-1]:  # 多頭排列強勢突破
                    pos = 1  # 買多
                    entry_p = c + sp_dist  # 買價
                    entry_time = dt  # 時間
                    entry_bar_idx = i  # 索引
                elif df["EMA20"].iloc[i] < df["EMA50"].iloc[i] < df["EMA200"].iloc[i] and c < df["low"].iloc[i-1]:  # 空頭排列強勢跌破
                    pos = -1  # 賣空
                    entry_p = c  # 賣價
                    entry_time = dt  # 時間
                    entry_bar_idx = i  # 索引
                    
            equity_records.append({"time": dt.strftime('%Y-%m-%d %H:%M:%S'), "balance": round(balance, 2)})  # 權益
            
        tot = len(trades)  # 筆數
        wins = sum(1 for t in trades if t["win"])  # 勝場
        wr = round(wins/tot*100, 1) if tot > 0 else 0.0  # 勝率
        pnl = round(sum(t["pnl_usd"] for t in trades), 2)  # 淨利
        win_d = sum(t["pnl_usd"] for t in trades if t["pnl_usd"] > 0)  # 毛利
        loss_d = sum(abs(t["pnl_usd"]) for t in trades if t["pnl_usd"] < 0)  # 毛損
        pf = round(win_d / (loss_d + 1e-9), 2) if loss_d > 0 else (99.0 if wins > 0 else 0.0)  # PF
        
        return {"symbol": symbol, "strategy": "1H 趨勢動量 (Engine B)", "trades": trades, "metrics": {"total_trades": tot, "wins": wins, "losses": tot-wins, "win_rate": wr, "total_pnl_usd": pnl, "profit_factor": pf}}

    def execute_and_export(self):  # 執行全量模組回測並輸出 JSON 與 CSV
        print("==========================================================================")  # 分隔線
        print(" 🚀 啟動【全天候跨週期多品種旗艦量化組合 (PEPPERSTONE 源)】全量回測...")  # 標題
        print("==========================================================================")  # 分隔線
        
        all_completed_trades = []  # 全部交易明細
        modules_summary = []  # 模組明細表
        symbols_meta = {}  # 商品資訊
        chart_data_dict = {}  # 圖表資料
        
        now_utc = datetime.datetime.now(datetime.timezone.utc)  # UTC 時間
        now_mt5 = now_utc + datetime.timedelta(hours=3)  # MT5 時間
        now_tpe = now_utc + datetime.timedelta(hours=8)  # 台北時間

        for cfg in self.module_configs:  # 遍歷模組
            mod_id = cfg["module_id"]  # ID
            sym = cfg["symbol"]  # 品種
            tf = cfg["tf"]  # 週期
            df = self.load_data(sym, tf)  # 載入資料
            if df.empty: continue  # 檢查
            
            if cfg["type"] == "Mean_Reversion":  # 引擎 A
                res = self.run_engine_a_night(df, sym, lot_size=1.0)  # 執行
            else:  # 引擎 B
                res = self.run_engine_b_trend(df, sym, lot_size=1.0)  # 執行
                
            for t in res["trades"]:  # 遍歷交易
                t["module_id"] = mod_id  # 加上模組 ID
                all_completed_trades.append(t)  # 寫入總表
                
            modules_summary.append({  # 加入模組摘要
                "module_id": mod_id, "strategy": res["strategy"], "symbol": sym, "timeframe": tf,
                "trades_count": res["metrics"]["total_trades"], "wins": res["metrics"]["wins"], "losses": res["metrics"]["losses"],
                "win_rate": res["metrics"]["win_rate"], "total_pnl_usd": res["metrics"]["total_pnl_usd"], "profit_factor": res["metrics"]["profit_factor"],
                "max_drawdown_pct": 0.0, "max_drawdown_usd": 0.0, "roi_pct": round(res["metrics"]["total_pnl_usd"] / 100000.0 * 100, 2)
            })  # 結束

        # 依進場時間倒序
        all_completed_trades.sort(key=lambda x: x["entry_time"], reverse=True)  # 排序
        for idx, t in enumerate(all_completed_trades):  # 重編序號
            t["global_id"] = idx + 1  # 賦予全域序號

        # 構建各品種即時狀態與圖表 (取各品種 15m 或 1h 最近 500 根)
        unique_syms = list(set([c["symbol"] for c in self.module_configs]))  # 不重複品種
        for sym in unique_syms:  # 遍歷品種
            df_sym = self.load_data(sym, "15m" if sym != "XAUUSD" else "1h")  # 讀取
            if df_sym.empty: continue  # 檢查
            
            df_sym["MA20"] = df_sym["close"].rolling(20).mean()  # 20 SMA
            df_sym["STD20"] = df_sym["close"].rolling(20).std()  # 20 STD
            df_sym["UB"] = df_sym["MA20"] + 2.0 * df_sym["STD20"]  # 上軌
            df_sym["LB"] = df_sym["MA20"] - 2.0 * df_sym["STD20"]  # 下軌
            delta = df_sym["close"].diff()  # 差分
            gain = delta.where(delta > 0, 0).rolling(14).mean()  # 漲幅
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()  # 跌幅
            df_sym["RSI"] = 100 - (100 / (1 + (gain / (loss + 1e-9))))  # RSI
            df_sym["Z"] = (df_sym["close"] - df_sym["MA20"]) / (df_sym["STD20"] + 1e-9)  # Z-Score
            
            last_row = df_sym.iloc[-1]  # 最新一筆
            curr_c = float(last_row["close"])  # 最新價
            prev_c = float(df_sym["close"].iloc[-96]) if len(df_sym) >= 96 else float(df_sym["close"].iloc[0])  # 24H 價
            change_24h = (curr_c - prev_c) / prev_c * 100  # 漲跌幅
            
            symbols_meta[sym] = {  # 商品中繼
                "symbol": sym, "current_price": round(curr_c, 5), "price_change_24h_pct": round(change_24h, 2),
                "high_24h": round(float(df_sym["high"].iloc[-96:].max()), 5) if len(df_sym) >= 96 else round(float(df_sym["high"].max()), 5),
                "low_24h": round(float(df_sym["low"].iloc[-96:].min()), 5) if len(df_sym) >= 96 else round(float(df_sym["low"].min()), 5),
                "current_rsi": round(float(last_row["RSI"]), 1) if not np.isnan(last_row["RSI"]) else 50.0,
                "current_zscore": round(float(last_row["Z"]), 2) if not np.isnan(last_row["Z"]) else 0.0,
                "spread_pips": self.spreads.get(sym, 0.8), "is_scalper_session": (now_mt5.hour == 0 or 1 <= now_mt5.hour <= 7),
                "is_straddle_session": (9 <= now_mt5.hour <= 22)
            }  # 結束
            
            df_chart = df_sym.tail(500).copy()  # 最近 500 根
            chart_data_dict[sym] = {  # 圖表封包
                "timestamps": [t.strftime('%Y-%m-%d %H:%M') for t in df_chart.index],
                "open": [round(float(x), 5) for x in df_chart["open"]], "high": [round(float(x), 5) for x in df_chart["high"]],
                "low": [round(float(x), 5) for x in df_chart["low"]], "close": [round(float(x), 5) for x in df_chart["close"]],
                "volume": [round(float(x), 1) for x in df_chart["volume"]],
                "bb_upper": [round(float(x), 5) if not np.isnan(x) else None for x in df_chart["UB"]],
                "bb_mid": [round(float(x), 5) if not np.isnan(x) else None for x in df_chart["MA20"]],
                "bb_lower": [round(float(x), 5) if not np.isnan(x) else None for x in df_chart["LB"]],
                "rsi": [round(float(x), 1) if not np.isnan(x) else None for x in df_chart["RSI"]],
                "z_score": [round(float(x), 2) if not np.isnan(x) else None for x in df_chart["Z"]]
            }  # 結束

        # 組合統計
        tot_trades = len(all_completed_trades)  # 總筆數
        wins = sum(1 for t in all_completed_trades if t["win"])  # 獲利數
        wr = round(wins/tot_trades*100, 1) if tot_trades > 0 else 0.0  # 勝率
        pnl = sum(t["pnl_usd"] for t in all_completed_trades)  # 總淨利
        win_d = sum(t["pnl_usd"] for t in all_completed_trades if t["pnl_usd"] > 0)  # 毛利
        loss_d = sum(abs(t["pnl_usd"]) for t in all_completed_trades if t["pnl_usd"] < 0)  # 毛損
        pf = round(win_d / (loss_d + 1e-9), 2) if loss_d > 0 else 99.0  # PF

        # 累積損益曲線
        trades_chronological = sorted(all_completed_trades, key=lambda x: x["exit_time"])  # 依時間正序
        first_time = trades_chronological[0]["entry_time"] if trades_chronological else "2025-10-01 00:00:00"  # 起點
        combined_equity_curve = [{"time": first_time, "cum_pnl": 0.0, "balance": 100000.0, "pnl": 0.0}]  # 起點
        running_pnl = 0.0  # 累計損益
        for t in trades_chronological:  # 遍歷
            running_pnl += t["pnl_usd"]  # 累加
            combined_equity_curve.append({  # 記錄節點
                "time": t["exit_time"], "cum_pnl": round(running_pnl, 2), "balance": round(100000.0 + running_pnl, 2),
                "pnl": t["pnl_usd"], "symbol": t["symbol"], "strategy": t["strategy"]
            })  # 結束

        comb_series = pd.Series([r["balance"] for r in combined_equity_curve])  # Series
        comb_cum_max = comb_series.cummax()  # 新高
        comb_dd_series = (comb_series - comb_cum_max) / comb_cum_max * 100  # 回撤
        mdd_pct = round(abs(comb_dd_series.min()), 2) if len(comb_dd_series) > 0 else 0.0  # MDD%
        mdd_usd = round(abs((comb_series - comb_cum_max).min()), 2) if len(comb_series) > 0 else 0.0  # MDD 美金

        payload = {  # 總 JSON
            "system_info": {  # 系統資訊
                "title": "全天候跨週期多品種旗艦量化監控儀表板 (M15+1H 抗摩擦穩健組合)",  # 標題
                "data_source": "TradingView (Broker: PEPPERSTONE)",  # 數據源
                "time_standard": "MT5 伺服器時間 (夏令 UTC+3 / 冬令 UTC+2)",  # 時間標準
                "last_updated_mt5": now_mt5.strftime('%Y-%m-%d %H:%M:%S (MT5 Server Time)'),  # MT5 時間
                "last_updated_tpe": now_tpe.strftime('%Y-%m-%d %H:%M:%S (台北 UTC+8)'),  # 台北時間
                "last_updated_utc": now_utc.strftime('%Y-%m-%d %H:%M:%S UTC'),  # UTC 時間
                "symbols_count": len(unique_syms), "modules_count": len(modules_summary)  # 統計數
            },  # 結束
            "portfolio_metrics": {  # 核心 KPI
                "total_trades": tot_trades, "wins": wins, "losses": tot_trades - wins, "win_rate": wr,
                "total_pnl_usd": round(pnl, 2), "profit_factor": pf, "max_drawdown_pct": mdd_pct,
                "max_drawdown_usd": mdd_usd, "roi_pct": round(pnl / 100000.0 * 100, 2),
                "initial_capital": 100000.0, "current_capital": round(100000.0 + pnl, 2)
            },  # 結束
            "modules_summary": modules_summary, "symbols_meta": symbols_meta, "active_positions": [],
            "combined_equity_curve": combined_equity_curve, "all_trades": all_completed_trades, "chart_data": chart_data_dict
        }  # 結束

        # 輸出 JSON
        json_path = os.path.join(os.path.dirname(__file__), "strategy_results.json")  # 路徑
        with open(json_path, "w", encoding="utf-8") as f:  # 寫入
            json.dump(payload, f, ensure_ascii=False, indent=2)  # 格式化
        print(f"[+] 策略回測數據 (旗艦組合) 已輸出至: {json_path}")  # 日誌

        # 輸出 CSV
        csv_path = os.path.join(os.path.dirname(__file__), "all_trades_history.csv")  # 路徑
        pd.DataFrame(all_completed_trades).to_csv(csv_path, index=False, encoding="utf-8-sig")  # 輸出
        print(f"[+] 完整歷史交易明細已輸出至: {csv_path}")  # 日誌

        print("\n==========================================================================")  # 分隔線
        print(f" 🏆【全天候跨週期旗艦量化組合】回測總淨利: +${pnl:,.2f} USD | 勝率: {wr}% | PF: {pf} | MDD: -{mdd_pct}%")  # 成果
        print("==========================================================================")  # 分隔線

if __name__ == "__main__":  # 主入口
    engine = MultiTimeframeMultiAssetEngine()  # 實例化
    engine.execute_and_export()  # 執行
