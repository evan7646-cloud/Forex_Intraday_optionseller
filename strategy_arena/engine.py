import os  # 匯入作業系統模組以處理資料庫檔案路徑
import sys  # 匯入系統模組
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 將專案根目錄加入模組搜尋路徑
import numpy as np  # 匯入 numpy 進行高效能矩陣運算與回測撮合
import pandas as pd  # 匯入 pandas 處理時間序列與交易報表
from strategy_arena.base import BaseOptionSellerStrategy  # 匯入策略外掛統一基類

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data_pepperstone")  # 定義 Pepperstone 數據資料庫根目錄

SPREADS = {  # 定義 28 大品種之實盤點差表 (Pips)
    "EURUSD": 0.3, "GBPUSD": 0.8, "USDJPY": 1.0, "EURJPY": 1.2,  # 歐美與日圓直盤點差
    "GBPJPY": 2.1, "AUDUSD": 0.6, "USDCAD": 0.6, "USDCHF": 0.6,  # 鎊日與美系直盤點差
    "EURGBP": 0.7, "GBPCHF": 1.7, "GBPAUD": 2.7, "CADJPY": 1.6,  # 歐鎊與英鎊交叉點差
    "AUDCHF": 1.0, "AUDCAD": 1.4, "CADCHF": 1.1, "EURCHF": 1.2,  # 澳瑞與瑞郎交叉點差
    "GBPCAD": 2.2, "EURAUD": 1.7, "EURCAD": 1.9, "AUDNZD": 2.0,  # 歐澳與澳紐交叉點差
    "NZDUSD": 0.9, "NZDCHF": 1.5, "NZDCAD": 1.8, "EURNZD": 2.8, "GBPNZD": 3.0,  # 紐幣與歐紐點差
    "CHFJPY": 1.5, "AUDJPY": 1.9, "NZDJPY": 1.8  # 瑞日與大洋洲日圓交叉點差
}  # 點差設定結束

QUOTE_TO_USD_RATES = {  # MT5 實盤計價幣別對美金即時匯率換算表
    "USD": 1.00000,                  # 美金面值 $1.00000
    "CHF": 1.0 / 0.80218,            # 1 CHF = $1.24660 USD (每手每點 = $12.47 USD)
    "GBP": 1.36386,                  # 1 GBP = $1.36386 USD (每手每點 = $13.64 USD)
    "CAD": 1.0 / 1.38452,            # 1 CAD = $0.72227 USD (每手每點 = $7.22 USD)
    "JPY": 1.0 / 159.178,            # 1 JPY = $0.006282 USD (每手每點 = $6.28 USD)
    "AUD": 0.71000,                  # 1 AUD = $0.71000 USD (每手每點 = $7.10 USD)
    "NZD": 0.60000                   # 1 NZD = $0.60000 USD (每手每點 = $6.00 USD)
}  # 匯率表結束

