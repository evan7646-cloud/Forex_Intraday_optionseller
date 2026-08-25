import os  # 導入作業系統模組
import json  # 導入 JSON 資料處理模組
import datetime  # 導入日期時間處理模組
import numpy as np  # 導入數值運算庫
import pandas as pd  # 導入資料表格分析庫
import warnings  # 導入警告過濾模組

warnings.filterwarnings("ignore")  # 忽略無害警告

class PureIntraday5mStrategyEngine:  # 定義純日內 5 分鐘策略回測與資料生成引擎 (以 PEPPERSTONE 5m 真實券商數據為基準)
    def __init__(self):  # 初始化引擎
        # 使用者指定之 5 大核心外匯貨幣對
        self.all_symbols = ["AUDCHF", "EURCHF", "AUDCAD", "USDCHF", "USDCAD"]  # 5 大精選貨幣對
        
        # 策略 1: 5 款夜間收租標的與專屬配置 (時段: MT5 00:00~07:00 開倉，MT5 09:00 強制清倉)
        self.scalper_configs = {  # 夜間收租配置表
            "AUDCHF": {"tp": 5.0, "sl": 35.0, "max_spread": 1.8},  # AUDCHF 配置
            "EURCHF": {"tp": 5.0, "sl": 35.0, "max_spread": 1.5},  # EURCHF 配置
            "AUDCAD": {"tp": 8.0, "sl": 40.0, "max_spread": 2.0},  # AUDCAD 配置
            "USDCHF": {"tp": 8.0, "sl": 40.0, "max_spread": 1.2},  # USDCHF 配置
            "USDCAD": {"tp": 8.0, "sl": 40.0, "max_spread": 1.2}   # USDCAD 配置
        }  # 結束
        
        # 策略 2: 3 款日間跨式賣方標的與專屬配置 (時段: MT5 09:00~22:00 開倉，MT5 23:00 強制清倉)
        self.straddle_configs = {  # 日間跨式賣方配置表
            "AUDCHF": {"z_in": 2.1, "z_out": 0.2, "z_stop": 3.8, "tp": 5.0, "sl": 35.0},  # AUDCHF 配置
            "AUDCAD": {"z_in": 2.1, "z_out": 0.2, "z_stop": 3.8, "tp": 8.0, "sl": 40.0},  # AUDCAD 配置
            "USDCAD": {"z_in": 2.1, "z_out": 0.2, "z_stop": 3.8, "tp": 5.0, "sl": 35.0}   # USDCAD 配置
        }  # 結束

        # 依使用者實盤截圖精確設定之平台點差 (Pips)
        self.platform_spreads = {  # 點差對照表
            "AUDCHF": 0.8,  # 8 pts
            "EURCHF": 0.6,  # 6 pts
            "AUDCAD": 1.1,  # 11 pts
            "USDCHF": 0.4,  # 4 pts
            "USDCAD": 0.4   # 4 pts
        }  # 結束

        self.data_dir = os.path.join(os.path.dirname(__file__), "data_pepperstone")  # PEPPERSTONE 數據目錄

    def get_pip_size(self, symbol: str) -> float:  # 取得 1 pip 最小價格單位
        return 0.01 if "JPY" in symbol else 0.0001  # JPY 貨幣對 1 pip = 0.01, 其餘 = 0.0001

    def get_pip_value_usd(self, symbol: str, lot_size: float = 1.0) -> float:  # 計算 1 pip 在 USD 的真實價值
        quote_usd_rates = {  # 報價貨幣轉 USD 的即時精確匯率對照表
            "USD": 1.0,        # 計價幣為 USD
            "CAD": 1.0/1.38,   # 計價幣為 CAD
            "CHF": 1.0/0.80,   # 計價幣為 CHF
            "JPY": 1.0/159.0,  # 計價幣為 JPY
            "GBP": 1.36,       # 計價幣為 GBP
            "NZD": 0.60,       # 計價幣為 NZD
            "AUD": 0.71        # 計價幣為 AUD
        }  # 匯率表結束
        base_pip = 100000.0 * self.get_pip_size(symbol)  # 1 標準手 1 pip 在計價幣的金額
        conversion = quote_usd_rates.get(symbol[-3:], 1.0)  # 取得對應美金轉換率
        return base_pip * conversion * lot_size  # 回傳每 pip 的美金價值

    def fetch_5m_data(self, symbol: str) -> pd.DataFrame:  # 優先從 PEPPERSTONE CSV 載入 5m K 線數據
        csv_filename = f"pepperstone_{symbol.lower()}_5m.csv"  # 檔名
        csv_path = os.path.join(self.data_dir, csv_filename)  # 完整路徑
        
        if os.path.exists(csv_path):  # 若 PEPPERSTONE CSV 存在
            try:  # 嘗試讀取
                df = pd.read_csv(csv_path)  # 讀取 CSV
                df['mt5_time'] = pd.to_datetime(df['timestamp_mt5'])  # 轉換為 datetime
                df = df.set_index('mt5_time')  # 以 MT5 時間為主索引
                df_clean = df[['open', 'high', 'low', 'close', 'volume']].dropna()  # 清理空值
                print(f"  [+] 成功載入 PEPPERSTONE TradingView 數據 [{symbol}]: {len(df_clean)} 根 5m K棒 (起: {df_clean.index[0]} ~ 訖: {df_clean.index[-1]})")  # 輸出成功日誌
                return df_clean  # 回傳資料表
            except Exception as e:  # 讀取異常
                print(f"  [!] 讀取 {csv_path} 失敗: {e}")  # 輸出錯誤
        
        # 若無本機 CSV 則印出提示
        print(f"  [!] 警告: 未找到 {csv_path}，請先執行 Download_dollar&Gold.py 下載！")  # 警告
        return pd.DataFrame()  # 回傳空表

    def run_scalper_strategy(self, symbol: str, df_raw: pd.DataFrame, cfg: dict, lot_size: float = 1.0) -> dict:  # 執行策略 1: 5m 亞洲夜間收租 (PEPPERSTONE MT5 數據)
        df = df_raw.copy()  # 複製原始數據
        df['MA'] = df['close'].rolling(20).mean()  # 計算 20 週期均線
        df['STD'] = df['close'].rolling(20).std()  # 計算 20 週期標準差
        df['UB'] = df['MA'] + 2.2 * df['STD']  # 計算布林上軌 (2.2倍標準差)
        df['LB'] = df['MA'] - 2.2 * df['STD']  # 計算布林下軌 (2.2倍標準差)

        delta = df['close'].diff()  # 計算價格差分
        gain = delta.where(delta > 0, 0).rolling(14).mean()  # 14 週期平均漲幅
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()  # 14 週期平均跌幅
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))  # 計算 RSI 指標

        pos = 0  # 倉位狀態 (1: 多, -1: 空, 0: 空手)
        entry_p = 0.0  # 進場價格
        entry_time = None  # 進場時間
        entry_bar_idx = 0  # 進場 K 棒索引
        balance = 100000.0  # 初始本金
        trades = []  # 交易記錄列表
        active_pos = None  # 當前即時活躍部位
        cost_per_trade = 5.0 * lot_size  # 單筆交易手續費 ($5 / 1.0 Lot)
        pip_size = self.get_pip_size(symbol)  # 取得商品最小 pip 單位
        pip_val_usd = self.get_pip_value_usd(symbol, lot_size)  # 取得每 pip 實際美金價值
        sp_pips = self.platform_spreads.get(symbol, 1.0)  # 實盤點差
        sp_dist = sp_pips * pip_size  # 點差價格距離
        tp_distance = cfg['tp'] * pip_size  # 止盈目標價差
        sl_distance = cfg['sl'] * pip_size  # 停損目標價差
        equity_records = []  # 權益曲線記錄

        for i in range(len(df)):  # 遍歷每根 5m K 棒
            dt = df.index[i]  # 當前時間 (MT5 伺服器時間)
            if i < 30:  # 預熱期
                equity_records.append({"time": dt.strftime('%Y-%m-%d %H:%M:%S'), "balance": balance})  # 記錄起始本金
                continue  # 跳過預熱
            c = float(df['close'].iloc[i])  # 收盤價
            h = float(df['high'].iloc[i])  # 最高價
            l = float(df['low'].iloc[i])  # 最低價
            hr = dt.hour  # 當前 MT5 伺服器小時
            
            # 純日內強制清倉：MT5 09:00 (歐盤前夕強制全平)
            is_force_exit = (hr == 9)  # 強制平倉觸發

            if pos != 0:  # 當前持有部位
                exit_price = 0.0  # 出場價格
                exit_reason = ""  # 出場原因
                is_closed = False  # 是否已結算平倉

                if pos == 1:  # 多單持倉 (Bid 賣出)
                    if h >= entry_p + tp_distance:  # 觸及止盈目標
                        exit_price = entry_p + tp_distance - sp_dist  # 扣點差出場
                        exit_reason = f"TP (+{cfg['tp']} pips)"  # 止盈原因標籤
                        is_closed = True  # 標記平倉
                    elif c >= df['MA'].iloc[i] and c > entry_p:  # 碰中軌且高於成本
                        exit_price = c - sp_dist  # 扣點差出場
                        exit_reason = "BB Middle (Mean Reversion)"  # 中軌原因
                        is_closed = True  # 標記平倉
                    elif l <= entry_p - sl_distance or is_force_exit:  # 觸及硬停損或時間清倉
                        exit_price = (entry_p - sl_distance - sp_dist) if l <= entry_p - sl_distance else (c - sp_dist)  # 出場價
                        exit_reason = f"SL (-{cfg['sl']} pips)" if l <= entry_p - sl_distance else "Zero-Overnight (MT5 09:00 強制清倉)"  # 原因
                        is_closed = True  # 標記平倉

                    if is_closed:  # 執行平倉結算
                        pnl_pips = (exit_price - entry_p) / pip_size  # 多單獲利點數 (pips)
                        pnl_dollars = pnl_pips * pip_val_usd - cost_per_trade  # 多單美金淨損益 (扣手續費)
                        ret_pct = (exit_price - entry_p) / entry_p * 100  # 計算報酬百分比
                        balance += pnl_dollars  # 更新帳戶餘額
                        duration_bars = i - entry_bar_idx  # 計算持倉 K 棒數
                        trades.append({  # 寫入歷史交易紀錄
                            "trade_id": len(trades) + 1,  # 交易序號
                            "strategy": "Asian Night Scalper (5m)",  # 策略名稱
                            "symbol": symbol,  # 貨幣對
                            "type": "Buy (Short Put)",  # 交易方向
                            "lot_size": lot_size,  # 下單手數
                            "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'),  # 進場時間 (MT5)
                            "entry_price": round(entry_p, 5),  # 進場價格
                            "exit_time": dt.strftime('%Y-%m-%d %H:%M:%S'),  # 出場時間 (MT5)
                            "exit_price": round(exit_price, 5),  # 出場價格
                            "pnl_usd": round(pnl_dollars, 2),  # 淨利 (USD)
                            "pnl_pips": round(pnl_pips, 1),  # 點數 (pips)
                            "return_pct": round(ret_pct, 3),  # 報酬率 (%)
                            "exit_reason": exit_reason,  # 平倉原因
                            "duration_bars": duration_bars,  # 持倉 K 棒數
                            "duration_mins": duration_bars * 5,  # 持倉分鐘數
                            "win": pnl_dollars > 0  # 是否獲利
                        })  # 結束單筆記錄
                        pos = 0  # 重設為空倉

                elif pos == -1:  # 空單持倉 (Ask 買回)
                    if l <= entry_p - tp_distance:  # 觸及止盈目標
                        exit_price = entry_p - tp_distance + sp_dist  # 扣點差出場
                        exit_reason = f"TP (+{cfg['tp']} pips)"  # 止盈原因標籤
                        is_closed = True  # 標記平倉
                    elif c <= df['MA'].iloc[i] and c < entry_p:  # 碰中軌且低於成本
                        exit_price = c + sp_dist  # 扣點差出場
                        exit_reason = "BB Middle (Mean Reversion)"  # 中軌原因
                        is_closed = True  # 標記平倉
                    elif h >= entry_p + sl_distance or is_force_exit:  # 觸及硬停損或時間清倉
                        exit_price = (entry_p + sl_distance + sp_dist) if h >= entry_p + sl_distance else (c + sp_dist)  # 出場價
                        exit_reason = f"SL (-{cfg['sl']} pips)" if h >= entry_p + sl_distance else "Zero-Overnight (MT5 09:00 強制清倉)"  # 原因
                        is_closed = True  # 標記平倉

                    if is_closed:  # 執行平倉結算
                        pnl_pips = (entry_p - exit_price) / pip_size  # 空單獲利點數 (pips)
                        pnl_dollars = pnl_pips * pip_val_usd - cost_per_trade  # 空單美金淨損益 (扣手續費)
                        ret_pct = (entry_p - exit_price) / entry_p * 100  # 計算報酬百分比
                        balance += pnl_dollars  # 更新帳戶餘額
                        duration_bars = i - entry_bar_idx  # 計算持倉 K 棒數
                        trades.append({  # 寫入歷史交易紀錄
                            "trade_id": len(trades) + 1,  # 交易序號
                            "strategy": "Asian Night Scalper (5m)",  # 策略名稱
                            "symbol": symbol,  # 貨幣對
                            "type": "Sell (Short Call)",  # 交易方向
                            "lot_size": lot_size,  # 下單手數
                            "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'),  # 進場時間 (MT5)
                            "entry_price": round(entry_p, 5),  # 進場價格
                            "exit_time": dt.strftime('%Y-%m-%d %H:%M:%S'),  # 出場時間 (MT5)
                            "exit_price": round(exit_price, 5),  # 出場價格
                            "pnl_usd": round(pnl_dollars, 2),  # 淨利 (USD)
                            "pnl_pips": round(pnl_pips, 1),  # 點數 (pips)
                            "return_pct": round(ret_pct, 3),  # 報酬率 (%)
                            "exit_reason": exit_reason,  # 平倉原因
                            "duration_bars": duration_bars,  # 持倉 K 棒數
                            "duration_mins": duration_bars * 5,  # 持倉分鐘數
                            "win": pnl_dollars > 0  # 是否獲利
                        })  # 結束單筆記錄
                        pos = 0  # 重設為空倉

            # 檢查進場訊號 (MT5 伺服器時間 00:00 ~ 07:00 夜間窗口)
            is_entry_session = (hr == 0 or 1 <= hr <= 7) and not is_force_exit  # MT5 伺服器夜間時段
            if pos == 0 and is_entry_session:  # 符合開倉時間窗口
                if c <= df['LB'].iloc[i] and df['RSI'].iloc[i] <= 35:  # 跌破下軌且 RSI 超賣
                    pos = 1  # 開多單
                    entry_p = c + sp_dist  # 買在 Ask (加點差)
                    entry_time = dt  # 記錄進場時間 (MT5)
                    entry_bar_idx = i  # 記錄進場索引
                elif c >= df['UB'].iloc[i] and df['RSI'].iloc[i] >= 65:  # 突破上軌且 RSI 超買
                    pos = -1  # 開空單
                    entry_p = c  # 賣在 Bid
                    entry_time = dt  # 記錄進場時間 (MT5)
                    entry_bar_idx = i  # 記錄進場索引

            equity_records.append({"time": dt.strftime('%Y-%m-%d %H:%M:%S'), "balance": round(balance, 2)})  # 記錄當前權益

        # 計算策略關鍵指標
        tot_trades = len(trades)  # 總筆數
        wins = sum(1 for t in trades if t['win'])  # 獲利筆數
        losses = tot_trades - wins  # 虧損筆數
        win_rate = round(wins / tot_trades * 100, 1) if tot_trades > 0 else 0.0  # 勝率
        total_pnl = round(balance - 100000.0, 2)  # 總淨利
        win_dollars = sum(t['pnl_usd'] for t in trades if t['pnl_usd'] > 0)  # 總獲利金額
        loss_dollars = sum(abs(t['pnl_usd']) for t in trades if t['pnl_usd'] < 0)  # 總虧損金額
        pf = round(win_dollars / (loss_dollars + 1e-9), 2) if loss_dollars > 0 else (99.0 if wins > 0 else 0.0)  # 獲利因子

        eq_series = pd.Series([r['balance'] for r in equity_records])  # 轉為 Series
        cum_max = eq_series.cummax()  # 計算歷史高點
        dd_series = (eq_series - cum_max) / cum_max * 100  # 計算回撤百分比
        mdd_pct = round(abs(dd_series.min()), 2) if len(dd_series) > 0 else 0.0  # 最大回撤百分比
        mdd_usd = round(abs((eq_series - cum_max).min()), 2) if len(eq_series) > 0 else 0.0  # 最大回撤金額

        return {  # 回傳策略結果包
            "symbol": symbol,  # 貨幣對
            "strategy": "Asian Night Scalper (5m)",  # 策略名稱
            "df_processed": df,  # 處理後數據表
            "trades": trades,  # 交易記錄
            "active_pos": active_pos,  # 活躍部位
            "equity_records": equity_records,  # 權益曲線
            "metrics": {  # 關鍵指標
                "total_trades": tot_trades,  # 總交易筆數
                "wins": wins,  # 獲利筆數
                "losses": losses,  # 虧損筆數
                "win_rate": win_rate,  # 勝率
                "total_pnl_usd": total_pnl,  # 總淨利 (USD)
                "profit_factor": pf,  # 獲利因子
                "max_drawdown_pct": mdd_pct,  # 最大回撤 (%)
                "max_drawdown_usd": mdd_usd,  # 最大回撤 (USD)
                "roi_pct": round(total_pnl / 100000.0 * 100, 2)  # 總投資報酬率
            }  # 指標結束
        }  # 回傳結束

    def run_straddle_strategy(self, symbol: str, df_raw: pd.DataFrame, cfg: dict, lot_size: float = 1.0) -> dict:  # 執行策略 2: 5m 合成跨式賣方 (PEPPERSTONE MT5 數據)
        df = df_raw.copy()  # 複製原始數據
        df['MA'] = df['close'].rolling(30).mean()  # 計算 30 週期均線
        df['STD'] = df['close'].rolling(30).std()  # 計算 30 週期標準差
        df['Z'] = (df['close'] - df['MA']) / (df['STD'] + 1e-9)  # 計算動態波動偏離度 Z-Score

        pos = 0  # 倉位狀態 (1: 多, -1: 空, 0: 空手)
        entry_p = 0.0  # 進場價格
        entry_time = None  # 進場時間
        entry_bar_idx = 0  # 進場 K 棒索引
        balance = 100000.0  # 初始本金
        trades = []  # 交易記錄列表
        active_pos = None  # 當前即時活躍部位
        cost_per_trade = 5.0 * lot_size  # 單筆交易手續費 ($5 / 1.0 Lot)
        pip_size = self.get_pip_size(symbol)  # 取得商品最小 pip 單位
        pip_val_usd = self.get_pip_value_usd(symbol, lot_size)  # 取得每 pip 實際美金價值
        sp_pips = self.platform_spreads.get(symbol, 1.0)  # 實盤點差
        sp_dist = sp_pips * pip_size  # 點差價格距離
        tp_distance = cfg['tp'] * pip_size  # 止盈目標價差
        sl_distance = cfg['sl'] * pip_size  # 停損目標價差
        equity_records = []  # 權益曲線記錄

        for i in range(len(df)):  # 遍歷每根 5m K 棒
            dt = df.index[i]  # 當前時間 (MT5 伺服器時間)
            if i < 35:  # 預熱期
                equity_records.append({"time": dt.strftime('%Y-%m-%d %H:%M:%S'), "balance": balance})  # 記錄起始本金
                continue  # 跳過預熱
            c = float(df['close'].iloc[i])  # 收盤價
            h = float(df['high'].iloc[i])  # 最高價
            l = float(df['low'].iloc[i])  # 最低價
            z = float(df['Z'].iloc[i])  # 當前 Z 值
            hr = dt.hour  # 當前 MT5 伺服器小時
            
            # 純日內強制清倉：MT5 23:00 (換日前夕強制清倉，確保 0 隔夜利息)
            is_force_exit = (hr == 23)  # 強制平倉觸發

            if pos != 0:  # 當前持有部位
                exit_price = 0.0  # 出場價格
                exit_reason = ""  # 出場原因
                is_closed = False  # 是否已結算平倉

                if pos == 1:  # 多單持倉 (Short Put 側)
                    if z >= -cfg['z_out'] and c > entry_p:  # Z 值均值回歸且處於獲利狀態
                        exit_price = c - sp_dist  # 扣點差出場
                        exit_reason = f"Mean Reversion (Z >= -{cfg['z_out']})"  # 均值回歸原因
                        is_closed = True  # 標記平倉
                    elif h >= entry_p + tp_distance:  # 觸及止盈目標
                        exit_price = entry_p + tp_distance - sp_dist  # 扣點差出場
                        exit_reason = f"TP (+{cfg['tp']} pips)"  # 止盈原因標籤
                        is_closed = True  # 標記平倉
                    elif z <= -cfg['z_stop'] or l <= entry_p - sl_distance or is_force_exit:  # 極端偏離或硬停損或強制清倉
                        exit_price = (entry_p - sl_distance - sp_dist) if l <= entry_p - sl_distance else (c - sp_dist)  # 出場價
                        exit_reason = f"SL (-{cfg['sl']} pips)" if l <= entry_p - sl_distance else ("SL (Z <= -3.8)" if z <= -cfg['z_stop'] else "Zero-Overnight (MT5 23:00 換日前強制清倉，0 Swap)")  # 原因
                        is_closed = True  # 標記平倉

                    if is_closed:  # 執行平倉結算
                        pnl_pips = (exit_price - entry_p) / pip_size  # 多單獲利點數 (pips)
                        pnl_dollars = pnl_pips * pip_val_usd - cost_per_trade  # 多單美金淨損益 (扣手續費)
                        ret_pct = (exit_price - entry_p) / entry_p * 100  # 計算報酬百分比
                        balance += pnl_dollars  # 更新帳戶餘額
                        duration_bars = i - entry_bar_idx  # 計算持倉 K 棒數
                        trades.append({  # 寫入歷史交易紀錄
                            "trade_id": len(trades) + 1,  # 交易序號
                            "strategy": "Synthetic Short Straddle (5m)",  # 策略名稱
                            "symbol": symbol,  # 貨幣對
                            "type": "Buy (Short Put)",  # 交易方向
                            "lot_size": lot_size,  # 下單手數
                            "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'),  # 進場時間 (MT5)
                            "entry_price": round(entry_p, 5),  # 進場價格
                            "exit_time": dt.strftime('%Y-%m-%d %H:%M:%S'),  # 出場時間 (MT5)
                            "exit_price": round(exit_price, 5),  # 出場價格
                            "pnl_usd": round(pnl_dollars, 2),  # 淨利 (USD)
                            "pnl_pips": round(pnl_pips, 1),  # 點數 (pips)
                            "return_pct": round(ret_pct, 3),  # 報酬率 (%)
                            "exit_reason": exit_reason,  # 平倉原因
                            "duration_bars": duration_bars,  # 持倉 K 棒數
                            "duration_mins": duration_bars * 5,  # 持倉分鐘數
                            "win": pnl_dollars > 0  # 是否獲利
                        })  # 結束單筆記錄
                        pos = 0  # 重設為空倉

                elif pos == -1:  # 空單持倉 (Short Call 側)
                    if z <= cfg['z_out'] and c < entry_p:  # Z 值均值回歸且處於獲利狀態
                        exit_price = c + sp_dist  # 扣點差出場
                        exit_reason = f"Mean Reversion (Z <= +{cfg['z_out']})"  # 均值回歸原因
                        is_closed = True  # 標記平倉
                    elif l <= entry_p - tp_distance:  # 觸及止盈目標
                        exit_price = entry_p - tp_distance + sp_dist  # 扣點差出場
                        exit_reason = f"TP (+{cfg['tp']} pips)"  # 止盈原因標籤
                        is_closed = True  # 標記平倉
                    elif z >= cfg['z_stop'] or h >= entry_p + sl_distance or is_force_exit:  # 極端偏離或硬停損或強制清倉
                        exit_price = (entry_p + sl_distance + sp_dist) if h >= entry_p + sl_distance else (c + sp_dist)  # 出場價
                        exit_reason = f"SL (-{cfg['sl']} pips)" if h >= entry_p + sl_distance else ("SL (Z >= +3.8)" if z >= cfg['z_stop'] else "Zero-Overnight (MT5 23:00 換日前強制清倉，0 Swap)")  # 原因
                        is_closed = True  # 標記平倉

                    if is_closed:  # 執行平倉結算
                        pnl_pips = (entry_p - exit_price) / pip_size  # 空單獲利點數 (pips)
                        pnl_dollars = pnl_pips * pip_val_usd - cost_per_trade  # 空單美金淨損益 (扣手續費)
                        ret_pct = (entry_p - exit_price) / entry_p * 100  # 計算報酬百分比
                        balance += pnl_dollars  # 更新帳戶餘額
                        duration_bars = i - entry_bar_idx  # 計算持倉 K 棒數
                        trades.append({  # 寫入歷史交易紀錄
                            "trade_id": len(trades) + 1,  # 交易序號
                            "strategy": "Synthetic Short Straddle (5m)",  # 策略名稱
                            "symbol": symbol,  # 貨幣對
                            "type": "Sell (Short Call)",  # 交易方向
                            "lot_size": lot_size,  # 下單手數
                            "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'),  # 進場時間 (MT5)
                            "entry_price": round(entry_p, 5),  # 進場價格
                            "exit_time": dt.strftime('%Y-%m-%d %H:%M:%S'),  # 出場時間 (MT5)
                            "exit_price": round(exit_price, 5),  # 出場價格
                            "pnl_usd": round(pnl_dollars, 2),  # 淨利 (USD)
                            "pnl_pips": round(pnl_pips, 1),  # 點數 (pips)
                            "return_pct": round(ret_pct, 3),  # 報酬率 (%)
                            "exit_reason": exit_reason,  # 平倉原因
                            "duration_bars": duration_bars,  # 持倉 K 棒數
                            "duration_mins": duration_bars * 5,  # 持倉分鐘數
                            "win": pnl_dollars > 0  # 是否獲利
                        })  # 結束單筆記錄
                        pos = 0  # 重設為空倉

            # 檢查進場訊號 (MT5 伺服器時間 09:00 ~ 22:00 日間活躍窗口)
            is_entry_session = (9 <= hr <= 22) and not is_force_exit  # MT5 伺服器日間時段
            if pos == 0 and is_entry_session:  # 符合開倉時間窗口
                if z <= -cfg['z_in']:  # 偏離下軌做多 (賣 Put)
                    pos = 1  # 開多單
                    entry_p = c + sp_dist  # 買在 Ask (加點差)
                    entry_time = dt  # 記錄進場時間 (MT5)
                    entry_bar_idx = i  # 記錄進場索引
                elif z >= cfg['z_in']:  # 偏離上軌做空 (賣 Call)
                    pos = -1  # 開空單
                    entry_p = c  # 賣在 Bid
                    entry_time = dt  # 記錄進場時間 (MT5)
                    entry_bar_idx = i  # 記錄進場索引

            equity_records.append({"time": dt.strftime('%Y-%m-%d %H:%M:%S'), "balance": round(balance, 2)})  # 記錄當前權益

        # 計算策略關鍵指標
        tot_trades = len(trades)  # 總筆數
        wins = sum(1 for t in trades if t['win'])  # 獲利筆數
        losses = tot_trades - wins  # 虧損筆數
        win_rate = round(wins / tot_trades * 100, 1) if tot_trades > 0 else 0.0  # 勝率
        total_pnl = round(balance - 100000.0, 2)  # 總淨利
        win_dollars = sum(t['pnl_usd'] for t in trades if t['pnl_usd'] > 0)  # 總獲利金額
        loss_dollars = sum(abs(t['pnl_usd']) for t in trades if t['pnl_usd'] < 0)  # 總虧損金額
        pf = round(win_dollars / (loss_dollars + 1e-9), 2) if loss_dollars > 0 else (99.0 if wins > 0 else 0.0)  # 獲利因子

        eq_series = pd.Series([r['balance'] for r in equity_records])  # 轉為 Series
        cum_max = eq_series.cummax()  # 計算歷史高點
        dd_series = (eq_series - cum_max) / cum_max * 100  # 計算回撤百分比
        mdd_pct = round(abs(dd_series.min()), 2) if len(dd_series) > 0 else 0.0  # 最大回撤百分比
        mdd_usd = round(abs((eq_series - cum_max).min()), 2) if len(eq_series) > 0 else 0.0  # 最大回撤金額

        return {  # 回傳策略結果包
            "symbol": symbol,  # 貨幣對
            "strategy": "Synthetic Short Straddle (5m)",  # 策略名稱
            "df_processed": df,  # 處理後數據表
            "trades": trades,  # 交易記錄
            "active_pos": active_pos,  # 活躍部位
            "equity_records": equity_records,  # 權益曲線
            "metrics": {  # 關鍵指標
                "total_trades": tot_trades,  # 總交易筆數
                "wins": wins,  # 獲利筆數
                "losses": losses,  # 虧損筆數
                "win_rate": win_rate,  # 勝率
                "total_pnl_usd": total_pnl,  # 總淨利 (USD)
                "profit_factor": pf,  # 獲利因子
                "max_drawdown_pct": mdd_pct,  # 最大回撤 (%)
                "max_drawdown_usd": mdd_usd,  # 最大回撤 (USD)
                "roi_pct": round(total_pnl / 100000.0 * 100, 2)  # 總投資報酬率
            }  # 指標結束
        }  # 回傳結束

    def execute_all_and_generate_payload(self) -> dict:  # 執行全量運算並生成 JSON 封包 (PEPPERSTONE 數據源)
        print(f"[*] 開始以 TradingView PEPPERSTONE 5m 真實數據回測 8 大模組...")  # 啟動日誌

        data_cache = {}  # 數據快取
        for sym in self.all_symbols:  # 遍歷標的
            df = self.fetch_5m_data(sym)  # 載入 PEPPERSTONE 5m 數據
            if not df.empty:  # 檢查非空
                data_cache[sym] = df  # 寫入快取

        now_utc = datetime.datetime.now(datetime.timezone.utc)  # 當前 UTC
        now_mt5 = now_utc + datetime.timedelta(hours=3)  # 夏令 MT5
        now_tpe = now_utc + datetime.timedelta(hours=8)  # 台北時間

        module_results = []  # 儲存模組結果
        all_completed_trades = []  # 儲存全部交易
        symbols_meta = {}  # 儲存商品中繼資訊
        chart_data_dict = {}  # 儲存圖表數據

        # 1. 執行 5 款 Asian Scalper 模組
        for sym, cfg in self.scalper_configs.items():  # 遍歷標的
            if sym not in data_cache or data_cache[sym].empty: continue  # 檢查
            res = self.run_scalper_strategy(sym, data_cache[sym], cfg, lot_size=1.0)  # 執行
            module_results.append(res)  # 記錄
            for t in res['trades']:  # 遍歷交易
                t['module_id'] = f"Scalper_{sym}"  # 模組 ID
                all_completed_trades.append(t)  # 寫入總列表

        # 2. 執行 3 款 Short Straddle 模組
        for sym, cfg in self.straddle_configs.items():  # 遍歷標的
            if sym not in data_cache or data_cache[sym].empty: continue  # 檢查
            res = self.run_straddle_strategy(sym, data_cache[sym], cfg, lot_size=1.0)  # 執行
            module_results.append(res)  # 記錄
            for t in res['trades']:  # 遍歷交易
                t['module_id'] = f"Straddle_{sym}"  # 模組 ID
                all_completed_trades.append(t)  # 寫入總列表

        # 依進場時間倒序排列
        all_completed_trades.sort(key=lambda x: x['entry_time'], reverse=True)  # 排序
        for idx, t in enumerate(all_completed_trades):  # 重編序號
            t['global_id'] = idx + 1  # 賦予全域序號

        # 3. 處理圖表與指標狀態
        for sym in self.all_symbols:  # 遍歷標的
            if sym not in data_cache: continue  # 檢查
            df = data_cache[sym].copy()  # 複製
            df['MA20'] = df['close'].rolling(20).mean()  # 20 均線
            df['STD20'] = df['close'].rolling(20).std()  # 20 標準差
            df['UB'] = df['MA20'] + 2.2 * df['STD20']  # 上軌
            df['LB'] = df['MA20'] - 2.2 * df['STD20']  # 下軌

            delta = df['close'].diff()  # 差分
            gain = delta.where(delta > 0, 0).rolling(14).mean()  # 漲幅
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()  # 跌幅
            df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))  # RSI

            df['MA30'] = df['close'].rolling(30).mean()  # 30 均線
            df['STD30'] = df['close'].rolling(30).std()  # 30 標準差
            df['Z'] = (df['close'] - df['MA30']) / (df['STD30'] + 1e-9)  # Z-Score

            last_row = df.iloc[-1]  # 最新 K 棒
            prev_close = float(df['close'].iloc[-288]) if len(df) >= 288 else float(df['close'].iloc[0])  # 24H 前
            curr_c = float(last_row['close'])  # 最新價
            change_24h = (curr_c - prev_close) / prev_close * 100  # 24H 漲跌幅

            symbols_meta[sym] = {  # 商品中繼
                "symbol": sym,  # 標的
                "current_price": round(curr_c, 5),  # 價格
                "price_change_24h_pct": round(change_24h, 2),  # 漲跌幅
                "high_24h": round(float(df['high'].iloc[-288:].max()), 5) if len(df) >= 288 else round(float(df['high'].max()), 5),  # 最高
                "low_24h": round(float(df['low'].iloc[-288:].min()), 5) if len(df) >= 288 else round(float(df['low'].min()), 5),  # 最低
                "current_rsi": round(float(last_row['RSI']), 1) if not np.isnan(last_row['RSI']) else 50.0,  # RSI
                "current_zscore": round(float(last_row['Z']), 2) if not np.isnan(last_row['Z']) else 0.0,  # Z-Score
                "supports_scalper": sym in self.scalper_configs,  # 支援夜間
                "supports_straddle": sym in self.straddle_configs,  # 支援日間
                "spread_pips": self.platform_spreads.get(sym, 1.0),  # 點差
                "is_scalper_session": (now_mt5.hour == 0 or 1 <= now_mt5.hour <= 7),  # 夜間時段
                "is_straddle_session": (9 <= now_mt5.hour <= 22)  # 日間時段
            }  # 結束

            df_chart = df.tail(800).copy()  # 取最近 800 筆圖表
            chart_data_dict[sym] = {  # 圖表資料
                "timestamps": [t.strftime('%Y-%m-%d %H:%M') for t in df_chart.index],  # MT5 時間
                "open": [round(float(x), 5) for x in df_chart['open']],  # 開盤
                "high": [round(float(x), 5) for x in df_chart['high']],  # 最高
                "low": [round(float(x), 5) for x in df_chart['low']],  # 最低
                "close": [round(float(x), 5) for x in df_chart['close']],  # 收盤
                "volume": [round(float(x), 1) for x in df_chart['volume']],  # 成交量
                "bb_upper": [round(float(x), 5) if not np.isnan(x) else None for x in df_chart['UB']],  # 上軌
                "bb_mid": [round(float(x), 5) if not np.isnan(x) else None for x in df_chart['MA20']],  # 中軌
                "bb_lower": [round(float(x), 5) if not np.isnan(x) else None for x in df_chart['LB']],  # 下軌
                "rsi": [round(float(x), 1) if not np.isnan(x) else None for x in df_chart['RSI']],  # RSI
                "z_score": [round(float(x), 2) if not np.isnan(x) else None for x in df_chart['Z']]  # Z-Score
            }  # 結束

        # 4. 計算組合綜合指標
        portfolio_total_trades = len(all_completed_trades)  # 總次數
        portfolio_wins = sum(1 for t in all_completed_trades if t['win'])  # 獲利次數
        portfolio_losses = portfolio_total_trades - portfolio_wins  # 虧損次數
        portfolio_win_rate = round(portfolio_wins / portfolio_total_trades * 100, 1) if portfolio_total_trades > 0 else 0.0  # 勝率
        portfolio_pnl = sum(t['pnl_usd'] for t in all_completed_trades)  # 總淨利
        portfolio_win_usd = sum(t['pnl_usd'] for t in all_completed_trades if t['pnl_usd'] > 0)  # 總毛利
        portfolio_loss_usd = sum(abs(t['pnl_usd']) for t in all_completed_trades if t['pnl_usd'] < 0)  # 總毛損
        portfolio_pf = round(portfolio_win_usd / (portfolio_loss_usd + 1e-9), 2) if portfolio_loss_usd > 0 else (99.0 if portfolio_wins > 0 else 0.0)  # PF

        # 模組摘要清單
        modules_summary = []  # 摘要清單
        for m in module_results:  # 遍歷
            modules_summary.append({  # 加入模組摘要
                "module_id": f"{'Scalper' if 'Scalper' in m['strategy'] else 'Straddle'}_{m['symbol']}",  # ID
                "strategy": m['strategy'],  # 策略
                "symbol": m['symbol'],  # 標的
                "trades_count": m['metrics']['total_trades'],  # 筆數
                "wins": m['metrics']['wins'],  # 勝場
                "losses": m['metrics']['losses'],  # 敗場
                "win_rate": m['metrics']['win_rate'],  # 勝率
                "total_pnl_usd": m['metrics']['total_pnl_usd'],  # 淨利
                "profit_factor": m['metrics']['profit_factor'],  # 獲利因子
                "max_drawdown_pct": m['metrics']['max_drawdown_pct'],  # 最大回撤%
                "max_drawdown_usd": m['metrics']['max_drawdown_usd'],  # 最大回撤美金
                "roi_pct": m['metrics']['roi_pct']  # ROI%
            })  # 結束

        # 累積損益曲線
        trades_chronological = sorted(all_completed_trades, key=lambda x: x['exit_time'])  # 依平倉時間排序
        first_time = trades_chronological[0]['entry_time'] if trades_chronological else "2026-07-01 00:00:00"  # 起始
        combined_equity_curve = [{"time": first_time, "cum_pnl": 0.0, "balance": 100000.0, "pnl": 0.0}]  # 起點
        running_pnl = 0.0  # 累計損益
        for t in trades_chronological:  # 遍歷
            running_pnl += t['pnl_usd']  # 累加
            combined_equity_curve.append({  # 記錄
                "time": t['exit_time'],  # 時間 (MT5)
                "cum_pnl": round(running_pnl, 2),  # 當前累計損益
                "balance": round(100000.0 + running_pnl, 2),  # 餘額
                "pnl": t['pnl_usd'],  # 單筆損益
                "symbol": t['symbol'],  # 標的
                "strategy": t['strategy']  # 策略
            })  # 結束

        comb_series = pd.Series([r['balance'] for r in combined_equity_curve])  # Series
        comb_cum_max = comb_series.cummax()  # 歷史高點
        comb_dd_series = (comb_series - comb_cum_max) / comb_cum_max * 100  # 回撤序列
        portfolio_mdd_pct = round(abs(comb_dd_series.min()), 2) if len(comb_dd_series) > 0 else 0.0  # 組合 MDD%
        portfolio_mdd_usd = round(abs((comb_series - comb_cum_max).min()), 2) if len(comb_series) > 0 else 0.0  # 組合 MDD 美金

        payload = {  # 總 JSON 封包
            "system_info": {  # 系統資訊
                "title": "5m 純日內雙策略 × 8 大模組極限收租監控儀表板 (PEPPERSTONE 數據源)",  # 標題
                "data_source": "TradingView (Broker: PEPPERSTONE)",  # 數據來源
                "time_standard": "MT5 伺服器時間 (夏令 UTC+3 / 冬令 UTC+2)",  # 時間標準
                "last_updated_mt5": now_mt5.strftime('%Y-%m-%d %H:%M:%S (MT5 Server Time)'),  # MT5 時間
                "last_updated_tpe": now_tpe.strftime('%Y-%m-%d %H:%M:%S (台北 UTC+8)'),  # 台北時間
                "last_updated_utc": now_utc.strftime('%Y-%m-%d %H:%M:%S UTC'),  # UTC 時間
                "symbols_count": len(self.all_symbols),  # 標的數
                "modules_count": len(module_results)  # 模組數
            },  # 結束
            "portfolio_metrics": {  # 總組合核心 KPI
                "total_trades": portfolio_total_trades,  # 總筆數
                "wins": portfolio_wins,  # 獲利筆數
                "losses": portfolio_losses,  # 虧損筆數
                "win_rate": portfolio_win_rate,  # 勝率
                "total_pnl_usd": round(portfolio_pnl, 2),  # 總淨利
                "profit_factor": portfolio_pf,  # 獲利因子
                "max_drawdown_pct": portfolio_mdd_pct,  # 最大回撤%
                "max_drawdown_usd": portfolio_mdd_usd,  # 最大回撤美金
                "roi_pct": round(portfolio_pnl / 100000.0 * 100, 2),  # 總 ROI
                "initial_capital": 100000.0,  # 初始本金
                "current_capital": round(100000.0 + portfolio_pnl, 2)  # 結算本金
            },  # 結束
            "modules_summary": modules_summary,  # 模組明細
            "symbols_meta": symbols_meta,  # 商品中繼
            "active_positions": [],  # 活躍持倉
            "combined_equity_curve": combined_equity_curve,  # 權益曲線
            "all_trades": all_completed_trades,  # 交易明細
            "chart_data": chart_data_dict  # 圖表數據
        }  # 結束

        output_json_path = os.path.join(os.path.dirname(__file__), "strategy_results.json")  # JSON 路徑
        with open(output_json_path, "w", encoding="utf-8") as f:  # 開啟寫入
            json.dump(payload, f, ensure_ascii=False, indent=2)  # 寫入 JSON
        print(f"[+] 策略回測數據 (PEPPERSTONE 源) 已成功輸出至: {output_json_path}")  # 輸出成功日誌

        output_csv_path = os.path.join(os.path.dirname(__file__), "all_trades_history.csv")  # CSV 路徑
        pd.DataFrame(all_completed_trades).to_csv(output_csv_path, index=False, encoding="utf-8-sig")  # 寫入 CSV
        print(f"[+] 完整歷史交易明細已輸出至: {output_csv_path}")  # 輸出成功日誌

        return payload  # 回傳資料

if __name__ == "__main__":  # 程式主入口
    engine = PureIntraday5mStrategyEngine()  # 實例化引擎
    engine.execute_all_and_generate_payload()  # 執行全量回測
