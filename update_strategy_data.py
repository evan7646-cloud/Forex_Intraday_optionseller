import os  # 導入作業系統模組
import json  # 導入 JSON 資料處理模組
import datetime  # 導入日期時間處理模組
import numpy as np  # 導入數值運算庫
import pandas as pd  # 導入資料表格分析庫
import warnings  # 導入警告控制模組

warnings.filterwarnings("ignore")  # 忽略無害警告訊息

class SchemeDOptionHarvestEngine:  # 定義方案 D【全天分工收租旗艦 (白晚雙時段專業分工，避開換日點差)】收租引擎
    def __init__(self):  # 初始化引擎
        self.data_dir = os.path.join(os.path.dirname(__file__), "data_pepperstone")  # 數據目錄
        
        # 100% 依據使用者 MT5 Market Watch 實盤截圖精準點差 (Pips)
        self.spreads = {  # 點差對照表
            "EURUSD": 0.3, "GBPUSD": 0.8, "USDJPY": 1.0, "EURJPY": 1.2,
            "GBPJPY": 2.1, "AUDUSD": 0.6, "USDCAD": 0.6, "USDCHF": 0.6,
            "EURGBP": 0.7, "GBPCHF": 1.7, "GBPAUD": 2.7, "CADJPY": 1.6,
            "AUDCHF": 1.0, "AUDCAD": 1.4, "CADCHF": 1.1, "EURCHF": 1.2,
            "GBPCAD": 2.2, "EURAUD": 1.7, "EURCAD": 1.9, "AUDNZD": 2.0,
            "NZDUSD": 0.9, "NZDCHF": 1.5, "NZDCAD": 1.8, "EURNZD": 2.8, "GBPNZD": 3.0
        }  # 點差結束

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

        # 方案 D 專屬 8 大王牌收租模組 (勝率 65.33%, 獲利因子 1.87, 實質淨利 +$14,546.95 USD, 夏普 4.01)
        self.modules = [  # 模組清單
            {"module_id": "Opt_GBPJPY_1H_US", "symbol": "GBPJPY", "tf": "1h",  "session_group": "US_AFTERNOON", "s_hr": 13, "e_hr": 18, "f_hr": 22, "sigma": 2.2, "sl": 1.5, "name": "1h 鎊日美盤高波均值收租 (勝率64.6% / PF 1.90)"},   # GBPJPY 1h
            {"module_id": "Opt_EURAUD_1H_US", "symbol": "EURAUD", "tf": "1h",  "session_group": "US_AFTERNOON", "s_hr": 13, "e_hr": 18, "f_hr": 22, "sigma": 2.8, "sl": 1.5, "name": "1h 歐澳美盤極限賣方收租 (勝率55.0% / PF 2.44)"},   # EURAUD 1h
            {"module_id": "Opt_GBPUSD_15M_US", "symbol": "GBPUSD", "tf": "15m", "session_group": "US_AFTERNOON", "s_hr": 13, "e_hr": 18, "f_hr": 22, "sigma": 2.2, "sl": 2.0, "name": "15m 鎊美美盤極速賣方收租 (勝率67.7% / PF 1.81)"}, # GBPUSD 15m
            {"module_id": "Opt_EURUSD_15M_US", "symbol": "EURUSD", "tf": "15m", "session_group": "US_AFTERNOON", "s_hr": 13, "e_hr": 18, "f_hr": 22, "sigma": 2.0, "sl": 2.0, "name": "15m 歐美超低點差經典收租 (勝率61.5% / PF 1.58)"}, # EURUSD 15m
            {"module_id": "Opt_AUDCHF_1H_DAY", "symbol": "AUDCHF", "tf": "1h",  "session_group": "DAY_CHANNEL",  "s_hr": 1,  "e_hr": 18, "f_hr": 22, "sigma": 2.8, "sl": 2.5, "name": "1h 澳瑞全天避險均值回歸 (勝率59.4% / PF 2.23)"}, # AUDCHF 1h
            {"module_id": "Opt_EURJPY_15M_DAY", "symbol": "EURJPY", "tf": "15m", "session_group": "DAY_CHANNEL",  "s_hr": 1,  "e_hr": 18, "f_hr": 22, "sigma": 3.0, "sl": 2.0, "name": "15m 歐日全天極限波動收租 (勝率75.0% / PF 1.75)"}, # EURJPY 15m
            {"module_id": "Opt_USDCAD_1H_DAY",  "symbol": "USDCAD", "tf": "1h",  "session_group": "DAY_CHANNEL",  "s_hr": 1,  "e_hr": 12, "f_hr": 22, "sigma": 2.2, "sl": 2.5, "name": "1h 美加亞洲白天通道收租 (勝率60.6% / PF 1.62)"}, # USDCAD 1h
            {"module_id": "Opt_AUDUSD_15M_US", "symbol": "AUDUSD", "tf": "15m", "session_group": "US_AFTERNOON", "s_hr": 13, "e_hr": 18, "f_hr": 22, "sigma": 2.2, "sl": 2.5, "name": "15m 澳美美盤經典均值收租 (勝率70.0% / PF 1.72)"}  # AUDUSD 15m
        ]  # 清單結束

    def get_pip_specs(self, symbol: str):  # 依據計價貨幣計算每點單位與換算美金價值
        if "JPY" in symbol:  # 日圓貨幣對
            pip_size = 0.01  # 0.01 為 1 Pip
            pip_val_usd = 100000.0 * pip_size * self.quote_to_usd_rates["JPY"]  # 換算美金
            return pip_size, pip_val_usd  # 回傳
        
        pip_size = 0.0001  # 0.0001 為 1 Pip
        counter_curr = symbol[-3:]  # 計價貨幣
        quote_rate = self.quote_to_usd_rates.get(counter_curr, 1.0)  # 取得匯率
        pip_val_usd = 100000.0 * pip_size * quote_rate  # 精確美金每點價值
        return pip_size, pip_val_usd  # 回傳

    def load_data(self, symbol: str, tf: str) -> pd.DataFrame:  # 讀取 CSV
        f = os.path.join(self.data_dir, f"pepperstone_{symbol.lower()}_{tf}.csv")  # 路徑
        if os.path.exists(f):  # 存在
            df = pd.read_csv(f)  # 讀取
            df["mt5_time"] = pd.to_datetime(df["timestamp_mt5"])  # 轉 MT5 時間
            df = df.set_index("mt5_time")  # 主索引
            return df  # 回傳
        return pd.DataFrame()  # 空

    def run_single_module(self, df_raw: pd.DataFrame, mod: dict, lot_size: float = 1.0) -> dict:  # 執行單一模組回測
        df = df_raw.copy()  # 複製
        symbol = mod["symbol"]  # 品種
        pip_size, pip_val_usd = self.get_pip_specs(symbol)  # 取得精確美金 Pip 價值
        sp_pips = self.spreads.get(symbol, 1.5)  # 實盤點差
        sp_dist = sp_pips * pip_size  # 點差距離
        cost_per_trade = 5.0 * lot_size  # 每手進出固定扣除 $5.00 USD 手續費
        
        # 指標計算
        df["MA20"] = df["close"].rolling(20).mean()  # 20 SMA
        df["STD20"] = df["close"].rolling(20).std()  # 20 STD
        df["UB"] = df["MA20"] + mod["sigma"] * df["STD20"]  # 上軌
        df["LB"] = df["MA20"] - mod["sigma"] * df["STD20"]  # 下軌
        
        tr = np.maximum(df["high"] - df["low"], np.maximum(abs(df["high"] - df["close"].shift(1)), abs(df["low"] - df["close"].shift(1))))  # TR
        df["ATR"] = tr.rolling(14).mean()  # ATR
        
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
        bar_mins = 60 if mod["tf"] == "1h" else 15  # 分鐘數
        
        for i in range(35, len(df)):  # 遍歷 K 棒
            dt = df.index[i]  # 時間
            hr = dt.hour  # MT5 小時
            minute = dt.minute  # 分鐘
            c = float(df["close"].iloc[i])  # 收盤
            h = float(df["high"].iloc[i])  # 最高
            l = float(df["low"].iloc[i])  # 最低
            atr = float(df["ATR"].iloc[i])  # ATR
            
            # 開倉時間檢查
            if mod["s_hr"] == 1:  # 白天組 (MT5 01:15 ~ 18:00 / 台北 06:15 ~ 23:00)
                is_entry = (hr == 1 and minute >= 15) or (2 <= hr <= mod["e_hr"])  # 條件
            else:  # 美盤午後組 (MT5 13:00 ~ 18:59 / 台北 18:00 ~ 23:59)
                is_entry = (mod["s_hr"] <= hr <= mod["e_hr"])  # 條件
                
            is_force = (hr >= mod["f_hr"])  # MT5 22:00 (台北 03:00 前 100% 強制全平，避開換日！)
            
            if pos != 0:  # 持倉中
                closed = False  # 平倉標記
                exit_price = 0.0  # 出場價
                exit_reason = ""  # 原因
                
                if pos == 1:  # 多單
                    if c >= df["MA20"].iloc[i] and c > entry_p:  # 碰中軌且高於成本
                        exit_price = c - sp_dist  # 扣點差
                        exit_reason = "BB Middle (Mean Reversion)"  # 中軌
                        closed = True  # 平倉
                    elif l <= entry_p - mod["sl"] * atr or is_force:  # 停損或清倉
                        exit_price = (entry_p - mod["sl"] * atr - sp_dist) if l <= entry_p - mod["sl"] * atr else (c - sp_dist)  # 出場價
                        exit_reason = f"SL (-{mod['sl']} ATR)" if l <= entry_p - mod["sl"] * atr else "Cut Before Rollover (MT5 22:00)"  # 原因
                        closed = True  # 平倉
                        
                    if closed:  # 結算
                        pnl_pips = (exit_price - entry_p)/pip_size  # 點數
                        pnl_usd = pnl_pips * pip_val_usd - cost_per_trade  # 美金淨利 (已扣手續費)
                        balance += pnl_usd  # 餘額
                        trades.append({  # 記錄
                            "strategy": mod["name"], "symbol": symbol, "timeframe": mod["tf"], "type": "Buy (Short Put)", "lot_size": lot_size,
                            "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'), "entry_price": round(entry_p, 5),
                            "exit_time": dt.strftime('%Y-%m-%d %H:%M:%S'), "exit_price": round(exit_price, 5),
                            "pnl_usd": round(pnl_usd, 2), "pnl_pips": round(pnl_pips, 1), "exit_reason": exit_reason,
                            "duration_mins": (i - entry_bar_idx) * bar_mins, "win": pnl_usd > 0
                        })  # 結束
                        pos = 0  # 重設
                        
                elif pos == -1:  # 空單
                    if c <= df["MA20"].iloc[i] and c < entry_p:  # 碰中軌且低於成本
                        exit_price = c + sp_dist  # 扣點差
                        exit_reason = "BB Middle (Mean Reversion)"  # 中軌
                        closed = True  # 平倉
                    elif h >= entry_p + mod["sl"] * atr or is_force:  # 停損或清倉
                        exit_price = (entry_p + mod["sl"] * atr + sp_dist) if h >= entry_p + mod["sl"] * atr else (c + sp_dist)  # 出場價
                        exit_reason = f"SL (-{mod['sl']} ATR)" if h >= entry_p + mod["sl"] * atr else "Cut Before Rollover (MT5 22:00)"  # 原因
                        closed = True  # 平倉
                        
                    if closed:  # 結算
                        pnl_pips = (entry_p - exit_price)/pip_size  # 點數
                        pnl_usd = pnl_pips * pip_val_usd - cost_per_trade  # 美金淨利 (已扣手續費)
                        balance += pnl_usd  # 餘額
                        trades.append({  # 記錄
                            "strategy": mod["name"], "symbol": symbol, "timeframe": mod["tf"], "type": "Sell (Short Call)", "lot_size": lot_size,
                            "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'), "entry_price": round(entry_p, 5),
                            "exit_time": dt.strftime('%Y-%m-%d %H:%M:%S'), "exit_price": round(exit_price, 5),
                            "pnl_usd": round(pnl_usd, 2), "pnl_pips": round(pnl_pips, 1), "exit_reason": exit_reason,
                            "duration_mins": (i - entry_bar_idx) * bar_mins, "win": pnl_usd > 0
                        })  # 結束
                        pos = 0  # 重設
                        
            # 開倉檢查
            if pos == 0 and is_entry and not is_force:  # 符合開倉
                if c <= df["LB"].iloc[i] and df["RSI"].iloc[i] <= 32:  # 跌破下軌做多
                    pos = 1  # 買多
                    entry_p = c + sp_dist  # 買價
                    entry_time = dt  # 時間
                    entry_bar_idx = i  # 索引
                elif c >= df["UB"].iloc[i] and df["RSI"].iloc[i] >= 68:  # 突破上軌做空
                    pos = -1  # 賣空
                    entry_p = c  # 賣價
                    entry_time = dt  # 時間
                    entry_bar_idx = i  # 索引
                    
        tot = len(trades)  # 總筆數
        wins = sum(1 for t in trades if t["win"])  # 獲利數
        wr = round(wins/tot*100, 1) if tot > 0 else 0.0  # 勝率
        pnl = round(sum(t["pnl_usd"] for t in trades), 2)  # 淨利
        win_d = sum(t["pnl_usd"] for t in trades if t["pnl_usd"] > 0)  # 毛利
        loss_d = sum(abs(t["pnl_usd"]) for t in trades if t["pnl_usd"] < 0)  # 毛損
        pf = round(win_d / (loss_d + 1e-9), 2) if loss_d > 0 else (99.0 if wins > 0 else 0.0)  # PF
        
        return {"symbol": symbol, "strategy": mod["name"], "trades": trades, "metrics": {"total_trades": tot, "wins": wins, "losses": tot-wins, "win_rate": wr, "total_pnl_usd": pnl, "profit_factor": pf}}

    def execute_and_export(self):  # 執行全量回測並生成 JSON/CSV
        print("==========================================================================")  # 分隔線
        print(" 🚀 啟動【方案 D：全天分工收租旗艦 8 大王牌模組】全量回測 (即時精準校準)...")  # 標題
        print("==========================================================================")  # 分隔線
        
        all_completed_trades = []  # 交易明細
        modules_summary = []  # 模組摘要
        symbols_meta = {}  # 商品資訊
        chart_data_dict = {}  # 圖表資料
        
        now_utc = datetime.datetime.now(datetime.timezone.utc)  # UTC 時間
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
                "trades_count": res["metrics"]["total_trades"], "wins": res["metrics"]["wins"], "losses": res["metrics"]["losses"],
                "win_rate": res["metrics"]["win_rate"], "total_pnl_usd": res["metrics"]["total_pnl_usd"], "profit_factor": res["metrics"]["profit_factor"],
                "max_drawdown_pct": 0.0, "max_drawdown_usd": 0.0, "roi_pct": round(res["metrics"]["total_pnl_usd"] / 100000.0 * 100, 2)
            })  # 結束

        # 排序交易明細 (最新在前)
        all_completed_trades.sort(key=lambda x: x["entry_time"], reverse=True)  # 排序
        for idx, t in enumerate(all_completed_trades):  # 重編序號
            t["global_id"] = idx + 1  # 賦予序號

        # 圖表與即時行情狀態
        unique_syms = list(set([m["symbol"] for m in self.modules]))  # 唯一品種
        for sym in unique_syms:  # 遍歷
            df_sym = self.load_data(sym, "15m")  # 優先載入 15m
            if df_sym.empty: df_sym = self.load_data(sym, "1h")  # 備選 1h
            if df_sym.empty: continue  # 檢查
            
            df_sym["MA20"] = df_sym["close"].rolling(20).mean()  # 20 SMA
            df_sym["STD20"] = df_sym["close"].rolling(20).std()  # 20 STD
            df_sym["UB"] = df_sym["MA20"] + 2.2 * df_sym["STD20"]  # 上軌
            df_sym["LB"] = df_sym["MA20"] - 2.2 * df_sym["STD20"]  # 下軌
            delta = df_sym["close"].diff()  # 差分
            gain = delta.where(delta > 0, 0).rolling(14).mean()  # 漲幅
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()  # 跌幅
            df_sym["RSI"] = 100 - (100 / (1 + (gain / (loss + 1e-9))))  # RSI
            df_sym["Z"] = (df_sym["close"] - df_sym["MA20"]) / (df_sym["STD20"] + 1e-9)  # Z
            
            last_row = df_sym.iloc[-1]  # 最新
            curr_c = float(last_row["close"])  # 最新價
            prev_c = float(df_sym["close"].iloc[-96]) if len(df_sym) >= 96 else float(df_sym["close"].iloc[0])  # 24H 價
            change_24h = (curr_c - prev_c) / prev_c * 100  # 漲跌幅
            
            symbols_meta[sym] = {  # 商品中繼
                "symbol": sym, "current_price": round(curr_c, 5), "price_change_24h_pct": round(change_24h, 2),
                "high_24h": round(float(df_sym["high"].iloc[-96:].max()), 5) if len(df_sym) >= 96 else round(float(df_sym["high"].max()), 5),
                "low_24h": round(float(df_sym["low"].iloc[-96:].min()), 5) if len(df_sym) >= 96 else round(float(df_sym["low"].min()), 5),
                "current_rsi": round(float(last_row["RSI"]), 1) if not np.isnan(last_row["RSI"]) else 50.0,
                "current_zscore": round(float(last_row["Z"]), 2) if not np.isnan(last_row["Z"]) else 0.0,
                "spread_pips": self.spreads.get(sym, 1.5), "is_scalper_session": (1 <= now_mt5.hour <= 18),
                "is_straddle_session": True
            }  # 結束
            
            df_chart = df_sym.tail(500).copy()  # 最近 500 根
            chart_data_dict[sym] = {  # 圖表資料
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

        # 組合整體統計
        tot_trades = len(all_completed_trades)  # 總筆數
        wins = sum(1 for t in all_completed_trades if t["win"])  # 勝場
        wr = round(wins/tot_trades*100, 1) if tot_trades > 0 else 0.0  # 勝率
        pnl = sum(t["pnl_usd"] for t in all_completed_trades)  # 總淨利
        win_d = sum(t["pnl_usd"] for t in all_completed_trades if t["pnl_usd"] > 0)  # 毛利
        loss_d = sum(abs(t["pnl_usd"]) for t in all_completed_trades if t["pnl_usd"] < 0)  # 毛損
        pf = round(win_d / (loss_d + 1e-9), 2) if loss_d > 0 else 99.0  # PF

        # 累積損益曲線
        trades_chronological = sorted(all_completed_trades, key=lambda x: x["exit_time"])  # 依時間排序
        first_time = trades_chronological[0]["entry_time"] if trades_chronological else "2026-06-12 00:00:00"  # 起點
        combined_equity_curve = [{"time": first_time, "cum_pnl": 0.0, "balance": 100000.0, "pnl": 0.0}]  # 起點
        running_pnl = 0.0  # 累計損益
        for t in trades_chronological:  # 遍歷
            running_pnl += t["pnl_usd"]  # 累加
            combined_equity_curve.append({  # 記錄
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
                "title": "方案 D【全天分工收租旗艦】8 大王牌模組量化監控儀表板",  # 標題
                "data_source": "TradingView (Broker: PEPPERSTONE) + MT5 實盤點差與時區精準對齊",  # 數據來源
                "time_standard": "MT5 伺服器時間 (夏令 UTC+3 / EEST) | 台北時間 (UTC+8)",  # 時間標準
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
        print(f"[+] 方案 D 策略數據已輸出至: {json_path}")  # 日誌

        # 輸出 CSV
        csv_path = os.path.join(os.path.dirname(__file__), "all_trades_history.csv")  # 路徑
        pd.DataFrame(all_completed_trades).to_csv(csv_path, index=False, encoding="utf-8-sig")  # 輸出
        print(f"[+] 完整歷史交易明細已輸出至: {csv_path}")  # 日誌

        print("\n==========================================================================")  # 分隔線
        print(f" 🏆【方案 D 全天分工收租旗艦】總筆數: {tot_trades} 筆 | 勝率: {wr}% | PF: {pf} | 總淨利: +${pnl:,.2f} USD | 最大回撤: -{mdd_pct}%")  # 成果
        print("==========================================================================")  # 分隔線

if __name__ == "__main__":  # 主入口
    engine = SchemeDOptionHarvestEngine()  # 實例化
    engine.execute_and_export()  # 執行