CORE_MODULES = [  # 方案 A 全天分工收租旗艦 8 大王牌核心模組清單 (v5.10 汰弱留強精銳版)
    # === 🌙 US_AFTERNOON 美盤午後 (4 組) ===
    {"module_id": "Opt_GBPJPY_1H_US",   "symbol": "GBPJPY", "tf": "1h",  "session_group": "US_AFTERNOON", "s_hr": 13, "e_hr": 18, "f_hr": 22, "sigma": 2.2, "sl": 1.5, "name": "1h 鎊日美盤高波收租"},   # GBPJPY 1h 美盤王牌
    {"module_id": "Opt_EURJPY_1H_US",   "symbol": "EURJPY", "tf": "1h",  "session_group": "US_AFTERNOON", "s_hr": 13, "e_hr": 18, "f_hr": 22, "sigma": 2.5, "sl": 1.5, "name": "1h 歐日美盤波動收租"},   # EURJPY 1h 美盤
    {"module_id": "Opt_GBPUSD_15M_US",  "symbol": "GBPUSD", "tf": "15m", "session_group": "US_AFTERNOON", "s_hr": 13, "e_hr": 18, "f_hr": 22, "sigma": 2.2, "sl": 2.0, "name": "15m 鎊美美盤極速收租"},   # GBPUSD 15m 美盤
    {"module_id": "Opt_EURCAD_1H_US",   "symbol": "EURCAD", "tf": "1h",  "session_group": "US_AFTERNOON", "s_hr": 13, "e_hr": 18, "f_hr": 22, "sigma": 3.0, "sl": 2.0, "name": "1h 歐加美盤高盈虧收租"},   # 🆕 EURCAD 1h 美盤 (取代 EURNZD/EURUSD)
    # === ☀️ DAY_CHANNEL 白天全天通道 (4 組) ===
    {"module_id": "Opt_EURJPY_15M_DAY",  "symbol": "EURJPY", "tf": "15m", "session_group": "DAY_CHANNEL",  "s_hr": 1,  "e_hr": 18, "f_hr": 22, "sigma": 3.0, "sl": 2.0, "name": "15m 歐日白天極限收租"},   # EURJPY 15m 白天
    {"module_id": "Opt_AUDCHF_1H_DAY",   "symbol": "AUDCHF", "tf": "1h",  "session_group": "DAY_CHANNEL",  "s_hr": 1,  "e_hr": 18, "f_hr": 22, "sigma": 2.8, "sl": 2.5, "name": "1h 澳瑞全天避險收租"},   # AUDCHF 1h 白天
    {"module_id": "Opt_AUDUSD_1H_DAY",   "symbol": "AUDUSD", "tf": "1h",  "session_group": "DAY_CHANNEL",  "s_hr": 1,  "e_hr": 18, "f_hr": 22, "sigma": 3.0, "sl": 2.0, "name": "1h 澳美白天低點差收租"},   # 🆕 AUDUSD 1h 白天
    {"module_id": "Opt_GBPJPY_15M_DAY",  "symbol": "GBPJPY", "tf": "15m", "session_group": "DAY_CHANNEL",  "s_hr": 1,  "e_hr": 18, "f_hr": 22, "sigma": 2.8, "sl": 2.5, "name": "15m 鎊日白天波動收租"}    # 🆕 GBPJPY 15m 白天 (取代 CHFJPY)
]  # 模組清單結束

def get_pip_specs(symbol: str):  # 依據計價幣計算點值大小與 1 手每點美元價值
    if "JPY" in symbol:  # 日圓相關貨幣對
        pip_size = 0.01  # 日圓貨幣對 0.01 為 1 Pip
        pip_val_usd = 100000.0 * pip_size * QUOTE_TO_USD_RATES["JPY"]  # 換算為 USD 面值
        return pip_size, pip_val_usd  # 回傳規格
    pip_size = 0.0001  # 標準貨幣對 0.0001 為 1 Pip
    counter_curr = symbol[-3:]  # 提取最後 3 碼計價幣
    quote_rate = QUOTE_TO_USD_RATES.get(counter_curr, 1.0)  # 取得即時匯率
    pip_val_usd = 100000.0 * pip_size * quote_rate  # 計算精確 USD 價值
    return pip_size, pip_val_usd  # 回傳規格

