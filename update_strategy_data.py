import os  # 導入作業系統模組
import json  # 導入 JSON 數據處理庫
import datetime  # 導入日期時間模組
import numpy as np  # 導入數值計算庫
import pandas as pd  # 導入 Pandas 表格庫

class SchemeDOptionHarvestEngine:  # 定義方案 D【全天分工收租旗艦 v5.10 汰弱留強精銳版】收租引擎
    def __init__(self):  # 初始化建構子
        self.data_dir = os.path.join(os.path.dirname(__file__), "data_pepperstone")  # 數據目錄
        
        # Pepperstone 實盤平均點差 (pips)
        self.spreads = {  # 點差字典
            "GBPJPY": 2.1,  # 鎊日 2.1 pips
            "EURJPY": 1.2,  # 歐日 1.2 pips
            "GBPUSD": 0.8,  # 鎊美 0.8 pips
            "EURCAD": 1.9,  # 歐加 1.9 pips
            "AUDCHF": 1.0,  # 澳瑞 1.0 pips
            "AUDUSD": 0.6   # 澳美 0.6 pips
        }  # 結束
        
        # MT5 實盤計價幣別對美金即時匯率
        self.quote_to_usd_rates = {  # 匯率換算表
            "USD": 1.00000,                  # 美金 $1.00000
            "CHF": 1.0 / 0.80218,            # 1 CHF = $1.24660 USD (每手每點 = $12.47 USD)
            "GBP": 1.36386,                  # 1 GBP = $1.36386 USD (每手每點 = $13.64 USD)
            "CAD": 1.0 / 1.38452,            # 1 CAD = $0.72227 USD (每手每點 = $7.22 USD)
            "JPY": 1.0 / 159.178,            # 1 JPY = $0.006282 USD (每手每點 = $6.28 USD)
            "AUD": 0.71000,                  # 1 AUD = $0.71000 USD (每手每點 = $7.10 USD)
            "NZD": 0.60000                   # 1 NZD = $0.60000 USD (每手每點 = $6.00 USD)
        }  # 匯率結束

        # 方案 A 穩健組合 8 大王牌模組 (v5.10 汰弱留強精銳版)
        self.modules = [  # 模組清單
            # === 🌙 US_Afternoon 美盤午後 (4 組) ===
            {"module_id": "Opt_GBPJPY_1H_US",   "symbol": "GBPJPY", "tf": "1h",  "session_group": "US_AFTERNOON", "s_hr": 13, "e_hr": 18, "f_hr": 22, "sigma": 2.2, "sl": 1.5, "name": "1h 鎊日美盤高波收租 (v5.10 自適應帶寬)"},   # GBPJPY 1h — 絕對王牌
            {"module_id": "Opt_EURJPY_1H_US",   "symbol": "EURJPY", "tf": "1h",  "session_group": "US_AFTERNOON", "s_hr": 13, "e_hr": 18, "f_hr": 22, "sigma": 2.5, "sl": 1.5, "name": "1h 歐日美盤波動收租 (v5.10 自適應帶寬)"},   # EURJPY 1h
            {"module_id": "Opt_GBPUSD_15M_US",  "symbol": "GBPUSD", "tf": "15m", "session_group": "US_AFTERNOON", "s_hr": 13, "e_hr": 18, "f_hr": 22, "sigma": 2.2, "sl": 2.0, "name": "15m 鎊美美盤極速收租 (v5.10 自適應帶寬)"}, # GBPUSD 15m
            {"module_id": "Opt_EURCAD_1H_US",   "symbol": "EURCAD", "tf": "1h",  "session_group": "US_AFTERNOON", "s_hr": 13, "e_hr": 18, "f_hr": 22, "sigma": 3.0, "sl": 2.0, "name": "1h 歐加美盤高盈虧收租 (v5.10 自適應帶寬)"}, # 🆕 EURCAD 1h
            # === ☀️ DaytimeChannel 白天全天通道 (4 組) ===
            {"module_id": "Opt_EURJPY_15M_DAY",  "symbol": "EURJPY", "tf": "15m", "session_group": "DAY_CHANNEL",  "s_hr": 1,  "e_hr": 18, "f_hr": 22, "sigma": 3.0, "sl": 2.0, "name": "15m 歐日白天極限收租 (v5.10 自適應帶寬)"}, # EURJPY 15m
            {"module_id": "Opt_AUDCHF_1H_DAY",   "symbol": "AUDCHF", "tf": "1h",  "session_group": "DAY_CHANNEL",  "s_hr": 1,  "e_hr": 18, "f_hr": 22, "sigma": 2.8, "sl": 2.5, "name": "1h 澳瑞全天避險收租 (v5.10 自適應帶寬)"},  # AUDCHF 1h
            {"module_id": "Opt_AUDUSD_1H_DAY",   "symbol": "AUDUSD", "tf": "1h",  "session_group": "DAY_CHANNEL",  "s_hr": 1,  "e_hr": 18, "f_hr": 22, "sigma": 3.0, "sl": 2.0, "name": "1h 澳美白天低點差收租 (v5.10 自適應帶寬)"},  # 🆕 AUDUSD 1h
            {"module_id": "Opt_GBPJPY_15M_DAY",  "symbol": "GBPJPY", "tf": "15m", "session_group": "DAY_CHANNEL",  "s_hr": 1,  "e_hr": 18, "f_hr": 22, "sigma": 2.8, "sl": 2.5, "name": "15m 鎊日白天波動收租 (v5.10 自適應帶寬)"},   # 🆕 GBPJPY 15m
        ]  # 清單結束

    def get_pip_specs(self, symbol: str):  # 依據計價貨幣計算每點單位與換算美金價值
        if "JPY" in symbol:  # 日圓貨幣對
            pip_size = 0.01  # 0.01 為 1 Pip
            pip_val_usd = 100000.0 * pip_size * self.quote_to_usd_rates["JPY"]  # 換算美金
            return pip_size, pip_val_usd  # 回傳
        
        quote_ccy = symbol[3:]  # 後三碼為計價幣別
        rate_to_usd = self.quote_to_usd_rates.get(quote_ccy, 1.0)  # 取得計價幣對 USD 匯率
        pip_size = 0.0001  # 標準 4 位小數貨幣對 0.0001 為 1 Pip
        pip_val_usd = 100000.0 * pip_size * rate_to_usd  # 換算每手每點美金價值
        return pip_size, pip_val_usd  # 回傳點數規格

    def load_data(self, symbol: str, timeframe: str):  # 讀取 CSV 行情歷史數據
        csv_file = os.path.join(self.data_dir, f"pepperstone_{symbol.lower()}_{timeframe}.csv")  # 檔案路徑
        if not os.path.exists(csv_file):  # 檢查檔案
            print(f"⚠️ 找不到數據檔案: {csv_file}")  # 警告
            return pd.DataFrame()  # 空表格
        
        df = pd.read_csv(csv_file)  # 讀取 CSV
        df["mt5_time"] = pd.to_datetime(df["timestamp_mt5"])  # 轉換時間
        df = df.set_index("mt5_time").sort_index()  # 設為時間索引
        return df  # 回傳資料表

    def run_single_module(self, df: pd.DataFrame, mod: dict, lot_size: float = 1.0):  # 執行單模組模擬撮合
        symbol = mod["symbol"]  # 品種
        pip_size, pip_val_usd = self.get_pip_specs(symbol)  # 點數規格
        sp_pips = self.spreads.get(symbol, 1.5)  # 實盤點差
        sp_dist = sp_pips * pip_size  # 點差價格距離
        cost_per_trade = 5.0 * lot_size  # 每手進出固定扣除 $5.00 USD 手續費
        
        # 指標計算
        df = df.copy()  # 複製資料表
        df["MA20"] = df["close"].rolling(20).mean()  # 20 SMA 中軌
        df["STD20"] = df["close"].rolling(20).std()  # 20 標準差
        df["UB"] = df["MA20"] + mod["sigma"] * df["STD20"]  # 上軌
        df["LB"] = df["MA20"] - mod["sigma"] * df["STD20"]  # 下軌
        
        tr = np.maximum(df["high"] - df["low"], np.maximum(abs(df["high"] - df["close"].shift(1)), abs(df["low"] - df["close"].shift(1))))  # TR
        df["ATR"] = tr.rolling(14).mean()  # 14 ATR
        
        delta = df["close"].diff()  # 價格差分
        gain = delta.where(delta > 0, 0).rolling(14).mean()  # 平均漲幅
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()  # 平均跌幅
        df["RSI"] = 100 - (100 / (1 + (gain / (loss + 1e-9))))  # 14 RSI
        
        # [v5.10] 布林帶寬擴張比率計算
        df["BB_WIDTH"] = (df["UB"] - df["LB"]) / (df["MA20"] + 1e-9)  # 當前帶寬
        df["BB_WIDTH_MA"] = df["BB_WIDTH"].rolling(20).mean()  # 帶寬 20 均線
        df["BB_WIDTH_RATIO"] = df["BB_WIDTH"] / (df["BB_WIDTH_MA"] + 1e-9)  # 帶寬比率
        
        # [v5.10] K 線反向引線形態佔比計算
        candle_range = (df["high"] - df["low"]) + 1e-9  # 全距
        df["LOWER_WICK_RATIO"] = (np.minimum(df["open"], df["close"]) - df["low"]) / candle_range  # 下影線佔比
        df["UPPER_WICK_RATIO"] = (df["high"] - np.maximum(df["open"], df["close"])) / candle_range  # 上影線佔比

        bb_ratio_limit = 1.60 if mod["tf"] == "1h" else 1.85  # 依週期設定帶寬上限
        min_wick_ratio = 0.04  # 最小引線確認比例
        
        s_hr, e_hr = mod["s_hr"], mod["e_hr"]  # 開倉小時範圍
        f_hr = mod["f_hr"]  # 強制平倉小時 (MT5 22:00 = 台北 03:00)
        bar_mins = 60 if mod["tf"] == "1h" else 15  # 單根 K 棒分鐘數
        
        pos = 0  # 倉位狀態 (0: 空手, 1: 多單/賣 Put, -1: 空單/賣 Call)
        entry_p = 0.0  # 進場價格
        entry_time = None  # 進場時間
        entry_bar_idx = 0  # 進場 K 棒索引
        trades = []  # 交易記錄清單
        balance = 100000.0  # 初始本金
        
        for i in range(35, len(df)):  # 遍歷 K 棒進行真實撮合
            dt = df.index[i]  # 時間
            hr, mi = dt.hour, dt.minute  # 小時分鐘
            c = float(df["close"].iloc[i])  # 收盤
            h = float(df["high"].iloc[i])  # 最高
            l = float(df["low"].iloc[i])  # 最低
            o = float(df["open"].iloc[i])  # 開盤
            atr = float(df["ATR"].iloc[i])  # ATR
            
            # 判斷是否處於允許開倉時間窗口
            is_window = False  # 預設 false
            if s_hr == 1:  # 白天全天通道組 (MT5 01:15 ~ 17:59)
                if (hr == 1 and mi >= 15) or (2 <= hr <= e_hr):  # 符合時間
                    is_window = True  # 開放
            else:  # 晚間美盤午後組 (MT5 13:00 ~ 18:59)
                if s_hr <= hr <= e_hr:  # 符合時間
                    is_window = True  # 開放
                    
            # 判斷是否為每日強制清倉時間 (MT5 22:00 或週五 MT5 20:00 提前清倉)
            is_friday_close = (dt.weekday() == 4 and hr >= 20)  # 週五提前清倉檢查 (避免週末跳空)
            is_force = (hr >= f_hr or hr == 0 or is_friday_close)  # 強制平倉旗標
            
            # 持倉管理 (止盈 / 停損 / 時間衰減 / 強制平倉)
            if pos != 0:  # 若有持倉
                closed = False  # 平倉旗標
                exit_price = 0.0  # 出場價
                exit_reason = ""  # 出場原因
                bars_held = i - entry_bar_idx  # 持倉 K 棒數
                
                curr_sl_dist = mod["sl"] * atr  # 基本 ATR 停損距離
                if bars_held >= 8:  # [v5.10] 持倉 >= 8 根觸發時間價值階梯衰減收緊
                    decay_factor = 1.0 - min(0.25, (bars_held - 7) * 0.03)  # 每根收緊 3% (上限 25%)
                    curr_sl_dist *= decay_factor  # 更新停損距離
                
                if pos == 1:  # 多單
                    if c >= df["MA20"].iloc[i] and c > entry_p:  # 碰中軌且高於成本才止盈
                        exit_price = c - sp_dist  # 扣點差
                        exit_reason = "BB Middle (Mean Reversion)"  # 中軌止盈
                        closed = True  # 平倉
                    elif l <= entry_p - curr_sl_dist or is_force:  # 停損或清倉
                        exit_price = (entry_p - curr_sl_dist - sp_dist) if l <= entry_p - curr_sl_dist else (c - sp_dist)  # 出場價
                        if is_friday_close:  # 若為週五提前清倉
                            exit_reason = "Cut Before Weekend (Friday MT5 20:00)"  # 週五清倉原因
                        elif l <= entry_p - curr_sl_dist:  # 停損
                            exit_reason = f"SL (-{mod['sl']} ATR)"  # 停損原因
                        else:  # 常規換日清倉
                            exit_reason = "Cut Before Rollover (MT5 22:00)"  # 換日原因
                        closed = True  # 平倉
                        
                    if closed:  # 結算
                        pnl_pips = (exit_price - entry_p) / pip_size  # 點數
                        pnl_usd = pnl_pips * pip_val_usd - cost_per_trade  # 美金淨利 (已扣手續費)
                        balance += pnl_usd  # 餘額
                        trades.append({  # 記錄
                            "strategy": mod["name"], "symbol": symbol, "timeframe": mod["tf"], "type": "Buy (Short Put)", "lot_size": lot_size,
                            "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'), "entry_price": round(entry_p, 5),
                            "exit_price": round(exit_price, 5), "exit_time": (dt + datetime.timedelta(minutes=bar_mins)).strftime('%Y-%m-%d %H:%M:%S'),
                            "pnl_usd": round(pnl_usd, 2), "pnl_pips": round(pnl_pips, 1), "exit_reason": exit_reason,
                            "duration_mins": (i - entry_bar_idx + 1) * bar_mins, "win": pnl_usd > 0
                        })  # 結束
                        pos = 0  # 重設
                        
                elif pos == -1:  # 空單
                    if c <= df["MA20"].iloc[i] and c < entry_p:  # 碰中軌且低於成本才止盈
                        exit_price = c + sp_dist  # 扣點差
                        exit_reason = "BB Middle (Mean Reversion)"  # 中軌止盈
                        closed = True  # 平倉
                    elif h >= entry_p + curr_sl_dist or is_force:  # 停損或清倉
                        exit_price = (entry_p + curr_sl_dist + sp_dist) if h >= entry_p + curr_sl_dist else (c + sp_dist)  # 出場價
                        if is_friday_close:  # 若為週五提前清倉
                            exit_reason = "Cut Before Weekend (Friday MT5 20:00)"  # 週五清倉原因
                        elif h >= entry_p + curr_sl_dist:  # 停損
                            exit_reason = f"SL (-{mod['sl']} ATR)"  # 停損原因
                        else:  # 常規換日清倉
                            exit_reason = "Cut Before Rollover (MT5 22:00)"  # 換日原因
                        closed = True  # 平倉
                        
                    if closed:  # 結算
                        pnl_pips = (entry_p - exit_price) / pip_size  # 點數
                        pnl_usd = pnl_pips * pip_val_usd - cost_per_trade  # 美金淨利 (已扣手續費)
                        balance += pnl_usd  # 餘額
                        trades.append({  # 記錄
                            "strategy": mod["name"], "symbol": symbol, "timeframe": mod["tf"], "type": "Sell (Short Call)", "lot_size": lot_size,
                            "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'), "entry_price": round(entry_p, 5),
                            "exit_price": round(exit_price, 5), "exit_time": (dt + datetime.timedelta(minutes=bar_mins)).strftime('%Y-%m-%d %H:%M:%S'),
                            "pnl_usd": round(pnl_usd, 2), "pnl_pips": round(pnl_pips, 1), "exit_reason": exit_reason,
                            "duration_mins": (i - entry_bar_idx + 1) * bar_mins, "win": pnl_usd > 0
                        })  # 結束
                        pos = 0  # 重設
                        
            # [v5.10] 開倉檢查 (帶寬擴張防禦 + 引線動能衰竭確認)
            if pos == 0 and is_window and not is_force:  # 空手且在開倉時段
                bb_ratio = float(df["BB_WIDTH_RATIO"].iloc[i])  # 帶寬比率
                lower_wick = float(df["LOWER_WICK_RATIO"].iloc[i])  # 下影線佔比
                upper_wick = float(df["UPPER_WICK_RATIO"].iloc[i])  # 上影線佔比
                
                # 多單 (賣 Put)：跌破下軌 + RSI <= 32 + 帶寬安全 + 下影線 >= 4% 或收陽線
                if c <= df["LB"].iloc[i] and df["RSI"].iloc[i] <= 32.0 and bb_ratio <= bb_ratio_limit and (lower_wick >= min_wick_ratio or c > o):  # 多單條件
                    pos = 1  # 開多
                    entry_p = c + sp_dist  # 買進加點差
                    entry_time = dt + datetime.timedelta(minutes=bar_mins)  # 對齊次根 K 棒開盤時間 (與 MT5 下單時間 100% 一致)
                    entry_bar_idx = i  # 索引
                # 空單 (賣 Call)：衝破上軌 + RSI >= 68 + 帶寬安全 + 上影線 >= 4% 或收陰線
                elif c >= df["UB"].iloc[i] and df["RSI"].iloc[i] >= 68.0 and bb_ratio <= bb_ratio_limit and (upper_wick >= min_wick_ratio or c < o):  # 空單條件
                    pos = -1  # 開空
                    entry_p = c - sp_dist  # 賣出扣點差
                    entry_time = dt + datetime.timedelta(minutes=bar_mins)  # 對齊次根 K 棒開盤時間 (與 MT5 下單時間 100% 一致)
                    entry_bar_idx = i  # 索引
                    
        # 計算模組統計指標
        tot = len(trades)  # 筆數
        wins = sum(1 for t in trades if t["win"])  # 獲利數
        wr = round(wins / tot * 100, 1) if tot > 0 else 0.0  # 勝率
        pnl = round(sum(t["pnl_usd"] for t in trades), 2)  # 淨利
        gross_win = sum(t["pnl_usd"] for t in trades if t["pnl_usd"] > 0)  # 毛利
        gross_loss = sum(abs(t["pnl_usd"]) for t in trades if t["pnl_usd"] < 0)  # 毛損
        pf = round(gross_win / (gross_loss + 1e-9), 2) if gross_loss > 0 else 99.0  # PF
        
        return {  # 回傳模組結果
            "module_id": mod["module_id"], "strategy": mod["name"], "symbol": symbol,
            "metrics": {"total_trades": tot, "winning_trades": wins, "losing_trades": tot - wins, "win_rate": wr, "total_pnl_usd": pnl, "profit_factor": pf},
            "trades": trades  # 交易清單
        }  # 結束

    def execute_and_export(self):  # 執行全量計算並輸出 JSON/CSV
        print("==========================================================================")  # 分隔線
        print(" 🚀 啟動【方案 D：全天分工收租旗艦 v5.10】全量回測與即時數據更新...")  # 標題
        print("==========================================================================")  # 分隔線
        
        all_completed_trades = []  # 全部完成交易清單
        modules_summary = []  # 模組摘要清單
        chart_data_dict = {}  # 圖表資料字典
        
        now_utc = datetime.datetime.now(datetime.timezone.utc)  # 當前 UTC
        now_mt5 = now_utc + datetime.timedelta(hours=3)  # MT5 時間 (UTC+3)
        now_tpe = now_utc + datetime.timedelta(hours=8)  # 台北時間 (UTC+8)

        for mod in self.modules:  # 遍歷模組
            mod_id = mod["module_id"]  # ID
            sym = mod["symbol"]  # 品種
            tf = mod["tf"]  # 週期
            df = self.load_data(sym, tf)  # 讀取
            if df.empty: continue  # 檢查
            
            res = self.run_single_module(df, mod, lot_size=1.0)  # 執行
            for t in res["trades"]:  # 遍歷交易
                t["module_id"] = mod_id  # 賦予 ID
                all_completed_trades.append(t)  # 寫入總表
                
            modules_summary.append({  # 加入模組摘要
                "module_id": mod_id, "strategy": res["strategy"], "symbol": sym, "timeframe": tf,
                "session_group": mod["session_group"], "total_pnl_usd": res["metrics"]["total_pnl_usd"],
                "trades_count": res["metrics"]["total_trades"],
                "wins": res["metrics"]["winning_trades"],
                "losses": res["metrics"]["losing_trades"],
                "win_rate": res["metrics"]["win_rate"],
                "profit_factor": res["metrics"]["profit_factor"],
                "roi_pct": round(res["metrics"]["total_pnl_usd"] / 100000.0 * 100, 2),
                "sigma": mod["sigma"], "sl_atr": mod["sl"]
            })  # 結束
            
            # 生成圖表歷史行情與指標序列
            df_chart = df.iloc[-500:].copy()  # 取最近 500 根
            df_chart["MA20"] = df_chart["close"].rolling(20).mean()  # 中軌
            df_chart["STD20"] = df_chart["close"].rolling(20).std()  # 標準差
            df_chart["UB"] = df_chart["MA20"] + mod["sigma"] * df_chart["STD20"]  # 上軌
            df_chart["LB"] = df_chart["MA20"] - mod["sigma"] * df_chart["STD20"]  # 下軌
            
            chart_payload = {  # 圖表資料物件
                "timestamps": [t.strftime('%Y-%m-%d %H:%M') for t in df_chart.index],  # 時間陣列
                "open": [round(x, 5) for x in df_chart["open"]],  # 開盤陣列
                "high": [round(x, 5) for x in df_chart["high"]],  # 最高陣列
                "low": [round(x, 5) for x in df_chart["low"]],  # 最低陣列
                "close": [round(x, 5) for x in df_chart["close"]],  # 收盤陣列
                "ma20": [round(x, 5) if not np.isnan(x) else None for x in df_chart["MA20"]],  # 20 SMA
                "ub": [round(x, 5) if not np.isnan(x) else None for x in df_chart["UB"]],  # 上軌
                "lb": [round(x, 5) if not np.isnan(x) else None for x in df_chart["LB"]],  # 下軌
                "bb_mid": [round(x, 5) if not np.isnan(x) else None for x in df_chart["MA20"]],  # 中軌別名
                "bb_upper": [round(x, 5) if not np.isnan(x) else None for x in df_chart["UB"]],  # 上軌別名
                "bb_lower": [round(x, 5) if not np.isnan(x) else None for x in df_chart["LB"]]  # 下軌別名
            }  # 結束
            chart_data_dict[mod_id] = chart_payload  # 以模組 ID 存入
            chart_data_dict[sym] = chart_payload  # 以標的名存入供 K 線切換使用

        all_completed_trades.sort(key=lambda x: x["exit_time"])  # 依出場時間排序
        for idx, t in enumerate(all_completed_trades, start=1):  # 給予唯一序號
            t["trade_id"] = idx  # 序號

        cum_pnl = 0.0  # 累計損益
        equity_series = []  # 權益曲線
        for t in all_completed_trades:  # 遍歷交易
            cum_pnl += t["pnl_usd"]  # 累加
            equity_series.append({"time": t["exit_time"], "equity": round(100000.0 + cum_pnl, 2), "pnl": t["pnl_usd"]})  # 寫入

        eq_vals = [e["equity"] for e in equity_series] if equity_series else [100000.0]  # 權益值陣列
        peak = 100000.0  # 最高淨值
        max_dd = 0.0  # 最大回撤
        for v in eq_vals:  # 計算回撤
            if v > peak: peak = v  # 更新最高
            dd = peak - v  # 當前回撤
            if dd > max_dd: max_dd = dd  # 更新最大回撤

        tot_trades = len(all_completed_trades)  # 總筆數
        tot_wins = sum(1 for t in all_completed_trades if t["win"])  # 總獲利數
        tot_pnl = round(cum_pnl, 2)  # 總淨利
        tot_wr = round(tot_wins / tot_trades * 100, 1) if tot_trades > 0 else 0.0  # 總勝率
        tot_gross_win = sum(t["pnl_usd"] for t in all_completed_trades if t["pnl_usd"] > 0)  # 總毛利
        tot_gross_loss = sum(abs(t["pnl_usd"]) for t in all_completed_trades if t["pnl_usd"] < 0)  # 總毛損
        tot_pf = round(tot_gross_win / (tot_gross_loss + 1e-9), 2) if tot_gross_loss > 0 else 99.0  # 總 PF

        final_eq = eq_vals[-1] if eq_vals else 100000.0  # 最新最終淨值
        cur_dd = max(0.0, peak - final_eq)  # 最新即時回撤美金
        cur_dd_pct = round(cur_dd / 100000.0 * 100, 2)  # 最新即時回撤百分比
        mdd_pct_val = round(max_dd / 100000.0 * 100, 2)  # 最大回撤百分比

        portfolio_metrics = {  # 組合總指標字典
            "total_trades": tot_trades, "winning_trades": tot_wins, "losing_trades": tot_trades - tot_wins,  # 筆數統計
            "win_rate": tot_wr, "total_net_pnl_usd": tot_pnl, "profit_factor": tot_pf,  # 勝率與損益
            "max_drawdown_usd": round(max_dd, 2), "max_drawdown_pct": mdd_pct_val,  # 最大回撤數值
            "max_drawdown_formatted": f"-${max_dd:,.2f} ({mdd_pct_val}%)",  # 最大回撤金額(%)格式化
            "current_drawdown_usd": round(cur_dd, 2), "current_drawdown_pct": cur_dd_pct,  # 目前回撤數值
            "current_drawdown_formatted": f"-${cur_dd:,.2f} ({cur_dd_pct}%)",  # 目前回撤金額(%)格式化
            "calmar_ratio": round(tot_pnl / (max_dd + 1e-9), 2), "initial_balance": 100000.0,  # 風險報酬與本金
            "final_equity": round(100000.0 + tot_pnl, 2), "last_updated": now_tpe.strftime('%Y-%m-%d %H:%M:%S')  # 最終淨值與時間
        }  # 結束

        # 生成商品中繼資料 (symbols_meta 供網頁即時報價卡片與過濾矩陣渲染)
        symbols_meta = {}  # 商品中繼資料字典
        for mod in self.modules:  # 遍歷模組
            sym = mod["symbol"]  # 品種名稱
            if sym not in symbols_meta:  # 若尚未計算
                f_name = f"pepperstone_{sym.lower()}_15m.csv" if os.path.exists(os.path.join(self.data_dir, f"pepperstone_{sym.lower()}_15m.csv")) else f"pepperstone_{sym.lower()}_1h.csv"  # 偏好 15M
                df_sym = pd.read_csv(os.path.join(self.data_dir, f_name))  # 讀取數據
                last_c = float(df_sym["close"].iloc[-1])  # 最新收盤價
                first_24h_c = float(df_sym["close"].iloc[-96]) if len(df_sym) >= 96 else float(df_sym["close"].iloc[0])  # 24H 前價格
                chg_pct = round((last_c - first_24h_c) / first_24h_c * 100, 2)  # 24H 漲跌幅
                
                ma20 = float(df_sym["close"].rolling(20).mean().iloc[-1])  # 最新 20 SMA
                std20 = float(df_sym["close"].rolling(20).std().iloc[-1])  # 最新 20 STD
                zscore = round((last_c - ma20) / (std20 + 1e-9), 2)  # 最新 Z-Score
                delta = df_sym["close"].diff()  # 差分
                gain = delta.where(delta > 0, 0).rolling(14).mean()  # 漲幅均值
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()  # 跌幅均值
                rsi = round(float((100 - (100 / (1 + (gain / (loss + 1e-9))))).iloc[-1]), 1)  # 最新 RSI
                
                digits = 3 if "JPY" in sym else 5  # 小數位數
                symbols_meta[sym] = {  # 儲存資訊
                    "symbol": sym,  # 標的名稱
                    "current_price": round(last_c, digits),  # 當前即時價格
                    "price_change_24h_pct": chg_pct,  # 24H 漲跌幅
                    "spread_pips": self.spreads.get(sym, 1.5),  # 實盤點差
                    "current_rsi": rsi,  # 當前 RSI
                    "current_zscore": zscore  # 當前 Z-Score
                }  # 字典結束

        system_info = {  # 系統資訊字典
            "version": "5.10 (汰弱留強精銳升級版)",  # 版本
            "last_updated_mt5": now_mt5.strftime('%Y-%m-%d %H:%M:%S'),  # MT5 時間
            "last_updated_tpe": now_tpe.strftime('%Y-%m-%d %H:%M:%S')  # 台北時間
        }  # 結束

        out_payload = {  # 輸出 JSON
            "system_version": "5.10 (汰弱留強精銳升級版)",  # 系統版本標籤
            "system_info": system_info,  # 系統時間資訊
            "portfolio_metrics": portfolio_metrics,
            "modules_summary": modules_summary,
            "symbols_meta": symbols_meta,  # 商品中繼字典
            "all_trades": all_completed_trades,
            "equity_curve": equity_series,
            "chart_data": chart_data_dict
        }  # 結束

        json_path = os.path.join(os.path.dirname(__file__), "strategy_results.json")  # JSON 路徑
        with open(json_path, "w", encoding="utf-8") as f:  # 寫入 JSON
            json.dump(out_payload, f, indent=2, ensure_ascii=False)  # 輸出
            
        csv_path = os.path.join(os.path.dirname(__file__), "all_trades_history.csv")  # CSV 路徑
        if all_completed_trades:  # 若有交易
            pd.DataFrame(all_completed_trades).to_csv(csv_path, index=False, encoding="utf-8-sig")  # 輸出 CSV

        print(f"✅ 數據成功更新！總淨利: ${tot_pnl:+,.2f} USD | 交易: {tot_trades} 筆 | 勝率: {tot_wr}% | PF: {tot_pf} | MDD: ${max_dd:,.2f} ({portfolio_metrics['max_drawdown_pct']}%) | Calmar: {portfolio_metrics['calmar_ratio']}")  # 提示

if __name__ == "__main__":  # 主入口
    engine = SchemeDOptionHarvestEngine()  # 實例化
    engine.execute_and_export()  # 執行更新
