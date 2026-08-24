import numpy as np  # 導入數值計算庫 NumPy
import pandas as pd  # 導入數據分析庫 Pandas
import matplotlib.pyplot as plt  # 導入專業繪圖庫 Matplotlib
from tvDatafeed import TvDatafeed, Interval  # 導入 TradingView 行情數據接口
import yfinance as yf  # 導入備用金融數據接口
import signal  # 導入信號模組 (用於 timeout 防卡死)

def _timeout_handler(signum, frame):  # timeout 信號處理器
    raise TimeoutError("TvDatafeed 請求超時 (30 秒)")  # 拋出超時異常

class PureIntraday5mScreeningEngine:  # 定義純日內 5 分鐘週期 (5m) 8 大商品專用回測與繪圖引擎
    def __init__(self):  # 初始化
        self.tv = None  # 延遲初始化 TradingView 客戶端 (避免建構時卡住)

    def _get_tv(self):  # 安全取得 TvDatafeed 實例
        if self.tv is None:  # 尚未建立
            try:  # 嘗試建立
                signal.signal(signal.SIGALRM, _timeout_handler)  # 設定 timeout 處理器
                signal.alarm(15)  # 15 秒內必須完成連線
                self.tv = TvDatafeed()  # 建立 TradingView 連線客戶端
                signal.alarm(0)  # 取消計時器
            except Exception as e:  # 連線失敗
                signal.alarm(0)  # 取消計時器
                print(f"[!] TvDatafeed 連線失敗: {e}")  # 輸出錯誤
                self.tv = None  # 保持 None
        return self.tv  # 回傳

    def get_pip_size(self, symbol: str) -> float:  # 取得 1 pip 的價格單位
        return 0.01 if "JPY" in symbol else 0.0001  # JPY 貨幣對 1 pip = 0.01, 其餘 = 0.0001

    def get_pip_value_usd(self, symbol: str, lot_size: float = 1.0) -> float:  # 計算每 pip 在 USD 的真實價值
        quote_usd_rates = {  # 報價貨幣轉 USD 的即時精確匯率對照表
            "EURUSD": 1.0,       # 報價貨幣為 USD: $10.00 / pip
            "NZDCAD": 1.0/1.37,  # 報價貨幣為 CAD: $7.30 / pip
            "AUDNZD": 0.60,      # 報價貨幣為 NZD: $6.00 / pip
            "AUDCAD": 1.0/1.37,  # 報價貨幣為 CAD: $7.30 / pip
            "EURGBP": 1.30,      # 報價貨幣為 GBP: $13.00 / pip
            "EURCHF": 1.0/0.88,  # 報價貨幣為 CHF: $11.36 / pip
            "EURJPY": 1.0/148.0, # 報價貨幣為 JPY: $6.76 / pip
        }  # 匯率表結束
        base_pip = 100000.0 * self.get_pip_size(symbol)  # 1 標準手 1 pip 在計價幣的金額 (非JPY=10, JPY=1000)
        conversion = quote_usd_rates.get(symbol, 1.0)  # 取得轉換率
        return base_pip * conversion * lot_size  # 回傳每 pip 美金價值

    def fetch_5m_data(self, symbol: str, n_bars: int = 5000) -> pd.DataFrame:  # 抓取 5m 高解析數據
        print(f"[*] 正在抓取 [{symbol}] 5m 數據 (目標: {n_bars} 根)...")  # 輸出日誌
        df = None  # 初始化
        tv = self._get_tv()  # 安全取得連線
        if tv is not None:  # 連線可用
            try:  # 嘗試 TradingView
                signal.signal(signal.SIGALRM, _timeout_handler)  # 設定 timeout 處理器
                signal.alarm(30)  # 30 秒內必須完成數據請求
                df = tv.get_hist(symbol=symbol, exchange="OANDA", interval=Interval.in_5_minute, n_bars=n_bars)  # 請求 5m 數據
                signal.alarm(0)  # 取消計時器
            except Exception as e:  # 捕獲所有異常 (含 TimeoutError)
                signal.alarm(0)  # 取消計時器
                print(f"[!] TvDatafeed [{symbol}] 請求失敗: {e}, 切換 yfinance")  # 輸出錯誤
        
        if df is not None and len(df) > 100:  # 驗證數據有效性
            df = df.reset_index()  # 重設索引
            df['datetime'] = pd.to_datetime(df['datetime']).dt.tz_localize(None) - pd.Timedelta(hours=8)  # [修復] 校準為 UTC 時間
            df.set_index('datetime', inplace=True)  # 設為索引
            return df[['open', 'high', 'low', 'close', 'volume']][~df.index.duplicated(keep='first')]  # 回傳去重數據
        
        # yfinance 備用下載
        ticker = f"{symbol}=X"  # 取得 yf 代碼
        df_yf = yf.download(ticker, period="60d", interval="5m", progress=False)  # 下載 5m 數據
        if isinstance(df_yf.columns, pd.MultiIndex): df_yf.columns = df_yf.columns.get_level_values(0)  # 展平欄位
        df_yf = df_yf.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})  # 統一欄位
        df_yf.index = pd.to_datetime(df_yf.index).tz_localize(None) if pd.to_datetime(df_yf.index).tz is not None else pd.to_datetime(df_yf.index)  # 格式化時間
        return df_yf[['open', 'high', 'low', 'close', 'volume']].dropna()  # 回傳有效表

    def run_5m_scalper(self, symbol: str, df_raw: pd.DataFrame, lot_size: float = 1.0, force_close_hour: int = 7) -> dict:  # 策略 1: 5m Asian Night Scalper (真實物理結算)
        df = df_raw.copy()  # 複製表
        df['MA'] = df['close'].rolling(20).mean()  # 20 均線
        df['STD'] = df['close'].rolling(20).std()  # 20 標準差
        df['UB'] = df['MA'] + 2.2 * df['STD']  # 上軌
        df['LB'] = df['MA'] - 2.2 * df['STD']  # 下軌
        
        delta = df['close'].diff()  # 差分
        gain = delta.where(delta > 0, 0).rolling(14).mean()  # 漲幅
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()  # 跌幅
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))  # RSI
        
        is_night = (df.index.hour >= 21) | (df.index.hour <= 6)  # 夜間開倉時段 (UTC 21:00 - 06:00)
        pos = 0  # 倉位
        entry_p = 0.0  # 開倉價
        cum_pnl = 0.0  # 累積淨損益 (從 $0 起計)
        wins, losses = 0, 0  # 勝負
        win_dollars, loss_dollars = 0.0, 0.0  # 盈虧美金
        cost_per_trade = 5.0 * lot_size  # 扣除手續費 ($5/手)
        pip_size = self.get_pip_size(symbol)  # 取得 1 pip 大小
        pip_val_usd = self.get_pip_value_usd(symbol, lot_size)  # 取得 1 pip 美金價值
        tp_distance = 5.0 * pip_size  # 5 pips 止盈距離
        sl_distance = 35.0 * pip_size  # 35 pips 停損距離
        equity_curve = [0.0]  # 淨損益曲線 (從 $0 起算)

        for i in range(len(df)):  # 遍歷 K 棒
            if i < 30: continue  # 預熱
            c = float(df['close'].iloc[i])  # 收盤價
            h = float(df['high'].iloc[i])  # 最高價
            l = float(df['low'].iloc[i])  # 最低價
            hr = df.index[i].hour  # 小時 (UTC)
            is_force_exit = (hr == force_close_hour)  # UTC 07:00 歐盤前夕強制清倉

            if pos != 0:  # 有持倉
                exit_price = 0.0  # 出場價
                is_closed = False  # 平倉標記

                if pos == 1:  # 多單
                    if h >= entry_p + tp_distance:  # 觸及 5 pips 止盈目標
                        exit_price = entry_p + tp_distance; is_closed = True  # 止盈
                    elif c >= df['MA'].iloc[i]:  # 回歸布林中軌平倉
                        exit_price = c; is_closed = True  # 中軌平倉
                    elif l <= entry_p - sl_distance:  # 觸及 35 pips 硬停損
                        exit_price = entry_p - sl_distance; is_closed = True  # 停損
                    elif is_force_exit:  # 時間強制清倉
                        exit_price = c; is_closed = True  # 強平

                    if is_closed:  # 執行真實結算
                        pnl_pips = (exit_price - entry_p) / pip_size  # 真實獲利 pips
                        pnl = pnl_pips * pip_val_usd - cost_per_trade  # 真實美金損益 (扣手續費)
                        cum_pnl += pnl  # 更新累計淨利
                        if pnl > 0: wins += 1; win_dollars += pnl  # 贏
                        else: losses += 1; loss_dollars += abs(pnl)  # 輸
                        pos = 0  # 清倉

                elif pos == -1:  # 空單
                    if l <= entry_p - tp_distance:  # 觸及 5 pips 止盈目標
                        exit_price = entry_p - tp_distance; is_closed = True  # 止盈
                    elif c <= df['MA'].iloc[i]:  # 回歸布林中軌平倉
                        exit_price = c; is_closed = True  # 中軌平倉
                    elif h >= entry_p + sl_distance:  # 觸及 35 pips 硬停損
                        exit_price = entry_p + sl_distance; is_closed = True  # 停損
                    elif is_force_exit:  # 時間強制清倉
                        exit_price = c; is_closed = True  # 強平

                    if is_closed:  # 執行真實結算
                        pnl_pips = (entry_p - exit_price) / pip_size  # 真實獲利 pips
                        pnl = pnl_pips * pip_val_usd - cost_per_trade  # 真實美金損益 (扣手續費)
                        cum_pnl += pnl  # 更新累計淨利
                        if pnl > 0: wins += 1; win_dollars += pnl  # 贏
                        else: losses += 1; loss_dollars += abs(pnl)  # 輸
                        pos = 0  # 清倉

            if pos == 0 and is_night[i] and not is_force_exit:  # 空倉進場
                if c <= df['LB'].iloc[i] and df['RSI'].iloc[i] <= 35: pos, entry_p = 1, c  # 買多
                elif c >= df['UB'].iloc[i] and df['RSI'].iloc[i] >= 65: pos, entry_p = -1, c  # 賣空

            equity_curve.append(cum_pnl)  # 記錄當前累計淨利

        tot = wins + losses  # 總筆數
        win_rate = (wins / tot * 100) if tot > 0 else 0.0  # 勝率
        pf = (win_dollars / (loss_dollars + 1e-9)) if loss_dollars > 0 else (99.0 if wins > 0 else 0.0)  # PF
        eq_ser = pd.Series(equity_curve)  # 轉 Series
        bal_ser = eq_ser + 100000.0  # 換算為 $100k 本金基準計算 MDD
        mdd = ((bal_ser - bal_ser.cummax()) / bal_ser.cummax() * 100).min()  # 最大回撤
        return {"Trades": tot, "WinRate": win_rate, "Profit": cum_pnl, "MDD": mdd, "PF": pf, "Equity": eq_ser}  # 回傳

    def run_5m_straddle(self, symbol: str, df_raw: pd.DataFrame, lot_size: float = 1.0, force_close_hour: int = 21) -> dict:  # 策略 2: 5m Synthetic Short Straddle (真實物理結算)
        df = df_raw.copy()  # 複製表
        df['MA'] = df['close'].rolling(30).mean()  # 均值
        df['STD'] = df['close'].rolling(30).std()  # 標準差
        df['Z'] = (df['close'] - df['MA']) / (df['STD'] + 1e-9)  # Z 值

        pos = 0  # 倉位
        entry_p = 0.0  # 進場價
        cum_pnl = 0.0  # 累積淨損益 (從 $0 起計)
        wins, losses = 0, 0  # 勝負
        win_dollars, loss_dollars = 0.0, 0.0  # 盈虧美金
        cost_per_trade = 5.0 * lot_size  # 扣除手續費
        pip_size = self.get_pip_size(symbol)  # 1 pip 大小
        pip_val_usd = self.get_pip_value_usd(symbol, lot_size)  # 1 pip 美金價值
        tp_distance = 5.0 * pip_size  # 5 pips 止盈距離
        sl_distance = 35.0 * pip_size  # 35 pips 停損距離
        equity_curve = [0.0]  # 淨損益曲線 (從 $0 起算)

        for i in range(len(df)):  # 遍歷 K 棒
            if i < 35: continue  # 預熱
            c = float(df['close'].iloc[i])  # 收盤價
            h = float(df['high'].iloc[i])  # 最高價
            l = float(df['low'].iloc[i])  # 最低價
            z = float(df['Z'].iloc[i])  # Z 值
            hr = df.index[i].hour  # 小時 (UTC)
            is_force_exit = (hr == force_close_hour)  # UTC 21:00 強制清倉

            if pos != 0:  # 有持倉
                exit_price = 0.0  # 出場價
                is_closed = False  # 平倉標記

                if pos == 1:  # 多單
                    if z >= -0.2:  # Z 均值回歸平倉
                        exit_price = c; is_closed = True  # 現價平倉
                    elif h >= entry_p + tp_distance:  # 觸及 5 pips 止盈
                        exit_price = entry_p + tp_distance; is_closed = True  # 止盈
                    elif z <= -3.8:  # Z 極端偏離停損
                        exit_price = c; is_closed = True  # 現價停損
                    elif l <= entry_p - sl_distance:  # 觸及 35 pips 硬停損
                        exit_price = entry_p - sl_distance; is_closed = True  # 停損
                    elif is_force_exit:  # 時間強制清倉
                        exit_price = c; is_closed = True  # 強平

                    if is_closed:  # 執行真實結算
                        pnl_pips = (exit_price - entry_p) / pip_size  # 真實獲利 pips
                        pnl = pnl_pips * pip_val_usd - cost_per_trade  # 真實美金損益 (扣手續費)
                        cum_pnl += pnl  # 更新累計淨利
                        if pnl > 0: wins += 1; win_dollars += pnl  # 贏
                        else: losses += 1; loss_dollars += abs(pnl)  # 輸
                        pos = 0  # 清倉

                elif pos == -1:  # 空單
                    if z <= 0.2:  # Z 均值回歸平倉
                        exit_price = c; is_closed = True  # 現價平倉
                    elif l <= entry_p - tp_distance:  # 觸及 5 pips 止盈
                        exit_price = entry_p - tp_distance; is_closed = True  # 止盈
                    elif z >= 3.8:  # Z 極端偏離停損
                        exit_price = c; is_closed = True  # 現價停損
                    elif h >= entry_p + sl_distance:  # 觸及 35 pips 硬停損
                        exit_price = entry_p + sl_distance; is_closed = True  # 停損
                    elif is_force_exit:  # 時間強制清倉
                        exit_price = c; is_closed = True  # 強平

                    if is_closed:  # 執行真實結算
                        pnl_pips = (entry_p - exit_price) / pip_size  # 真實獲利 pips
                        pnl = pnl_pips * pip_val_usd - cost_per_trade  # 真實美金損益 (扣手續費)
                        cum_pnl += pnl  # 更新累計淨利
                        if pnl > 0: wins += 1; win_dollars += pnl  # 贏
                        else: losses += 1; loss_dollars += abs(pnl)  # 輸
                        pos = 0  # 清倉

            # 2. 開倉 (僅在日間活躍時段 UTC 07:00 - 20:00 允許進場)
            if pos == 0 and (7 <= hr <= 20) and not is_force_exit:  # 日間開倉
                if z <= -2.1: pos, entry_p = 1, c  # 賣 Put 等效
                elif z >= 2.1: pos, entry_p = -1, c  # 賣 Call 等效
            equity_curve.append(cum_pnl)  # 記錄當前累計淨利

        tot = wins + losses  # 總單數
        win_rate = (wins / tot * 100) if tot > 0 else 0.0  # 勝率
        pf = (win_dollars / (loss_dollars + 1e-9)) if loss_dollars > 0 else (99.0 if wins > 0 else 0.0)  # PF
        eq_ser = pd.Series(equity_curve)  # 轉 Series
        bal_ser = eq_ser + 100000.0  # 換算為 $100k 本金基準計算 MDD
        mdd = ((bal_ser - bal_ser.cummax()) / bal_ser.cummax() * 100).min()  # 最大回撤
        return {"Trades": tot, "WinRate": win_rate, "Profit": cum_pnl, "MDD": mdd, "PF": pf, "Equity": eq_ser}  # 回傳