def compute_technical_indicators(df: pd.DataFrame, mod: dict) -> pd.DataFrame:  # 全特徵擴展函數
    df = df.copy()  # 複製資料表
    df["MA20"] = df["close"].rolling(20).mean()  # 計算 20 週期均線
    df["STD20"] = df["close"].rolling(20).std()  # 計算 20 週期標準差
    df["UB"] = df["MA20"] + mod["sigma"] * df["STD20"]  # 計算布林上軌
    df["LB"] = df["MA20"] - mod["sigma"] * df["STD20"]  # 計算布林下軌
    
    tr = np.maximum(df["high"] - df["low"], np.maximum(abs(df["high"] - df["close"].shift(1)), abs(df["low"] - df["close"].shift(1))))  # TR
    df["ATR"] = tr.rolling(14).mean()  # 14 週期 ATR
    
    delta = df["close"].diff()  # 價格一階差分
    gain = delta.where(delta > 0, 0).rolling(14).mean()  # 滑動平均漲幅
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()  # 滑動平均跌幅
    df["RSI"] = 100 - (100 / (1 + (gain / (loss + 1e-9))))  # 14 週期 RSI
    df["RSI_PREV"] = df["RSI"].shift(1)  # 前一期 RSI 數值
    
    df["EMA50"] = df["close"].ewm(span=50).mean()  # 50 EMA
    df["EMA200"] = df["close"].ewm(span=200).mean()  # 200 EMA
    
    plus_dm = np.where((df["high"].diff() > -df["low"].diff()) & (df["high"].diff() > 0), df["high"].diff(), 0.0)  # +DM
    minus_dm = np.where((-df["low"].diff() > df["high"].diff()) & (-df["low"].diff() > 0), -df["low"].diff(), 0.0)  # -DM
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(14).mean() / (df["ATR"] + 1e-9))  # +DI
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(14).mean() / (df["ATR"] + 1e-9))  # -DI
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9))  # DX
    df["ADX"] = dx.rolling(14).mean()  # 14 週期 ADX
    
    df["BB_WIDTH"] = (df["UB"] - df["LB"]) / (df["MA20"] + 1e-9)  # 布林帶寬
    df["BB_WIDTH_MA"] = df["BB_WIDTH"].rolling(20).mean()  # 帶寬均線
    df["BB_WIDTH_RATIO"] = df["BB_WIDTH"] / (df["BB_WIDTH_MA"] + 1e-9)  # 帶寬比率
    
    candle_range = (df["high"] - df["low"]) + 1e-9  # K 棒全距
    df["LOWER_WICK_RATIO"] = (np.minimum(df["open"], df["close"]) - df["low"]) / candle_range  # 下影線佔比
    df["UPPER_WICK_RATIO"] = (df["high"] - np.maximum(df["open"], df["close"])) / candle_range  # 上影線佔比
    
    return df  # 回傳完整特徵表

_DATA_CACHE = {}  # 全域資料快取以極大化競技場執行速度

def load_cached_market_data() -> dict:  # 載入並快取 8 大模組市場數據
    global _DATA_CACHE  # 使用全域快取變數
    if len(_DATA_CACHE) > 0:  # 若已有快取
        return _DATA_CACHE  # 直接回傳快取
    for mod in CORE_MODULES:  # 遍歷 8 大模組
        f = os.path.join(DATA_DIR, f"pepperstone_{mod['symbol'].lower()}_{mod['tf']}.csv")  # 檔案路徑
        if not os.path.exists(f):  # 若檔案不存在
            continue  # 跳過
        raw_df = pd.read_csv(f)  # 讀取 CSV
        raw_df["mt5_time"] = pd.to_datetime(raw_df["timestamp_mt5"])  # 轉換時間格式
        raw_df = raw_df.set_index("mt5_time")  # 設定時間為索引
        df_feat = compute_technical_indicators(raw_df, mod)  # 計算全套指標
        _DATA_CACHE[mod["module_id"]] = (mod, df_feat)  # 寫入快取
    return _DATA_CACHE  # 回傳快取

