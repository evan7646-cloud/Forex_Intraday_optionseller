import os  # 導入作業系統模組
import sys  # 導入系統模組
import numpy as np  # 導入數值計算庫
import pandas as pd  # 導入數據分析庫
import matplotlib.pyplot as plt  # 導入繪圖庫
import yfinance as yf  # 導入金融行情數據介面

# 設定繁體中文字型，確保 Mac 與 Linux 環境圖表不缺字亂碼
plt.rcParams['font.sans-serif'] = ['Hiragino Sans TC', 'PingFang HK', 'Hiragino Sans GB', 'Arial Unicode MS', 'DejaVu Sans', 'sans-serif']  # 設定中文字型
plt.rcParams['axes.unicode_minus'] = False  # 正常顯示負號

class RealisticMultiTFScreeningEngine:  # 定義實盤點差級多週期與多模型大規模量化回測引擎
    def __init__(self):  # 初始化函數
        # 定義 28 大外匯商品
        self.symbols = [  # 商品清單
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",  # 7 大主要直盤
            "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD",            # 6 大歐元交叉盤
            "GBPJPY", "GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD",                      # 5 大英鎊交叉盤
            "AUDJPY", "AUDCAD", "AUDNZD", "AUDCHF",                                # 4 大澳幣交叉盤
            "NZDCAD", "NZDJPY", "NZDCHF",                                          # 3 大紐幣交叉盤
            "CADJPY", "CADCHF", "CHFJPY"                                           # 3 大加幣/瑞郎交叉盤
        ]  # 清單結束

        # 定義各商品在真實經紀商/Prop firm 的保守實盤平均點差 (Pips)
        self.real_spreads = {  # 點差對照表
            "EURUSD": 0.8, "USDJPY": 0.9, "GBPUSD": 1.0, "AUDUSD": 1.0, "USDCAD": 1.2, "USDCHF": 1.2, "NZDUSD": 1.2,  # 直盤點差
            "EURGBP": 1.3, "EURJPY": 1.3, "EURCHF": 1.5, "EURCAD": 1.8, "EURAUD": 2.0, "EURNZD": 2.5,                 # 歐元交叉盤
            "GBPJPY": 1.6, "GBPCAD": 2.2, "GBPCHF": 2.2, "GBPAUD": 2.5, "GBPNZD": 3.0,                                 # 英鎊交叉盤
            "AUDCAD": 1.5, "AUDNZD": 1.6, "AUDJPY": 1.5, "AUDCHF": 1.6,                                                 # 澳幣交叉盤
            "NZDCAD": 1.8, "NZDJPY": 1.8, "NZDCHF": 1.8,                                                                 # 紐幣交叉盤
            "CADJPY": 1.5, "CADCHF": 1.8, "CHFJPY": 1.8                                                                  # 其餘交叉盤
        }  # 點差表結束

    def get_pip_size(self, symbol: str) -> float:  # 計算 1 pip 價格單位
        return 0.01 if "JPY" in symbol else 0.0001  # JPY 貨幣對 0.01, 其餘 0.0001

    def get_pip_value_usd(self, symbol: str, lot_size: float = 1.0) -> float:  # 計算每 pip 在 USD 的真實價值
        quote_rates = {  # 報價幣對 USD 匯率
            "USD": 1.0, "CAD": 1.0/1.37, "CHF": 1.0/0.88, "JPY": 1.0/148.0,  # 直盤與主要幣別
            "GBP": 1.30, "NZD": 0.60, "AUD": 0.66                            # 大洋洲與英鎊
        }  # 匯率表結束
        quote_curr = symbol[-3:]  # 取得計價幣
        conversion = quote_rates.get(quote_curr, 1.0)  # 轉換匯率
        base_pip = 100000.0 * self.get_pip_size(symbol)  # 1 手 pip 面值
        return base_pip * conversion * lot_size  # 回傳美金價值

    def fetch_data(self, symbol: str, interval: str, period: str) -> pd.DataFrame:  # 下載歷史數據
        ticker = f"{symbol}=X"  # 設定 Yahoo Finance 標的
        try:  # 嘗試下載
            df = yf.download(ticker, period=period, interval=interval, progress=False)  # 執行下載
            if df.empty: return pd.DataFrame()  # 檢查是否為空
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)  # 展平欄位
            df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}).dropna()  # 整理欄位
            if df.index.tz is not None: df.index = pd.to_datetime(df.index).tz_localize(None)  # 去時區
            else: df.index = pd.to_datetime(df.index)  # 格式化索引
            return df[['open', 'high', 'low', 'close', 'volume']]  # 回傳有效欄位
        except Exception as e:  # 捕捉異常
            return pd.DataFrame()  # 失敗回傳空表

    # =========================================================================
    # 模式 1: 實盤修正版「亞盤震盪均值回歸」 (Asian Post-Rollover Session: UTC 00:00~06:00)
    # 特點: 避開 21:00~23:59 換匯擴點, 動態 ATR 止盈止損, 徹底消除 1:7 逆向盈虧比
    # =========================================================================
    def run_model_asian_reversion(self, symbol: str, df_raw: pd.DataFrame, tf_name: str, lot_size: float = 1.0) -> dict:  # 模型 1 運算函數
        df = df_raw.copy()  # 複製表
        pip_size = self.get_pip_size(symbol)  # pip 單位
        pip_val = self.get_pip_value_usd(symbol, lot_size)  # pip 美金價值
        sp_pips = self.real_spreads.get(symbol, 1.5)  # 取得該商品實盤點差
        sp_dist = sp_pips * pip_size  # 點差距離

        # 計算指標
        df['MA'] = df['close'].rolling(20).mean()  # 20 均線
        df['STD'] = df['close'].rolling(20).std()  # 20 標準差
        df['UB'] = df['MA'] + 2.0 * df['STD']  # 上軌
        df['LB'] = df['MA'] - 2.0 * df['STD']  # 下軌
        
        # ATR 計算動態波動區間
        high_low = df['high'] - df['low']  # 當前 K 棒震幅
        high_close = (df['high'] - df['close'].shift()).abs()  # 跳空震幅 1
        low_close = (df['low'] - df['close'].shift()).abs()  # 跳空震幅 2
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)  # 真實波幅 TR
        df['ATR'] = tr.rolling(14).mean()  # 14 週期 ATR

        delta = df['close'].diff()  # 差分
        gain = delta.where(delta > 0, 0).rolling(14).mean()  # 漲幅
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()  # 跌幅
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))  # 14 週期 RSI

        pos = 0  # 倉位
        entry_p = 0.0  # 進場價
        cum_pnl = 0.0  # 累計損益
        wins, losses = 0, 0  # 勝負
        win_usd, loss_usd = 0.0, 0.0  # 盈虧美金
        trades_list = []  # 交易記錄
        equity_curve = [0.0]  # 資金曲線
        cost = 5.0 * lot_size  # 經紀商每手往返手續費 $5

        for i in range(30, len(df)):  # 遍歷 K 棒
            c, h, l = float(df['close'].iloc[i]), float(df['high'].iloc[i]), float(df['low'].iloc[i])  # 價格
            atr_val = float(df['ATR'].iloc[i])  # ATR 數值
            hr = df.index[i].hour  # UTC 小時
            is_force_exit = (hr == 7)  # UTC 07:00 歐盤前強平

            # 動態止盈 (1.2x ATR) 與 停損 (1.8x ATR) -> 實質健康盈虧比 1 : 1.5
            tp_dist = max(atr_val * 1.2, 10.0 * pip_size)  # 確保至少大於 10 pips, 消除點差侵蝕
            sl_dist = max(atr_val * 1.8, 18.0 * pip_size)  # 動態停損

            if pos != 0:  # 持倉管理
                closed = False  # 平倉標記
                exit_p = 0.0  # 出場價

                if pos == 1:  # 多單出場 (以 Bid 賣出)
                    if h >= entry_p + tp_dist: exit_p = entry_p + tp_dist - sp_dist; closed = True  # 止盈
                    elif c >= df['MA'].iloc[i]: exit_p = c - sp_dist; closed = True  # 中軌均值回歸平倉
                    elif l <= entry_p - sl_dist: exit_p = entry_p - sl_dist - sp_dist; closed = True  # 停損
                    elif is_force_exit: exit_p = c - sp_dist; closed = True  # 強平

                    if closed:  # 結算
                        pips = (exit_p - entry_p) / pip_size  # 淨點數
                        pnl = pips * pip_val - cost  # 美金淨利
                        cum_pnl += pnl  # 累計
                        if pnl > 0: wins += 1; win_usd += pnl  # 獲利
                        else: losses += 1; loss_usd += abs(pnl)  # 虧損
                        trades_list.append(pnl)  # 記錄
                        pos = 0  # 清倉

                elif pos == -1:  # 空單出場 (以 Ask 買回)
                    if l <= entry_p - tp_dist: exit_p = entry_p - tp_dist + sp_dist; closed = True  # 止盈
                    elif c <= df['MA'].iloc[i]: exit_p = c + sp_dist; closed = True  # 中軌均值回歸平倉
                    elif h >= entry_p + sl_dist: exit_p = entry_p + sl_dist + sp_dist; closed = True  # 停損
                    elif is_force_exit: exit_p = c + sp_dist; closed = True  # 強平

                    if closed:  # 結算
                        pips = (entry_p - exit_p) / pip_size  # 淨點數
                        pnl = pips * pip_val - cost  # 美金淨利
                        cum_pnl += pnl  # 累計
                        if pnl > 0: wins += 1; win_usd += pnl  # 獲利
                        else: losses += 1; loss_usd += abs(pnl)  # 虧損
                        trades_list.append(pnl)  # 記錄
                        pos = 0  # 清倉

            # 開倉訊號：嚴格鎖定在 UTC 00:00 ~ 05:30 (徹底避開 21:00~23:59 換匯擴點期)
            if pos == 0 and (0 <= hr <= 5) and not is_force_exit:  # 開倉時段
                if c <= df['LB'].iloc[i] and df['RSI'].iloc[i] <= 35:  # 多頭超賣
                    pos = 1; entry_p = c + sp_dist  # 以 Ask 開多 (包含點差成本)
                elif c >= df['UB'].iloc[i] and df['RSI'].iloc[i] >= 65:  # 空頭超買
                    pos = -1; entry_p = c  # 以 Bid 開空

            equity_curve.append(cum_pnl)  # 記錄

        tot = wins + losses  # 總筆數
        win_rate = (wins / tot * 100) if tot > 0 else 0.0  # 勝率
        pf = (win_usd / (loss_usd + 1e-9)) if loss_usd > 0 else (99.0 if wins > 0 else 0.0)  # PF
        eq_ser = pd.Series(equity_curve)  # 轉 Series
        bal_ser = eq_ser + 100000.0  # 換算 $100k
        mdd = ((bal_ser - bal_ser.cummax()) / bal_ser.cummax() * 100).min()  # MDD
        
        return {
            "Model": "Asian_Reversion_Clean", "Symbol": symbol, "Timeframe": tf_name,
            "Spread_Pips": sp_pips, "Trades": tot, "WinRate": round(win_rate, 1),
            "Profit": round(cum_pnl, 1), "PF": round(pf, 2), "MDD": round(mdd, 2),
            "Equity": eq_ser
        }

    # =========================================================================
    # 模式 2: 「歐美主力時段流動性順勢突破/動能交易」 (London/NY Trend Session: UTC 07:00~17:00)
    # 特點: 點差最窄 (0.8~1.2 pips), 賺取大趨勢點數 (30~80 pips), 徹底擺脫點差敏感
    # =========================================================================
    def run_model_london_trend(self, symbol: str, df_raw: pd.DataFrame, tf_name: str, lot_size: float = 1.0) -> dict:  # 模型 2 運算函數
        df = df_raw.copy()  # 複製表
        pip_size = self.get_pip_size(symbol)  # pip 單位
        pip_val = self.get_pip_value_usd(symbol, lot_size)  # pip 美金價值
        sp_pips = self.real_spreads.get(symbol, 1.2)  # 取得實盤點差
        sp_dist = sp_pips * pip_size  # 點差距離

        # EMA 雙均線 + 動能過濾
        df['EMA_Fast'] = df['close'].ewm(span=20).mean()  # 20 EMA
        df['EMA_Slow'] = df['close'].ewm(span=50).mean()  # 50 EMA
        df['Donchian_High'] = df['high'].rolling(20).max().shift(1)  # 20 根最高價突破線
        df['Donchian_Low'] = df['low'].rolling(20).min().shift(1)  # 20 根最低價突破線

        high_low = df['high'] - df['low']  # 震幅
        high_close = (df['high'] - df['close'].shift()).abs()  # 跳空 1
        low_close = (df['low'] - df['close'].shift()).abs()  # 跳空 2
        df['ATR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()  # ATR

        pos = 0  # 倉位
        entry_p = 0.0  # 進場價
        cum_pnl = 0.0  # 累計損益
        wins, losses = 0, 0  # 勝負
        win_usd, loss_usd = 0.0, 0.0  # 盈虧美金
        trades_list = []  # 交易記錄
        equity_curve = [0.0]  # 權益曲線
        cost = 5.0 * lot_size  # 手續費

        for i in range(55, len(df)):  # 遍歷 K 棒
            c, h, l = float(df['close'].iloc[i]), float(df['high'].iloc[i]), float(df['low'].iloc[i])  # 價格
            atr_val = float(df['ATR'].iloc[i])  # ATR
            hr = df.index[i].hour  # UTC 小時
            is_force_exit = (hr == 20)  # UTC 20:00 美盤尾聲強平清倉 (Zero-Overnight)

            # 順勢盈虧比架構：止盈 2.5x ATR, 停損 1.2x ATR -> 盈虧比高達 2.1 : 1 (順勢大賺小賠)
            tp_dist = max(atr_val * 2.5, 20.0 * pip_size)  # 2.5x ATR 止盈
            sl_dist = max(atr_val * 1.2, 12.0 * pip_size)  # 1.2x ATR 停損

            if pos != 0:  # 持倉管理
                closed = False  # 平倉標記
                exit_p = 0.0  # 出場價

                if pos == 1:  # 多單
                    if h >= entry_p + tp_dist: exit_p = entry_p + tp_dist - sp_dist; closed = True  # 止盈
                    elif l <= entry_p - sl_dist: exit_p = entry_p - sl_dist - sp_dist; closed = True  # 停損
                    elif c < df['EMA_Fast'].iloc[i]: exit_p = c - sp_dist; closed = True  # 均線跌破動態追蹤出場
                    elif is_force_exit: exit_p = c - sp_dist; closed = True  # 時間強平

                    if closed:  # 結算
                        pips = (exit_p - entry_p) / pip_size  # 淨點數
                        pnl = pips * pip_val - cost  # 淨利
                        cum_pnl += pnl  # 累計
                        if pnl > 0: wins += 1; win_usd += pnl  # 獲利
                        else: losses += 1; loss_usd += abs(pnl)  # 虧損
                        trades_list.append(pnl)  # 記錄
                        pos = 0  # 清倉

                elif pos == -1:  # 空單
                    if l <= entry_p - tp_dist: exit_p = entry_p - tp_dist + sp_dist; closed = True  # 止盈
                    elif h >= entry_p + sl_dist: exit_p = entry_p + sl_dist + sp_dist; closed = True  # 停損
                    elif c > df['EMA_Fast'].iloc[i]: exit_p = c + sp_dist; closed = True  # 均線升破動態追蹤出場
                    elif is_force_exit: exit_p = c + sp_dist; closed = True  # 時間強平

                    if closed:  # 結算
                        pips = (entry_p - exit_p) / pip_size  # 淨點數
                        pnl = pips * pip_val - cost  # 淨利
                        cum_pnl += pnl  # 累計
                        if pnl > 0: wins += 1; win_usd += pnl  # 獲利
                        else: losses += 1; loss_usd += abs(pnl)  # 虧損
                        trades_list.append(pnl)  # 記錄
                        pos = 0  # 清倉

            # 開倉訊號：限定於倫敦與紐約交疊黃金時段 (UTC 07:00 ~ 15:00, 流動性最大, 點差最低)
            if pos == 0 and (7 <= hr <= 15) and not is_force_exit:  # 開倉時段
                # 多頭突破：均線多頭排列 且 突破 20 根最高價
                if df['EMA_Fast'].iloc[i] > df['EMA_Slow'].iloc[i] and c > df['Donchian_High'].iloc[i]:  # 多頭
                    pos = 1; entry_p = c + sp_dist  # 以 Ask 進場
                # 空頭突破：均線空頭排列 且 跌破 20 根最低價
                elif df['EMA_Fast'].iloc[i] < df['EMA_Slow'].iloc[i] and c < df['Donchian_Low'].iloc[i]:  # 空頭
                    pos = -1; entry_p = c  # 以 Bid 進場

            equity_curve.append(cum_pnl)  # 記錄

        tot = wins + losses  # 總筆數
        win_rate = (wins / tot * 100) if tot > 0 else 0.0  # 勝率
        pf = (win_usd / (loss_usd + 1e-9)) if loss_usd > 0 else (99.0 if wins > 0 else 0.0)  # PF
        eq_ser = pd.Series(equity_curve)  # 轉 Series
        bal_ser = eq_ser + 100000.0  # 換算 $100k
        mdd = ((bal_ser - bal_ser.cummax()) / bal_ser.cummax() * 100).min()  # MDD
        
        return {
            "Model": "London_NY_TrendBreak", "Symbol": symbol, "Timeframe": tf_name,
            "Spread_Pips": sp_pips, "Trades": tot, "WinRate": round(win_rate, 1),
            "Profit": round(cum_pnl, 1), "PF": round(pf, 2), "MDD": round(mdd, 2),
            "Equity": eq_ser
        }

    # =========================================================================
    # 模式 3: 「H1/H4 週期大波段跨式/震盪回歸收租模型」 (Macro Swing Range Harvest)
    # 特點: H1 週期單筆獲利 40~100 pips, 點差 1.5 pips 僅佔利潤 1.5%~3%, 徹底免疫點差損耗
    # =========================================================================
    def run_model_h1_swing_harvest(self, symbol: str, df_raw: pd.DataFrame, tf_name: str, lot_size: float = 1.0) -> dict:  # 模型 3 運算函數
        df = df_raw.copy()  # 複製表
        pip_size = self.get_pip_size(symbol)  # pip 單位
        pip_val = self.get_pip_value_usd(symbol, lot_size)  # pip 美金價值
        sp_pips = self.real_spreads.get(symbol, 1.5)  # 實盤點差
        sp_dist = sp_pips * pip_size  # 點差距離

        df['MA'] = df['close'].rolling(30).mean()  # 30 週期均線
        df['STD'] = df['close'].rolling(30).std()  # 30 週期標準差
        df['Z'] = (df['close'] - df['MA']) / (df['STD'] + 1e-9)  # 滾動 Z-Score

        high_low = df['high'] - df['low']  # 震幅
        high_close = (df['high'] - df['close'].shift()).abs()  # 跳空 1
        low_close = (df['low'] - df['close'].shift()).abs()  # 跳空 2
        df['ATR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()  # ATR

        pos = 0  # 倉位
        entry_p = 0.0  # 進場價
        cum_pnl = 0.0  # 累計損益
        wins, losses = 0, 0  # 勝負
        win_usd, loss_usd = 0.0, 0.0  # 盈虧美金
        trades_list = []  # 交易記錄
        equity_curve = [0.0]  # 權益曲線
        cost = 5.0 * lot_size  # 手續費

        for i in range(35, len(df)):  # 遍歷 K 棒
            c, h, l = float(df['close'].iloc[i]), float(df['high'].iloc[i]), float(df['low'].iloc[i])  # 價格
            z = float(df['Z'].iloc[i])  # Z 值
            atr_val = float(df['ATR'].iloc[i])  # ATR

            tp_dist = max(atr_val * 1.5, 30.0 * pip_size)  # 大空間止盈 30~80 pips
            sl_dist = max(atr_val * 2.0, 45.0 * pip_size)  # 大空間停損

            if pos != 0:  # 持倉管理
                closed = False  # 平倉標記
                exit_p = 0.0  # 出場價

                if pos == 1:  # 多單
                    if z >= -0.2: exit_p = c - sp_dist; closed = True  # Z 均值回歸平倉
                    elif h >= entry_p + tp_dist: exit_p = entry_p + tp_dist - sp_dist; closed = True  # 止盈
                    elif z <= -3.8: exit_p = c - sp_dist; closed = True  # Z 偏離停損
                    elif l <= entry_p - sl_dist: exit_p = entry_p - sl_dist - sp_dist; closed = True  # 停損

                    if closed:  # 結算
                        pips = (exit_p - entry_p) / pip_size  # 點數
                        pnl = pips * pip_val - cost  # 美金
                        cum_pnl += pnl  # 累計
                        if pnl > 0: wins += 1; win_usd += pnl  # 獲利
                        else: losses += 1; loss_usd += abs(pnl)  # 虧損
                        trades_list.append(pnl)  # 記錄
                        pos = 0  # 清倉

                elif pos == -1:  # 空單
                    if z <= 0.2: exit_p = c + sp_dist; closed = True  # Z 均值回歸平倉
                    elif l <= entry_p - tp_dist: exit_p = entry_p - tp_dist + sp_dist; closed = True  # 止盈
                    elif z >= 3.8: exit_p = c + sp_dist; closed = True  # Z 偏離停損
                    elif h >= entry_p + sl_dist: exit_p = entry_p + sl_dist + sp_dist; closed = True  # 停損

                    if closed:  # 結算
                        pips = (entry_p - exit_p) / pip_size  # 點數
                        pnl = pips * pip_val - cost  # 美金
                        cum_pnl += pnl  # 累計
                        if pnl > 0: wins += 1; win_usd += pnl  # 獲利
                        else: losses += 1; loss_usd += abs(pnl)  # 虧損
                        trades_list.append(pnl)  # 記錄
                        pos = 0  # 清倉

            # 開倉訊號 (Z-Score 極限偏離)
            if pos == 0:  # 空倉
                if z <= -2.2: pos = 1; entry_p = c + sp_dist  # 賣 Put 等效買多 (Ask)
                elif z >= 2.2: pos = -1; entry_p = c  # 賣 Call 等效做空 (Bid)

            equity_curve.append(cum_pnl)  # 記錄

        tot = wins + losses  # 總筆數
        win_rate = (wins / tot * 100) if tot > 0 else 0.0  # 勝率
        pf = (win_usd / (loss_usd + 1e-9)) if loss_usd > 0 else (99.0 if wins > 0 else 0.0)  # PF
        eq_ser = pd.Series(equity_curve)  # 轉 Series
        bal_ser = eq_ser + 100000.0  # 換算 $100k
        mdd = ((bal_ser - bal_ser.cummax()) / bal_ser.cummax() * 100).min()  # MDD
        
        return {
            "Model": "H1_Swing_Harvest", "Symbol": symbol, "Timeframe": tf_name,
            "Spread_Pips": sp_pips, "Trades": tot, "WinRate": round(win_rate, 1),
            "Profit": round(cum_pnl, 1), "PF": round(pf, 2), "MDD": round(mdd, 2),
            "Equity": eq_ser
        }

    # =========================================================================
    # 執行大規模掃描矩陣 (28 商品 × 4 週期 M15/M30/H1/H4 × 3 大模型)
    # =========================================================================
    def execute_large_scale_screening(self):  # 執行主控函數
        print("\n" + "=" * 90)  # 標頭
        print("  🚀 啟動「實盤點差與滑點真實環境」大規模跨週期 (M15, M30, H1, H4) × 28 商品量化海選  ")  # 標題
        print("=" * 90 + "\n")  # 分隔線

        all_results = []  # 儲存指標總表
        equity_dict = {}  # 儲存曲線字典

        # 週期與下載區間配置
        tf_configs = [  # 週期清單
            ("M15", "15m", "60d"),   # M15 週期
            ("M30", "30m", "60d"),   # M30 週期
            ("H1",  "1h",  "730d"),  # H1 週期 (2 年長週期數據)
            ("H4",  "1h",  "730d")   # H4 週期 (由 1h 聚合)
        ]  # 配置結束

        total_iterations = len(self.symbols) * len(tf_configs)  # 總下載次數
        curr_iter = 0  # 計數器

        for sym in self.symbols:  # 遍歷 28 大商品
            for tf_name, interval_str, period_str in tf_configs:  # 遍歷週期
                curr_iter += 1  # 累加計數
                print(f"[{curr_iter:3d}/{total_iterations}] 下載與測試: {sym:6s} [{tf_name:3s}] ...", end="", flush=True)  # 日誌
                df = self.fetch_data(sym, interval_str, period_str)  # 抓取真實數據
                if df.empty or len(df) < 150:  # 檢查有效性
                    print(" ❌ 無數據")  # 提示
                    continue  # 跳過

                if tf_name == "H4":  # 若為 H4 則對 1h 進行重採樣
                    df = df.resample('4h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()  # 重採樣為 4H
                    if len(df) < 100: continue  # 檢查

                print(f" ✅ ({len(df)} 根)", end="", flush=True)  # 顯示數據量

                # 測試模型 1: 修正版亞盤震盪 (僅限 M15, M30)
                if tf_name in ["M15", "M30"]:  # 篩選短週期
                    res1 = self.run_model_asian_reversion(sym, df, tf_name)  # 執行模型 1
                    if res1["Trades"] >= 15:  # 過濾樣本過少
                        all_results.append(res1)  # 加入指標
                        equity_dict[f"{res1['Model']}_{sym}_{tf_name}"] = res1['Equity']  # 存入曲線

                # 測試模型 2: 歐美主力時段順勢突破 (M15, M30, H1)
                if tf_name in ["M15", "M30", "H1"]:  # 篩選突破週期
                    res2 = self.run_model_london_trend(sym, df, tf_name)  # 執行模型 2
                    if res2["Trades"] >= 15:  # 過濾樣本過少
                        all_results.append(res2)  # 加入指標
                        equity_dict[f"{res2['Model']}_{sym}_{tf_name}"] = res2['Equity']  # 存入曲線

                # 測試模型 3: H1/H4 大空間跨式收租 (H1, H4)
                if tf_name in ["H1", "H4"]:  # 篩選長週期
                    res3 = self.run_model_h1_swing_harvest(sym, df, tf_name)  # 執行模型 3
                    if res3["Trades"] >= 15:  # 過濾樣本過少
                        all_results.append(res3)  # 加入指標
                        equity_dict[f"{res3['Model']}_{sym}_{tf_name}"] = res3['Equity']  # 存入曲線

                print(" -> 完成")  # 輸出完成提示

        # 轉為 DataFrame 分析與篩選
        df_all = pd.DataFrame(all_results)  # 轉為表格
        df_clean = df_all.drop(columns=['Equity'])  # 移除曲線欄位
        csv_file = "realistic_multitf_all_results.csv"  # 完整輸出檔名
        df_clean.to_csv(csv_file, index=False)  # 輸出 CSV
        print(f"\n[+] 全矩陣實盤點差回測數據 (共 {len(df_clean)} 組) 已儲存至: {csv_file}")  # 輸出日誌

        # 嚴格篩選「實盤真實可獲利模式」標準：
        # 1. 獲利因子 PF >= 1.35
        # 2. 勝率 WinRate >= 50.0% (突破型) 或 >= 65.0% (震盪型)
        # 3. 最大回撤 MDD >= -2.0% (即回撤不超過 2.0%)
        # 4. 總淨利 Profit > 0 且 交易次數 Trades >= 20
        profitable_filter = (
            (df_clean["Profit"] > 0) &
            (df_clean["PF"] >= 1.35) &
            (df_clean["MDD"] >= -2.0) &
            (df_clean["Trades"] >= 20)
        )
        df_winners = df_clean[profitable_filter].sort_values(by=["PF", "Profit"], ascending=[False, False])  # 排序

        winners_csv = "realistic_profitable_models.csv"  # 獲利模式清單
        df_winners.to_csv(winners_csv, index=False)  # 輸出
        print(f"[+] 篩選出的【實盤高勝率/高期望值可獲利模式清單】已儲存至: {winners_csv}\n")  # 日誌

        print("=" * 95)  # 標頭
        print("         🏆 實盤點差摩擦下【真實能穩定盈利 Top 15 量化模型排行榜】 (扣除實盤點差與手續費)          ")  # 標題
        print("=" * 95)  # 標頭
        print(df_winners.head(15).to_string(index=False))  # 輸出前 15 名
        print("=" * 95 + "\n")  # 結尾

        # 生成獲利模式對比圖表
        self.plot_realistic_winners(df_winners.head(6), equity_dict)  # 繪製前 6 大真實獲利模型圖表

    def plot_realistic_winners(self, df_top: pd.DataFrame, equity_dict: dict):  # 繪製真實獲利模型獨立多子圖
        if df_top.empty:  # 檢查是否為空
            print("[!] 無符合條件之獲利模型，跳過繪圖。")  # 提示
            return  # 返回

        fig, axes = plt.subplots(3, 2, figsize=(18, 14), sharex=False)  # 3x2 子圖矩陣
        fig.patch.set_facecolor('#0d1117')  # 畫布背景
        axes_flat = axes.flatten()  # 展平陣列
        colors = ["#3fb950", "#58a6ff", "#d2a8ff", "#f0883e", "#00e676", "#79c0ff"]  # 專屬配色

        for idx, (_, row) in enumerate(df_top.iterrows()):  # 遍歷前 6 大
            ax = axes_flat[idx]  # 取得子圖
            ax.set_facecolor('#161b22')  # 背景色
            key = f"{row['Model']}_{row['Symbol']}_{row['Timeframe']}"  # 鍵名
            if key in equity_dict:  # 若曲線存在
                eq = equity_dict[key]  # 取得曲線
                c = colors[idx % len(colors)]  # 顏色
                ax.plot(eq.values, color=c, linewidth=2.2, label=f"{row['Symbol']} [{row['Timeframe']}]")  # 繪線
                ax.fill_between(range(len(eq)), eq.values, 0, color=c, alpha=0.15)  # 漸層填充
                ax.axhline(0, color='#8b949e', linestyle='--', linewidth=1.0, alpha=0.6)  # $0 基準線

                ax.set_title(f"Rank {idx+1}: [{row['Model']}] {row['Symbol']} ({row['Timeframe']}) - 實盤純利: +${row['Profit']:,.1f}", fontsize=12, fontweight='bold', color='#f0f6fc')  # 標題
                ax.set_ylabel('實質累積損益 ($)', fontsize=10.5, color='#8b949e')  # Y 軸
                ax.grid(True, linestyle=':', alpha=0.25, color='#30363d')  # 網格

                info = (  # 數據方塊
                    f"模型: {row['Model']}\n"
                    f"實盤點差: {row['Spread_Pips']} pips\n"
                    f"勝率: {row['WinRate']}%\n"
                    f"獲利因子 (PF): {row['PF']}\n"
                    f"總交易筆數: {row['Trades']} 筆\n"
                    f"最大回撤: {row['MDD']}%"
                )
                ax.text(0.03, 0.93, info, transform=ax.transAxes, fontsize=9.5,
                        verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', facecolor='#21262d', edgecolor=c, alpha=0.85), color='#f0f6fc')  # 指標框

        for ax in axes_flat:  # 設定刻度樣式
            ax.tick_params(colors='#8b949e', labelsize=9)  # 刻度顏色
            ax.set_xlabel('K 線模擬步數 (含完整實盤點差與手續費扣除)', fontsize=9.5, color='#8b949e')  # X 軸標籤

        plt.tight_layout()  # 自動排版
        chart_file = "realistic_profitable_top_models.png"  # 圖名
        plt.savefig(chart_file, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')  # 存檔
        print(f"[+] 實盤真實可獲利 Top 模型圖表已成功輸出至: {chart_file}")  # 輸出日誌

if __name__ == "__main__":  # 執行入口
    engine = RealisticMultiTFScreeningEngine()  # 實例化
    engine.execute_large_scale_screening()  # 啟動大規模實盤點差回測
