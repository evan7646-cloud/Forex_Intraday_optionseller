import os  # 導入作業系統模組
import json  # 導入 JSON 資料處理模組
import datetime  # 導入日期時間處理模組
import numpy as np  # 導入數值運算庫
import pandas as pd  # 導入資料表格分析庫
import yfinance as yf  # 導入 Yahoo Finance 行情介面
try:  # 嘗試導入 TradingView 介面
    from tvDatafeed import TvDatafeed, Interval  # 導入 TradingView 資料接口
except Exception:  # 若無安裝或載入失敗
    TvDatafeed = None  # 設定為 None

class PureIntraday5mStrategyEngine:  # 定義純日內 5 分鐘策略回測與資料生成引擎
    def __init__(self):  # 初始化引擎
        self.tv = None  # 初始化 TradingView 連線物件
        if TvDatafeed is not None:  # 若套件可用
            try:  # 嘗試建立連線
                self.tv = TvDatafeed()  # 建立客戶端實例
            except Exception:  # 連線例外處理
                self.tv = None  # 設為 None

        # 定義策略 1: 4 款夜間收租標的
        self.scalper_symbols = ["NZDCAD", "AUDNZD", "AUDCAD", "EURGBP"]  # 亞洲夜間剝頭皮貨幣對
        # 定義策略 2: 4 款跨式賣方標的
        self.straddle_symbols = ["EURCHF", "EURGBP", "EURUSD", "EURJPY"]  # 日間跨式賣方貨幣對
        # 整合所有獨立貨幣對清單
        self.all_symbols = sorted(list(set(self.scalper_symbols + self.straddle_symbols)))  # 7 大不重複貨幣對

    def fetch_5m_data(self, symbol: str, n_bars: int = 5000) -> pd.DataFrame:  # 抓取 5m K 線數據
        print(f"[*] 正在抓取 [{symbol}] 5m 行情數據...")  # 輸出抓取日誌
        df = None  # 初始化數據表

        if self.tv is not None:  # 若 TradingView 可用
            try:  # 嘗試自 TradingView 取得
                df = self.tv.get_hist(symbol=symbol, exchange="OANDA", interval=Interval.in_5_minute, n_bars=n_bars)  # 發送請求
                if df is not None and len(df) > 100:  # 檢查數據長度
                    df = df.reset_index()  # 重設索引
                    df['datetime'] = pd.to_datetime(df['datetime']).dt.tz_localize(None)  # 去除時區
                    df.set_index('datetime', inplace=True)  # 設為時間索引
                    df = df[['open', 'high', 'low', 'close', 'volume']][~df.index.duplicated(keep='first')]  # 欄位篩選與去重
                    print(f"  [+] TradingView 成功獲取 {len(df)} 根 5m K 線")  # 輸出成功日誌
                    return df  # 回傳有效資料表
            except Exception as e:  # 捕捉異常
                print(f"  [-] TradingView 獲取失敗 ({e})，轉為 Yahoo Finance 備援...")  # 輸出備援提示

        # Yahoo Finance 備援機制
        ticker = f"{symbol}=X"  # 設定 Yahoo 貨幣對代碼格式
        try:  # 嘗試下載
            df_yf = yf.download(ticker, period="60d", interval="5m", progress=False)  # 抓取近 60 天 5m 數據
            if isinstance(df_yf.columns, pd.MultiIndex):  # 若欄位為 MultiIndex
                df_yf.columns = df_yf.columns.get_level_values(0)  # 展平欄位索引
            df_yf = df_yf.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})  # 標準化欄位名稱
            if df_yf.index.tz is not None:  # 若包含時區
                df_yf.index = pd.to_datetime(df_yf.index).tz_localize(None)  # 轉為無時區時間
            else:  # 無時區
                df_yf.index = pd.to_datetime(df_yf.index)  # 確保時間格式
            df_clean = df_yf[['open', 'high', 'low', 'close', 'volume']].dropna()  # 清理空值
            print(f"  [+] Yahoo Finance 成功獲取 {len(df_clean)} 根 5m K 線")  # 輸出成功日誌
            return df_clean  # 回傳清理後的數據表
        except Exception as err:  # 捕捉下載異常
            print(f"  [!] Yahoo Finance 下載失敗: {err}")  # 輸出錯誤訊息
            return pd.DataFrame()  # 回傳空表

    def run_scalper_strategy(self, symbol: str, df_raw: pd.DataFrame, lot_size: float = 1.0) -> dict:  # 執行策略 1: 5m 亞洲夜間收租 (1.0 Lot)
        df = df_raw.copy()  # 複製原始數據
        df['MA'] = df['close'].rolling(20).mean()  # 計算 20 週期均線
        df['STD'] = df['close'].rolling(20).std()  # 計算 20 週期標準差
        df['UB'] = df['MA'] + 2.2 * df['STD']  # 計算布林上軌 (2.2倍標準差)
        df['LB'] = df['MA'] - 2.2 * df['STD']  # 計算布林下軌 (2.2倍標準差)

        delta = df['close'].diff()  # 計算價格差分
        gain = delta.where(delta > 0, 0).rolling(14).mean()  # 14 週期平均漲幅
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()  # 14 週期平均跌幅
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))  # 計算 RSI 指標

        is_night = (df.index.hour >= 21) | (df.index.hour <= 6)  # 夜間開倉時段 (UTC 21:00 - 06:00)
        pos = 0  # 倉位狀態 (1: 多, -1: 空, 0: 空手)
        entry_p = 0.0  # 進場價格
        entry_time = None  # 進場時間
        entry_bar_idx = 0  # 進場 K 棒索引
        balance = 100000.0  # 初始本金
        trades = []  # 交易記錄列表
        active_pos = None  # 當前即時活躍部位
        cost_per_trade = 5.0 * lot_size  # 單筆交易手續費 ($5 / 1.0 Lot)
        tp_ratio = 0.0005  # 止盈比例 0.05% (5 pips)
        sl_ratio = 0.0035  # 止損比例 0.35% (35 pips)
        equity_records = []  # 權益曲線記錄

        for i in range(len(df)):  # 遍歷每根 5m K 棒
            dt = df.index[i]  # 當前時間
            if i < 30:  # 預熱期
                equity_records.append({"time": dt.strftime('%Y-%m-%d %H:%M:%S'), "balance": balance})  # 記錄起始本金
                continue  # 跳過預熱
            c = float(df['close'].iloc[i])  # 收盤價
            h = float(df['high'].iloc[i])  # 最高價
            l = float(df['low'].iloc[i])  # 最低價
            hr = dt.hour  # 當前小時 (UTC)
            is_force_exit = (hr == 7)  # UTC 07:00 歐盤前夕強制清倉

            if pos != 0:  # 當前持有部位
                exit_price = 0.0  # 出場價格
                exit_reason = ""  # 出場原因
                is_closed = False  # 是否已結算平倉

                if pos == 1:  # 多單持倉
                    if h >= entry_p * (1.0 + tp_ratio):  # 觸及 5 pips 止盈目標
                        exit_price = entry_p * (1.0 + tp_ratio)  # 止盈價
                        exit_reason = "TP (+5 pips)"  # 止盈原因標籤
                        is_closed = True  # 標記平倉
                    elif c >= df['MA'].iloc[i]:  # 回歸布林中軌止盈
                        exit_price = c  # 中軌現價
                        exit_reason = "TP (BB Midline)"  # 中軌止盈原因
                        is_closed = True  # 標記平倉
                    elif l <= entry_p * (1.0 - sl_ratio):  # 觸及 35 pips 硬停損
                        exit_price = entry_p * (1.0 - sl_ratio)  # 停損價
                        exit_reason = "SL (-35 pips)"  # 硬停損原因
                        is_closed = True  # 標記平倉
                    elif is_force_exit:  # UTC 07:00 時間強制清倉
                        exit_price = c  # 現價清倉
                        exit_reason = "Time Cutoff (UTC 07:00)"  # 強制清倉原因
                        is_closed = True  # 標記平倉

                    if is_closed:  # 執行平倉結算
                        pnl_dollars = (exit_price - entry_p) / entry_p * 100000.0 * lot_size - cost_per_trade  # 計算淨美金盈虧
                        pnl_pips = (exit_price - entry_p) / entry_p * 10000  # 計算盈虧 pips 點數
                        ret_pct = (exit_price - entry_p) / entry_p * 100  # 計算報酬百分比
                        balance += pnl_dollars  # 更新帳戶餘額
                        duration_bars = i - entry_bar_idx  # 計算持倉 K 棒數量
                        trades.append({  # 寫入歷史交易紀錄
                            "trade_id": len(trades) + 1,  # 交易序號
                            "strategy": "Asian Night Scalper (5m)",  # 策略名稱
                            "symbol": symbol,  # 貨幣對
                            "type": "Buy (Long)",  # 交易方向
                            "lot_size": lot_size,  # 下單手數
                            "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'),  # 進場時間
                            "entry_price": round(entry_p, 5),  # 進場價格
                            "exit_time": dt.strftime('%Y-%m-%d %H:%M:%S'),  # 出場時間
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

                elif pos == -1:  # 空單持倉
                    if l <= entry_p * (1.0 - tp_ratio):  # 觸及 5 pips 止盈目標
                        exit_price = entry_p * (1.0 - tp_ratio)  # 止盈價
                        exit_reason = "TP (+5 pips)"  # 止盈標籤
                        is_closed = True  # 標記平倉
                    elif c <= df['MA'].iloc[i]:  # 回歸布林中軌止盈
                        exit_price = c  # 中軌現價
                        exit_reason = "TP (BB Midline)"  # 中軌止盈原因
                        is_closed = True  # 標記平倉
                    elif h >= entry_p * (1.0 + sl_ratio):  # 觸及 35 pips 硬停損
                        exit_price = entry_p * (1.0 + sl_ratio)  # 停損價
                        exit_reason = "SL (-35 pips)"  # 停損標籤
                        is_closed = True  # 標記平倉
                    elif is_force_exit:  # UTC 07:00 時間強制清倉
                        exit_price = c  # 現價清倉
                        exit_reason = "Time Cutoff (UTC 07:00)"  # 強制清倉原因
                        is_closed = True  # 標記平倉

                    if is_closed:  # 執行平倉結算
                        pnl_dollars = (entry_p - exit_price) / entry_p * 100000.0 * lot_size - cost_per_trade  # 計算淨美金盈虧
                        pnl_pips = (entry_p - exit_price) / entry_p * 10000  # 計算盈虧 pips 點數
                        ret_pct = (entry_p - exit_price) / entry_p * 100  # 計算報酬百分比
                        balance += pnl_dollars  # 更新帳戶餘額
                        duration_bars = i - entry_bar_idx  # 計算持倉 K 棒數
                        trades.append({  # 寫入歷史交易紀錄
                            "trade_id": len(trades) + 1,  # 交易序號
                            "strategy": "Asian Night Scalper (5m)",  # 策略名稱
                            "symbol": symbol,  # 貨幣對
                            "type": "Sell (Short)",  # 交易方向
                            "lot_size": lot_size,  # 下單手數
                            "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'),  # 進場時間
                            "entry_price": round(entry_p, 5),  # 進場價格
                            "exit_time": dt.strftime('%Y-%m-%d %H:%M:%S'),  # 出場時間
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

            # 檢查進場訊號 (僅在夜間時段且非強制清倉時間)
            if pos == 0 and is_night[i] and not is_force_exit:  # 符合開倉時間窗口
                if c <= df['LB'].iloc[i] and df['RSI'].iloc[i] <= 35:  # 跌破下軌且 RSI 超賣
                    pos = 1  # 開多單
                    entry_p = c  # 記錄進場價
                    entry_time = dt  # 記錄進場時間
                    entry_bar_idx = i  # 記錄進場索引
                elif c >= df['UB'].iloc[i] and df['RSI'].iloc[i] >= 65:  # 突破上軌且 RSI 超買
                    pos = -1  # 開空單
                    entry_p = c  # 記錄進場價
                    entry_time = dt  # 記錄進場時間
                    entry_bar_idx = i  # 記錄進場索引

            equity_records.append({"time": dt.strftime('%Y-%m-%d %H:%M:%S'), "balance": round(balance, 2)})  # 記錄當前權益

        # 檢查最後一根 K 棒是否有活躍持倉
        if pos != 0:  # 仍有未平倉持倉
            last_c = float(df['close'].iloc[-1])  # 最新收盤價
            unrealized_pnl = ((last_c - entry_p) if pos == 1 else (entry_p - last_c)) / entry_p * 100000.0 * lot_size - cost_per_trade  # 計算未實現盈虧美金
            unrealized_pips = ((last_c - entry_p) if pos == 1 else (entry_p - last_c)) / entry_p * 10000  # 計算未實現 pips
            active_pos = {  # 構建活躍部位物件
                "strategy": "Asian Night Scalper (5m)",  # 策略名稱
                "symbol": symbol,  # 貨幣對
                "type": "Buy (Long)" if pos == 1 else "Sell (Short)",  # 方向
                "lot_size": lot_size,  # 手數
                "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'),  # 進場時間
                "entry_price": round(entry_p, 5),  # 進場價
                "current_price": round(last_c, 5),  # 最新價
                "target_tp_price": round(entry_p * (1.0 + (tp_ratio if pos == 1 else -tp_ratio)), 5),  # 目標止盈價
                "hard_sl_price": round(entry_p * (1.0 + (-sl_ratio if pos == 1 else sl_ratio)), 5),  # 硬停損價
                "unrealized_pnl_usd": round(unrealized_pnl, 2),  # 未實現盈虧 (USD)
                "unrealized_pnl_pips": round(unrealized_pips, 1),  # 未實現盈虧 (pips)
                "duration_mins": (len(df) - 1 - entry_bar_idx) * 5  # 持倉時間
            }  # 活躍持倉結束

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

    def run_straddle_strategy(self, symbol: str, df_raw: pd.DataFrame, lot_size: float = 1.0) -> dict:  # 執行策略 2: 5m 合成跨式賣方 (1.0 Lot)
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
        tp_ratio = 0.0005  # 止盈比例 0.05% (5 pips)
        sl_ratio = 0.0035  # 止損比例 0.35% (35 pips)
        equity_records = []  # 權益曲線記錄

        for i in range(len(df)):  # 遍歷每根 5m K 棒
            dt = df.index[i]  # 當前時間
            if i < 35:  # 預熱期
                equity_records.append({"time": dt.strftime('%Y-%m-%d %H:%M:%S'), "balance": balance})  # 記錄起始本金
                continue  # 跳過預熱
            c = float(df['close'].iloc[i])  # 收盤價
            h = float(df['high'].iloc[i])  # 最高價
            l = float(df['low'].iloc[i])  # 最低價
            z = float(df['Z'].iloc[i])  # 當前 Z 值
            hr = dt.hour  # 當前小時 (UTC)
            is_force_exit = (hr == 21)  # UTC 21:00 美盤收盤前夕強制清倉

            if pos != 0:  # 當前持有部位
                exit_price = 0.0  # 出場價格
                exit_reason = ""  # 出場原因
                is_closed = False  # 是否已結算平倉

                if pos == 1:  # 多單持倉 (Short Put 側)
                    if z >= -0.2:  # Z 值均值回歸收租
                        exit_price = c  # 現價平倉
                        exit_reason = "Mean Reversion (Z >= -0.2)"  # 均值回歸原因
                        is_closed = True  # 標記平倉
                    elif h >= entry_p * (1.0 + tp_ratio):  # 觸及 5 pips 止盈目標
                        exit_price = entry_p * (1.0 + tp_ratio)  # 止盈價
                        exit_reason = "TP (+5 pips)"  # 止盈原因標籤
                        is_closed = True  # 標記平倉
                    elif z <= -3.8:  # 極端偏離停損
                        exit_price = c  # 現價停損
                        exit_reason = "SL (Z <= -3.8)"  # Z值極端偏離停損
                        is_closed = True  # 標記平倉
                    elif l <= entry_p * (1.0 - sl_ratio):  # 觸及 35 pips 硬停損
                        exit_price = entry_p * (1.0 - sl_ratio)  # 硬停損價
                        exit_reason = "SL (-35 pips)"  # 硬停損標籤
                        is_closed = True  # 標記平倉
                    elif is_force_exit:  # UTC 21:00 時間強制清倉
                        exit_price = c  # 現價清倉
                        exit_reason = "Time Cutoff (UTC 21:00)"  # 強制清倉原因
                        is_closed = True  # 標記平倉

                    if is_closed:  # 執行平倉結算
                        pnl_dollars = (exit_price - entry_p) / entry_p * 100000.0 * lot_size - cost_per_trade  # 計算淨美金盈虧
                        pnl_pips = (exit_price - entry_p) / entry_p * 10000  # 計算盈虧 pips
                        ret_pct = (exit_price - entry_p) / entry_p * 100  # 計算報酬百分比
                        balance += pnl_dollars  # 更新帳戶餘額
                        duration_bars = i - entry_bar_idx  # 計算持倉 K 棒數
                        trades.append({  # 寫入歷史交易紀錄
                            "trade_id": len(trades) + 1,  # 交易序號
                            "strategy": "Synthetic Short Straddle (5m)",  # 策略名稱
                            "symbol": symbol,  # 貨幣對
                            "type": "Buy (Short Put)",  # 交易方向
                            "lot_size": lot_size,  # 下單手數
                            "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'),  # 進場時間
                            "entry_price": round(entry_p, 5),  # 進場價格
                            "exit_time": dt.strftime('%Y-%m-%d %H:%M:%S'),  # 出場時間
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
                    if z <= 0.2:  # Z 值均值回歸收租
                        exit_price = c  # 現價平倉
                        exit_reason = "Mean Reversion (Z <= 0.2)"  # 均值回歸原因
                        is_closed = True  # 標記平倉
                    elif l <= entry_p * (1.0 - tp_ratio):  # 觸及 5 pips 止盈目標
                        exit_price = entry_p * (1.0 - tp_ratio)  # 止盈價
                        exit_reason = "TP (+5 pips)"  # 止盈原因標籤
                        is_closed = True  # 標記平倉
                    elif z >= 3.8:  # 極端偏離停損
                        exit_price = c  # 現價停損
                        exit_reason = "SL (Z >= 3.8)"  # Z值極端偏離停損
                        is_closed = True  # 標記平倉
                    elif h >= entry_p * (1.0 + sl_ratio):  # 觸及 35 pips 硬停損
                        exit_price = entry_p * (1.0 + sl_ratio)  # 硬停損價
                        exit_reason = "SL (-35 pips)"  # 硬停損標籤
                        is_closed = True  # 標記平倉
                    elif is_force_exit:  # UTC 21:00 時間強制清倉
                        exit_price = c  # 現價清倉
                        exit_reason = "Time Cutoff (UTC 21:00)"  # 強制清倉原因
                        is_closed = True  # 標記平倉

                    if is_closed:  # 執行平倉結算
                        pnl_dollars = (entry_p - exit_price) / entry_p * 100000.0 * lot_size - cost_per_trade  # 計算淨美金盈虧
                        pnl_pips = (entry_p - exit_price) / entry_p * 10000  # 計算盈虧 pips
                        ret_pct = (entry_p - exit_price) / entry_p * 100  # 計算報酬百分比
                        balance += pnl_dollars  # 更新帳戶餘額
                        duration_bars = i - entry_bar_idx  # 計算持倉 K 棒數
                        trades.append({  # 寫入歷史交易紀錄
                            "trade_id": len(trades) + 1,  # 交易序號
                            "strategy": "Synthetic Short Straddle (5m)",  # 策略名稱
                            "symbol": symbol,  # 貨幣對
                            "type": "Sell (Short Call)",  # 交易方向
                            "lot_size": lot_size,  # 下單手數
                            "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'),  # 進場時間
                            "entry_price": round(entry_p, 5),  # 進場價格
                            "exit_time": dt.strftime('%Y-%m-%d %H:%M:%S'),  # 出場時間
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

            # 檢查進場訊號 (僅在日間活躍時段 UTC 07:00 - 20:00 允許進場)
            if pos == 0 and (7 <= hr <= 20) and not is_force_exit:  # 符合日間開倉窗口
                if z <= -2.1:  # 動態偏離低於 -2.1 買入
                    pos = 1  # 開多單
                    entry_p = c  # 記錄進場價
                    entry_time = dt  # 記錄進場時間
                    entry_bar_idx = i  # 記錄進場索引
                elif z >= 2.1:  # 動態偏離高於 +2.1 賣出
                    pos = -1  # 開空單
                    entry_p = c  # 記錄進場價
                    entry_time = dt  # 記錄進場時間
                    entry_bar_idx = i  # 記錄進場索引

            equity_records.append({"time": dt.strftime('%Y-%m-%d %H:%M:%S'), "balance": round(balance, 2)})  # 記錄當前權益

        # 檢查最後一根 K 棒是否有活躍持倉
        if pos != 0:  # 仍有未平倉持倉
            last_c = float(df['close'].iloc[-1])  # 最新收盤價
            unrealized_pnl = ((last_c - entry_p) if pos == 1 else (entry_p - last_c)) / entry_p * 100000.0 * lot_size - cost_per_trade  # 計算未實現盈虧美金
            unrealized_pips = ((last_c - entry_p) if pos == 1 else (entry_p - last_c)) / entry_p * 10000  # 計算未實現 pips
            active_pos = {  # 構建活躍部位物件
                "strategy": "Synthetic Short Straddle (5m)",  # 策略名稱
                "symbol": symbol,  # 貨幣對
                "type": "Buy (Short Put)" if pos == 1 else "Sell (Short Call)",  # 方向
                "lot_size": lot_size,  # 手數
                "entry_time": entry_time.strftime('%Y-%m-%d %H:%M:%S'),  # 進場時間
                "entry_price": round(entry_p, 5),  # 進場價
                "current_price": round(last_c, 5),  # 最新價
                "target_tp_price": round(entry_p * (1.0 + (tp_ratio if pos == 1 else -tp_ratio)), 5),  # 目標止盈價
                "hard_sl_price": round(entry_p * (1.0 + (-sl_ratio if pos == 1 else sl_ratio)), 5),  # 硬停損價
                "unrealized_pnl_usd": round(unrealized_pnl, 2),  # 未實現盈虧 (USD)
                "unrealized_pnl_pips": round(unrealized_pips, 1),  # 未實現盈虧 (pips)
                "duration_mins": (len(df) - 1 - entry_bar_idx) * 5  # 持倉時間
            }  # 活躍持倉結束

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

    def execute_all_and_generate_payload(self) -> dict:  # 執行全策略回測並打包所有前端 JSON 資料
        print("\n========================================================")  # 分隔線
        print("   開始執行純日內 5m 雙策略 × 8 大模組即時運算與數據封包   ")  # 標題
        print("========================================================\n")  # 分隔線

        now_utc = datetime.datetime.now(datetime.timezone.utc)  # 取得當前 UTC 時間
        now_tpe = now_utc + datetime.timedelta(hours=8)  # 取得台北時間 (UTC+8)

        data_cache = {}  # 儲存已抓取之 5m 數據表
        for sym in self.all_symbols:  # 遍歷所有貨幣對
            df = self.fetch_5m_data(sym, n_bars=5000)  # 抓取 5m 數據
            if not df.empty:  # 數據非空
                data_cache[sym] = df  # 快取數據

        module_results = []  # 儲存所有 8 個策略模組結果
        all_completed_trades = []  # 儲存所有完成的交易紀錄
        active_positions_list = []  # 儲存所有當前活躍持倉
        symbols_meta = {}  # 儲存商品即時行情與指標狀態
        chart_data_dict = {}  # 儲存各商品 5m K 線與指標數據 (提供 Plotly 圖表)

        # 1. 執行 4 款 Asian Scalper 模組
        for sym in self.scalper_symbols:  # 遍歷標的
            if sym not in data_cache or data_cache[sym].empty: continue  # 檢查數據
            res = self.run_scalper_strategy(sym, data_cache[sym], lot_size=1.0)  # 執行 1.0 手回測
            module_results.append(res)  # 儲存模組結果
            for t in res['trades']:  # 遍歷交易
                t['module_id'] = f"Scalper_{sym}"  # 添加模組識別 ID
                all_completed_trades.append(t)  # 寫入總交易列表
            if res['active_pos'] is not None:  # 若有活躍持倉
                active_positions_list.append(res['active_pos'])  # 寫入活躍列表

        # 2. 執行 4 款 Short Straddle 模組
        for sym in self.straddle_symbols:  # 遍歷標的
            if sym not in data_cache or data_cache[sym].empty: continue  # 檢查數據
            res = self.run_straddle_strategy(sym, data_cache[sym], lot_size=1.0)  # 執行 1.0 手回測
            module_results.append(res)  # 儲存模組結果
            for t in res['trades']:  # 遍歷交易
                t['module_id'] = f"Straddle_{sym}"  # 添加模組識別 ID
                all_completed_trades.append(t)  # 寫入總交易列表
            if res['active_pos'] is not None:  # 若有活躍持倉
                active_positions_list.append(res['active_pos'])  # 寫入活躍列表

        # 重新排序總交易明細 (依進場時間倒序)
        all_completed_trades.sort(key=lambda x: x['entry_time'], reverse=True)  # 最新交易排在最前面
        for idx, t in enumerate(all_completed_trades):  # 重編全域序號
            t['global_id'] = idx + 1  # 賦予全域唯一序號

        # 3. 處理各標的即時報價、指標狀態與 K 線圖表數據 (取最近 800 根 5m K 線加速傳輸)
        for sym in self.all_symbols:  # 遍歷標的
            if sym not in data_cache: continue  # 檢查
            df = data_cache[sym].copy()  # 複製
            df['MA20'] = df['close'].rolling(20).mean()  # 20 均線
            df['STD20'] = df['close'].rolling(20).std()  # 20 標準差
            df['UB'] = df['MA20'] + 2.2 * df['STD20']  # 布林上軌
            df['LB'] = df['MA20'] - 2.2 * df['STD20']  # 布林下軌

            delta = df['close'].diff()  # 差分
            gain = delta.where(delta > 0, 0).rolling(14).mean()  # 漲幅
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()  # 跌幅
            df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))  # RSI

            df['MA30'] = df['close'].rolling(30).mean()  # 30 均線
            df['STD30'] = df['close'].rolling(30).std()  # 30 標準差
            df['Z'] = (df['close'] - df['MA30']) / (df['STD30'] + 1e-9)  # Z-Score

            last_row = df.iloc[-1]  # 最新一根 K 線
            prev_close = float(df['close'].iloc[-288]) if len(df) >= 288 else float(df['close'].iloc[0])  # 24H 前價格 (288根 5m)
            curr_c = float(last_row['close'])  # 最新收盤價
            change_24h = (curr_c - prev_close) / prev_close * 100  # 24H 漲跌幅

            # 標記商品支援策略
            supports_scalper = sym in self.scalper_symbols  # 是否支援夜間剝頭皮
            supports_straddle = sym in self.straddle_symbols  # 是否支援跨式賣方

            symbols_meta[sym] = {  # 構建商品中繼資訊
                "symbol": sym,  # 貨幣對
                "current_price": round(curr_c, 5),  # 最新價格
                "price_change_24h_pct": round(change_24h, 2),  # 24H 漲跌幅
                "high_24h": round(float(df['high'].iloc[-288:].max()), 5) if len(df) >= 288 else round(float(df['high'].max()), 5),  # 24H 最高
                "low_24h": round(float(df['low'].iloc[-288:].min()), 5) if len(df) >= 288 else round(float(df['low'].min()), 5),  # 24H 最低
                "current_rsi": round(float(last_row['RSI']), 1) if not np.isnan(last_row['RSI']) else 50.0,  # 最新 RSI
                "current_zscore": round(float(last_row['Z']), 2) if not np.isnan(last_row['Z']) else 0.0,  # 最新 Z-Score
                "supports_scalper": supports_scalper,  # 是否包含在 Scalper
                "supports_straddle": supports_straddle,  # 是否包含在 Straddle
                "is_scalper_session": (now_utc.hour >= 21) or (now_utc.hour <= 6),  # 當前是否在夜間收租時段
                "is_straddle_session": 7 <= now_utc.hour <= 20  # 當前是否在日間跨式時段
            }  # 商品資訊結束

            # 抽取最近 800 根供圖表繪製
            df_chart = df.tail(800).copy()  # 取最近 800 筆
            chart_data_dict[sym] = {  # 圖表數據封包
                "timestamps": [t.strftime('%Y-%m-%d %H:%M') for t in df_chart.index],  # 時間陣列
                "open": [round(float(x), 5) for x in df_chart['open']],  # 開盤價
                "high": [round(float(x), 5) for x in df_chart['high']],  # 最高價
                "low": [round(float(x), 5) for x in df_chart['low']],  # 最低價
                "close": [round(float(x), 5) for x in df_chart['close']],  # 收盤價
                "volume": [round(float(x), 1) for x in df_chart['volume']],  # 成交量
                "bb_upper": [round(float(x), 5) if not np.isnan(x) else None for x in df_chart['UB']],  # 布林上軌
                "bb_mid": [round(float(x), 5) if not np.isnan(x) else None for x in df_chart['MA20']],  # 布林中軌
                "bb_lower": [round(float(x), 5) if not np.isnan(x) else None for x in df_chart['LB']],  # 布林下軌
                "rsi": [round(float(x), 1) if not np.isnan(x) else None for x in df_chart['RSI']],  # RSI 指標
                "z_score": [round(float(x), 2) if not np.isnan(x) else None for x in df_chart['Z']]  # Z-Score 指標
            }  # 圖表封包結束

        # 4. 計算整體組合 (Portfolio 8 Modules) 關鍵綜合指標
        portfolio_total_trades = len(all_completed_trades)  # 組合總交易次數
        portfolio_wins = sum(1 for t in all_completed_trades if t['win'])  # 組合總獲利次數
        portfolio_losses = portfolio_total_trades - portfolio_wins  # 組合總虧損次數
        portfolio_win_rate = round(portfolio_wins / portfolio_total_trades * 100, 1) if portfolio_total_trades > 0 else 0.0  # 組合總勝率
        portfolio_pnl = sum(t['pnl_usd'] for t in all_completed_trades)  # 組合總淨利美金
        portfolio_win_usd = sum(t['pnl_usd'] for t in all_completed_trades if t['pnl_usd'] > 0)  # 總獲利美金
        portfolio_loss_usd = sum(abs(t['pnl_usd']) for t in all_completed_trades if t['pnl_usd'] < 0)  # 總虧損美金
        portfolio_pf = round(portfolio_win_usd / (portfolio_loss_usd + 1e-9), 2) if portfolio_loss_usd > 0 else (99.0 if portfolio_wins > 0 else 0.0)  # 組合 PF

        # 計算模組個別統計表
        modules_summary = []  # 模組統計清單
        for m in module_results:  # 遍歷模組
            modules_summary.append({  # 加入模組摘要
                "module_id": f"{'Scalper' if 'Scalper' in m['strategy'] else 'Straddle'}_{m['symbol']}",  # 唯一標識
                "strategy": m['strategy'],  # 策略名稱
                "symbol": m['symbol'],  # 貨幣對
                "trades_count": m['metrics']['total_trades'],  # 交易次數
                "wins": m['metrics']['wins'],  # 獲利次數
                "losses": m['metrics']['losses'],  # 虧損次數
                "win_rate": m['metrics']['win_rate'],  # 勝率
                "total_pnl_usd": m['metrics']['total_pnl_usd'],  # 總淨利 (USD)
                "profit_factor": m['metrics']['profit_factor'],  # 獲利因子
                "max_drawdown_pct": m['metrics']['max_drawdown_pct'],  # 最大回撤 (%)
                "max_drawdown_usd": m['metrics']['max_drawdown_usd'],  # 最大回撤 (USD)
                "roi_pct": m['metrics']['roi_pct']  # 投報率 (%)
            })  # 結束摘要

        # 建立按時間對齊的綜合權益曲線 (各模組依平倉時間聚合)
        trades_chronological = sorted(all_completed_trades, key=lambda x: x['exit_time'])  # 依平倉時間正序
        combined_equity_curve = [{"time": "2024-01-01 00:00:00", "balance": 100000.0, "pnl": 0.0}]  # 初始起始點
        running_bal = 100000.0  # 當前累計淨值
        for t in trades_chronological:  # 依序累加
            running_bal += t['pnl_usd']  # 累計損益
            combined_equity_curve.append({  # 記錄節點
                "time": t['exit_time'],  # 時間點
                "balance": round(running_bal, 2),  # 當前權益
                "pnl": t['pnl_usd'],  # 本筆損益
                "symbol": t['symbol'],  # 交易標的
                "strategy": t['strategy']  # 交易策略
            })  # 結束節點

        # 計算組合歷史最大回撤
        comb_series = pd.Series([r['balance'] for r in combined_equity_curve])  # 轉 Series
        comb_cum_max = comb_series.cummax()  # 歷史新高
        comb_dd_series = (comb_series - comb_cum_max) / comb_cum_max * 100  # 回撤百分比
        portfolio_mdd_pct = round(abs(comb_dd_series.min()), 2) if len(comb_dd_series) > 0 else 0.0  # 組合最大回撤百分比
        portfolio_mdd_usd = round(abs((comb_series - comb_cum_max).min()), 2) if len(comb_series) > 0 else 0.0  # 組合最大回撤美金

        # 構建最終輸出 JSON 結構
        payload = {  # 總資料物件
            "system_info": {  # 系統資訊
                "title": "5m 純日內雙策略 8 商品極限收租監控儀表板",  # 標題
                "last_updated_utc": now_utc.strftime('%Y-%m-%d %H:%M:%S UTC'),  # UTC 時間
                "last_updated_tpe": now_tpe.strftime('%Y-%m-%d %H:%M:%S (UTC+8)'),  # 台北時間
                "symbols_count": len(self.all_symbols),  # 標的數量
                "modules_count": len(module_results)  # 模組數量
            },  # 系統資訊結束
            "portfolio_metrics": {  # 總組合核心 KPI
                "total_trades": portfolio_total_trades,  # 總交易次數
                "wins": portfolio_wins,  # 獲利次數
                "losses": portfolio_losses,  # 虧損次數
                "win_rate": portfolio_win_rate,  # 綜合勝率
                "total_pnl_usd": round(portfolio_pnl, 2),  # 總淨利 (USD)
                "profit_factor": portfolio_pf,  # 獲利因子
                "max_drawdown_pct": portfolio_mdd_pct,  # 最大回撤 (%)
                "max_drawdown_usd": portfolio_mdd_usd,  # 最大回撤 (USD)
                "roi_pct": round(portfolio_pnl / 100000.0 * 100, 2),  # 總投報率
                "initial_capital": 100000.0,  # 初始本金
                "current_capital": round(100000.0 + portfolio_pnl, 2)  # 當前結算本金
            },  # 組合 KPI 結束
            "modules_summary": modules_summary,  # 8 大模組指標明細
            "symbols_meta": symbols_meta,  # 7 大貨幣對即時狀態
            "active_positions": active_positions_list,  # 即時未平倉活躍持倉
            "combined_equity_curve": combined_equity_curve,  # 組合權益曲線
            "all_trades": all_completed_trades,  # 全部歷史交易明細
            "chart_data": chart_data_dict  # 7 大貨幣對圖表 K 線與指標數據
        }  # 總資料結束

        # 輸出 strategy_results.json
        output_json_path = os.path.join(os.path.dirname(__file__), "strategy_results.json")  # 輸出路徑
        with open(output_json_path, "w", encoding="utf-8") as f:  # 開啟檔案
            json.dump(payload, f, ensure_ascii=False, indent=2)  # 寫入 JSON
        print(f"[+] 策略回測數據已成功輸出至: {output_json_path}")  # 輸出成功日誌

        # 輸出 all_trades_history.csv
        output_csv_path = os.path.join(os.path.dirname(__file__), "all_trades_history.csv")  # CSV 輸出路徑
        pd.DataFrame(all_completed_trades).to_csv(output_csv_path, index=False, encoding="utf-8-sig")  # 輸出 CSV
        print(f"[+] 完整歷史交易明細已輸出至: {output_csv_path}")  # 輸出成功日誌

        return payload  # 回傳資料

if __name__ == "__main__":  # 程式執行主入口
    engine = PureIntraday5mStrategyEngine()  # 建立引擎實例
    engine.execute_all_and_generate_payload()  # 啟動全量運算