def backtest_option_seller_strategy(strategy: BaseOptionSellerStrategy, market_data: dict = None) -> dict:  # 競技場專屬回測執行函數
    if market_data is None:  # 若未傳入數據
        market_data = load_cached_market_data()  # 自動載入
    all_trades = []  # 完結交易清單
    module_summaries = []  # 各模組細項清單
    
    for mod_id, (mod, raw_df) in market_data.items():  # 遍歷各模組
        df = strategy.prepare_indicators(raw_df.copy(), mod)  # 呼叫外掛指標擴展鉤子
        symbol = mod["symbol"]  # 品種名稱
        pip_size, pip_val_usd = get_pip_specs(symbol)  # 取得 Pip 規格
        sp_pips = SPREADS.get(symbol, 1.5)  # 點差點數
        sp_dist = sp_pips * pip_size  # 點差價格距離
        
        pos = 0  # 倉位 (0: 空手, 1: 多單, -1: 空單)
        entry_p = 0.0  # 開倉價格
        entry_idx = 0  # 開倉 K 棒索引
        entry_time = None  # 開倉時間
        lot_size = 1.0  # 基礎下單手數
        
        mod_trades = []  # 單模組交易清單
        
        for i in range(35, len(df)):  # 逐根 K 棒撮合
            dt = df.index[i]  # 當前時間
            hr = dt.hour  # 當前小時
            minute = dt.minute  # 當前分鐘
            c = float(df["close"].iloc[i])  # 當前收盤價
            h = float(df["high"].iloc[i])  # 當前最高價
            l = float(df["low"].iloc[i])  # 當前最低價
            atr = float(df["ATR"].iloc[i])  # 當前 ATR 數值
            row = df.iloc[i]  # 當前列資料物件
            
            if mod["s_hr"] == 1:  # 白天時段開倉判定 (MT5 01:15 ~ 18:00)
                is_entry_win = (hr == 1 and minute >= 15) or (2 <= hr <= mod["e_hr"])  # 條件
            else:  # 美盤時段開倉判定 (MT5 13:00 ~ 18:59)
                is_entry_win = (mod["s_hr"] <= hr <= mod["e_hr"])  # 條件
                
            is_force = (hr >= mod["f_hr"] or hr == 0)  # MT5 22:00~00:59 強制清倉離場
            
            if pos != 0:  # 持倉管理中
                closed = False  # 平倉標記
                exit_price = 0.0  # 出場價格
                exit_reason = ""  # 出場原因
                bars_held = i - entry_idx  # 持有 K 棒數
                
                curr_sl_dist = mod["sl"] * atr  # 基準停損距離
                # 呼叫外掛出場調制鉤子 (例如時間衰減或階梯收緊)
                curr_sl_dist = strategy.filter_exit(row, pos, entry_p, curr_sl_dist, bars_held, mod)  # 調制停損
                cost_per_trade = 5.0 * lot_size  # 計算每手 $5.00 手續費
                
                if pos == 1:  # 多單
                    if c >= df["MA20"].iloc[i] and c > entry_p:  # 價格回歸中軌且獲利
                        exit_price = c - sp_dist  # 扣除點差平倉
                        exit_reason = "BB Middle (Mean Reversion)"  # 原因
                        closed = True  # 平倉
                    elif l <= entry_p - curr_sl_dist or is_force:  # 觸及停損或時間強制全平
                        exit_price = (entry_p - curr_sl_dist - sp_dist) if l <= entry_p - curr_sl_dist else (c - sp_dist)  # 出場價
                        exit_reason = "ATR Hard SL" if l <= entry_p - curr_sl_dist else "Cut Before Rollover (22:00)"  # 原因
                        closed = True  # 平倉
                        
                    if closed:  # 結算多單
                        pnl_pips = (exit_price - entry_p) / pip_size  # 點數
                        pnl_usd = pnl_pips * pip_val_usd - cost_per_trade  # 美金淨利 (扣除手續費)
                        trade_rec = {  # 紀錄字典
                            "strategy": strategy.name, "module_id": mod["module_id"], "group": mod["session_group"],
                            "symbol": symbol, "type": "Buy (Short Put)", "entry_time": entry_time,
                            "exit_time": dt, "entry_price": entry_p, "exit_price": exit_price,
                            "pnl_usd": round(pnl_usd, 2), "pnl_pips": round(pnl_pips, 1),
                            "win": pnl_usd > 0, "exit_reason": exit_reason, "bars_held": bars_held
                        }  # 字典結束
                        all_trades.append(trade_rec)  # 寫入總表
                        mod_trades.append(trade_rec)  # 寫入模組表
                        pos = 0  # 重設倉位
                        
                elif pos == -1:  # 空單
                    if c <= df["MA20"].iloc[i] and c < entry_p:  # 價格回歸中軌且獲利
                        exit_price = c + sp_dist  # 加回點差平倉
                        exit_reason = "BB Middle (Mean Reversion)"  # 原因
                        closed = True  # 平倉
                    elif h >= entry_p + curr_sl_dist or is_force:  # 觸及停損或時間強制全平
                        exit_price = (entry_p + curr_sl_dist + sp_dist) if h >= entry_p + curr_sl_dist else (c + sp_dist)  # 出場價
                        exit_reason = "ATR Hard SL" if h >= entry_p + curr_sl_dist else "Cut Before Rollover (22:00)"  # 原因
                        closed = True  # 平倉
                        
                    if closed:  # 結算空單
                        pnl_pips = (entry_p - exit_price) / pip_size  # 點數
                        pnl_usd = pnl_pips * pip_val_usd - cost_per_trade  # 美金淨利 (扣除手續費)
                        trade_rec = {  # 紀錄字典
                            "strategy": strategy.name, "module_id": mod["module_id"], "group": mod["session_group"],
                            "symbol": symbol, "type": "Sell (Short Call)", "entry_time": entry_time,
                            "exit_time": dt, "entry_price": entry_p, "exit_price": exit_price,
                            "pnl_usd": round(pnl_usd, 2), "pnl_pips": round(pnl_pips, 1),
                            "win": pnl_usd > 0, "exit_reason": exit_reason, "bars_held": bars_held
                        }  # 字典結束
                        all_trades.append(trade_rec)  # 寫入總表
                        mod_trades.append(trade_rec)  # 寫入模組表
                        pos = 0  # 重設倉位
                        
            if pos == 0 and is_entry_win and not is_force:  # 開倉判定
                def_long = (c <= df["LB"].iloc[i] and df["RSI"].iloc[i] <= 32.0)  # 基準做多訊號
                def_short = (c >= df["UB"].iloc[i] and df["RSI"].iloc[i] >= 68.0)  # 基準做空訊號
                
                # 呼叫外掛進場過濾鉤子
                allow_long = strategy.filter_entry(row, is_long=True, default_signal=def_long, mod_info=mod)  # 多單過濾
                allow_short = strategy.filter_entry(row, is_long=False, default_signal=def_short, mod_info=mod)  # 空單過濾
                
                if allow_long:  # 執行做多開倉
                    pos = 1  # 設為多單部位
                    entry_p = c + sp_dist  # 以 Ask 價格成交
                    entry_idx = i  # 紀錄開倉索引
                    entry_time = dt  # 紀錄開倉時間
                    lot_size = strategy.calculate_lot_size(row, base_lot=1.0, mod_info=mod)  # 計算下單手數
                elif allow_short:  # 執行做空開倉
                    pos = -1  # 設為空單部位
                    entry_p = c - sp_dist  # 以 Bid 價格成交 (已扣除點差)
                    entry_idx = i  # 紀錄開倉索引
                    entry_time = dt  # 紀錄開倉時間
                    lot_size = strategy.calculate_lot_size(row, base_lot=1.0, mod_info=mod)  # 計算下單手數
                    
        # 計算單模組統計指標
        m_tot = len(mod_trades)  # 模組總筆數
        m_wins = sum(1 for t in mod_trades if t["win"])  # 獲利數
        m_wr = round(m_wins / m_tot * 100, 1) if m_tot > 0 else 0.0  # 勝率
        m_pnl = round(sum(t["pnl_usd"] for t in mod_trades), 2)  # 淨利
        m_win_d = sum(t["pnl_usd"] for t in mod_trades if t["pnl_usd"] > 0)  # 毛利
        m_loss_d = abs(sum(t["pnl_usd"] for t in mod_trades if t["pnl_usd"] < 0))  # 毛損
        m_pf = round(m_win_d / (m_loss_d + 1e-9), 2) if m_loss_d > 0 else (99.0 if m_wins > 0 else 0.0)  # PF
        module_summaries.append({  # 加入模組細項
            "module_id": mod["module_id"], "symbol": symbol, "group": mod["session_group"],
            "trades": m_tot, "win_rate": m_wr, "pf": m_pf, "pnl_usd": m_pnl
        })  # 結束
        
    tdf = pd.DataFrame(all_trades)  # 轉為總 DataFrame
    if len(tdf) == 0:  # 若無任何交易
        return {  # 回傳全零
            "name": strategy.name, "desc": strategy.description, "total_pnl": 0.0, "annual_pnl": 0.0,
            "trades": 0, "win_rate": 0.0, "pf": 0.0, "mdd_usd": 0.0, "mdd_pct": 0.0, "sharpe": 0.0,
            "calmar": 0.0, "expectancy": 0.0, "us_metrics": {}, "day_metrics": {},
            "module_summaries": module_summaries, "equity_curve": np.array([0.0]), "dates": []
        }  # 結束
        
    tdf = tdf.sort_values("exit_time").reset_index(drop=True)  # 依出場時間排序
    pnls = tdf["pnl_usd"].values  # 損益陣列
    eq = np.cumsum(pnls)  # 累積權益陣列
    mdd_usd = float(np.max(np.maximum.accumulate(eq) - eq))  # 最大回撤美金
    mdd_pct = round(mdd_usd / 100000.0 * 100, 2)  # 最大回撤佔 100K 帳戶百分比
    tot_pnl = round(pnls.sum(), 2)  # 總淨利
    wins = tdf[tdf["win"]]["pnl_usd"].sum()  # 總毛利
    loss = abs(tdf[~tdf["win"]]["pnl_usd"].sum())  # 總毛損
    pf = round(wins / (loss + 1e-9), 2) if loss > 0 else 99.0  # 組合獲利因子
    wr = round(len(tdf[tdf["win"]]) / len(tdf) * 100, 1)  # 組合勝率
    expectancy = round(tot_pnl / len(tdf), 2)  # 每筆期望值美金
    
    first_d = pd.to_datetime(tdf["entry_time"].min())  # 歷史首筆時間
    last_d = pd.to_datetime(tdf["exit_time"].max())  # 歷史末筆時間
    years = max((last_d - first_d).days / 365.25, 0.25)  # 統計年數
    annual_pnl = round(tot_pnl / years, 2)  # 年化獲利
    calmar = round(tot_pnl / (mdd_usd + 1e-9), 2)  # 卡瑪比率
    
    ret_std = pnls.std()  # 損益標準差
    sharpe = round(float((pnls.mean() / ret_std) * np.sqrt(252)), 2) if ret_std > 0 else 0.0  # 夏普比率
    
    # 子競技場拆解 (美盤 vs 白天)
    us_df = tdf[tdf["group"] == "US_AFTERNOON"]  # 美盤子表
    day_df = tdf[tdf["group"] == "DAY_CHANNEL"]  # 白天子表
    
    def calc_sub_group(sdf):  # 計算子時段群組統計
        if len(sdf) == 0: return {"trades": 0, "win_rate": 0.0, "pf": 0.0, "pnl_usd": 0.0, "mdd_usd": 0.0}  # 空表
        s_pnl = round(sdf["pnl_usd"].sum(), 2)  # 淨利
        s_wr = round(len(sdf[sdf["win"]]) / len(sdf) * 100, 1)  # 勝率
        s_w = sdf[sdf["win"]]["pnl_usd"].sum()  # 毛利
        s_l = abs(sdf[~sdf["win"]]["pnl_usd"].sum())  # 毛損
        s_pf = round(s_w / (s_l + 1e-9), 2) if s_l > 0 else 99.0  # PF
        s_eq = np.cumsum(sdf["pnl_usd"].values)  # 權益
        s_mdd = round(float(np.max(np.maximum.accumulate(s_eq) - s_eq)), 2)  # MDD
        return {"trades": len(sdf), "win_rate": s_wr, "pf": s_pf, "pnl_usd": s_pnl, "mdd_usd": s_mdd}  # 回傳
        
    us_metrics = calc_sub_group(us_df)  # 美盤指標
    day_metrics = calc_sub_group(day_df)  # 白天指標
    
    return {  # 回傳完整回測報告字典
        "name": strategy.name, "desc": strategy.description, "total_pnl": tot_pnl,  # 基礎資訊
        "annual_pnl": annual_pnl, "trades": len(tdf), "win_rate": wr, "pf": pf,  # 獲利指標
        "mdd_usd": mdd_usd, "mdd_pct": mdd_pct, "sharpe": sharpe, "calmar": calmar,  # 風控指標
        "expectancy": expectancy, "years": round(years, 2),  # 期望值與時間
        "us_metrics": us_metrics, "day_metrics": day_metrics,  # 子時段指標
        "module_summaries": module_summaries, "equity_curve": eq, "dates": pd.to_datetime(tdf["exit_time"])  # 曲線與明細
    }  # 字典結束