def run_5m_8pair_full_comparison(lot_size: float = 1.0):  # 執行 5m 全 8 商品真實結算回測與視覺化生成
    print("\n===============================================================================")  # 標頭
    print(f"   純日內 5 分鐘 (5m) 兩大策略 × 8 大首選標的 (各 {lot_size} Lot / 真實點值結算 / $0 起計)   ")  # 標題
    print("===============================================================================")  # 標頭

    engine = PureIntraday5mScreeningEngine()  # 實例化
    
    # 策略 1: 4 款夜間剝頭皮標的 (5m)
    scalper_pairs = ["NZDCAD", "AUDNZD", "AUDCAD", "EURGBP"]  # 清單 1
    # 策略 2: 4 款日間跨式賣方標的 (5m)
    straddle_pairs = ["EURJPY", "EURGBP", "EURUSD", "EURCHF"] # 清單 2

    summary_records = []  # 統計總表
    curves_scalper = {}   # 曲線 1
    curves_straddle = {}  # 曲線 2

    print("\n--- [1. 正在回測 Strategy 1: Asian Night Scalper (5m) ] ---")  # 日誌
    for sym in scalper_pairs:  # 遍歷
        df = engine.fetch_5m_data(sym, n_bars=5000)  # 抓數據
        if df.empty or len(df) < 200: continue  # 檢查
        res = engine.run_5m_scalper(sym, df, lot_size=lot_size, force_close_hour=7)  # 執行真實結算回測
        curves_scalper[sym] = res['Equity']  # 記錄
        summary_records.append({  # 記錄指標
            "策略名稱": "Asian Scalper (5m)", "交易品種": sym, "下單手數": f"{lot_size} Lot",  # 基本
            "勝率 (%)": round(res['WinRate'], 1), "總交易筆數": res['Trades'],            # 統計
            "扣手續費純利 ($)": round(res['Profit'], 1), "獲利因子 (PF)": round(res['PF'], 2), # 收益
            "最大回撤 MDD (%)": round(res['MDD'], 2)                                      # 回撤
        })  # 結束

    print("\n--- [2. 正在回測 Strategy 2: Synthetic Short Straddle (5m) ] ---")  # 日誌
    for sym in straddle_pairs:  # 遍歷
        df = engine.fetch_5m_data(sym, n_bars=5000)  # 抓數據
        if df.empty or len(df) < 200: continue  # 檢查
        res = engine.run_5m_straddle(sym, df, lot_size=lot_size, force_close_hour=21)  # 執行真實結算回測
        curves_straddle[sym] = res['Equity']  # 記錄
        summary_records.append({  # 記錄指標
            "策略名稱": "Short Straddle (5m)", "交易品種": sym, "下單手數": f"{lot_size} Lot", # 基本
            "勝率 (%)": round(res['WinRate'], 1), "總交易筆數": res['Trades'],            # 統計
            "扣手續費純利 ($)": round(res['Profit'], 1), "獲利因子 (PF)": round(res['PF'], 2), # 收益
            "最大回撤 MDD (%)": round(res['MDD'], 2)                                      # 回撤
        })  # 結束

    df_sum = pd.DataFrame(summary_records)  # 轉 DataFrame
    print("\n[ 純日內 5 分鐘 (5m) 8 大商品真實物理結算指標總表 ]")  # 標題
    print(df_sum.to_string(index=False))  # 格式化輸出

    # 繪製 5m 專用雙面板對比圖 (從 $0 起計，含 $0 基準參考線)
    plt.style.use('dark_background')  # 使用質感深色背景
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 11), sharex=False)  # 雙子圖
    fig.patch.set_facecolor('#0d1117')  # 圖表外框背景
    ax1.set_facecolor('#161b22')  # 子圖 1 背景
    ax2.set_facecolor('#161b22')  # 子圖 2 背景
    
    # 子圖 1: 5m Asian Night Scalper (4 款標的)
    colors1 = {"NZDCAD": "#a371f7", "AUDNZD": "#3fb950", "AUDCAD": "#58a6ff", "EURGBP": "#f0883e"}  # 配色
    for sym, eq in curves_scalper.items():  # 遍歷
        c = colors1.get(sym, "#16a085")  # 顏色
        final_val = eq.iloc[-1] if len(eq) > 0 else 0.0  # 終值
        ax1.plot(eq.values, label=f"{sym} (PnL: {'+' if final_val>=0 else ''}${final_val:.1f})", color=c, linewidth=2.2)  # 畫線
    ax1.axhline(0, color='#8b949e', linestyle='--', linewidth=1.2, alpha=0.6, label='$0 Baseline')  # 0 基準線
    ax1.set_title(f'Strategy 1: Asian Night Scalper (5m) - Real PnL from $0 (Flat at UTC 07:00, {lot_size} Lot)', fontsize=13, fontweight='bold', color='#f0f6fc')  # 標題
    ax1.set_ylabel('Cumulative Net Profit ($)', fontsize=11, color='#8b949e')  # Y 軸
    ax1.grid(True, linestyle=':', alpha=0.3, color='#30363d')  # 網格
    ax1.legend(loc='upper left', fontsize=10, facecolor='#21262d', edgecolor='#30363d')  # 圖例

    # 子圖 2: 5m Synthetic Short Straddle (4 款標的)
    colors2 = {"EURJPY": "#f85149", "EURGBP": "#f0883e", "EURUSD": "#d2a8ff", "EURCHF": "#2ea043"}  # 配色
    for sym, eq in curves_straddle.items():  # 遍歷
        c = colors2.get(sym, "#f39c12")  # 顏色
        final_val = eq.iloc[-1] if len(eq) > 0 else 0.0  # 終值
        ax2.plot(eq.values, label=f"{sym} (PnL: {'+' if final_val>=0 else ''}${final_val:.1f})", color=c, linewidth=2.2)  # 畫線
    ax2.axhline(0, color='#8b949e', linestyle='--', linewidth=1.2, alpha=0.6, label='$0 Baseline')  # 0 基準線
    ax2.set_title(f'Strategy 2: Synthetic Short Straddle (5m) - Real PnL from $0 (Flat at UTC 21:00, {lot_size} Lot)', fontsize=13, fontweight='bold', color='#f0f6fc')  # 標題
    ax2.set_ylabel('Cumulative Net Profit ($)', fontsize=11, color='#8b949e')  # Y 軸
    ax2.set_xlabel('Simulated 5-Minute Bar Steps', fontsize=11, color='#8b949e')  # X 軸
    ax2.grid(True, linestyle=':', alpha=0.3, color='#30363d')  # 網格
    ax2.legend(loc='upper left', fontsize=10, facecolor='#21262d', edgecolor='#30363d')  # 圖例

    plt.tight_layout()  # 自動排版
    out_chart = "pure_intraday_5m_8pair_comparison.png"  # 圖名
    plt.savefig(out_chart, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')  # 存檔
    print(f"\n[+] 真實物理結算 5m 對比圖已重新繪製並輸出至: {out_chart}")  # 輸出日誌
    print("===============================================================================\n")  # 結尾

if __name__ == "__main__":  # 執行入口
    run_5m_8pair_full_comparison(lot_size=1.0)  # 啟動 1.0 Lot 真實結算回測
