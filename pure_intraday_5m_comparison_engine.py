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

    def run_5m_scalper(self, df_raw: pd.DataFrame, lot_size: float = 2.0, force_close_hour: int = 7) -> dict:  # 策略 1: 5m Asian Night Scalper (UTC 07:00 強制清倉)
        df = df_raw.copy()  # 複製表
        df['MA'] = df['close'].rolling(20).mean()  # 20 均線
        df['STD'] = df['close'].rolling(20).std()  # 20 標準差
        df['UB'] = df['MA'] + 2.2 * df['STD']  # 上軌
        df['LB'] = df['MA'] - 2.2 * df['STD']  # 下軌
        
        delta = df['close'].diff()  # 差分
        gain = delta.where(delta > 0, 0).rolling(14).mean()  # 漲幅
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()  # 跌幅
        df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))  # RSI
        
        is_night = (df.index.hour >= 21) | (df.index.hour <= 6)  # 夜間開倉時段
        pos = 0  # 倉位
        entry_p = 0.0  # 開倉價
        balance = 100000.0  # 初始本金 ($100,000)
        wins, losses = 0, 0  # 勝負
        win_dollars, loss_dollars = 0.0, 0.0  # 盈虧美金
        cost_per_trade = 5.0 * lot_size  # 2.0 手扣除手續費 ($10/筆)
        tp_ratio = 0.0005  # 5m 目標 5 pips
        sl_ratio = 0.0035  # 5m 硬停損 35 pips
        equity_curve = [balance]  # 淨值列表

        for i in range(len(df)):  # 遍歷 K 棒
            if i < 30: continue  # 預熱
            c = df['close'].iloc[i]  # 收盤價
            h = df['high'].iloc[i]  # 最高價
            l = df['low'].iloc[i]  # 最低價
            hr = df.index[i].hour  # 小時
            is_force_exit = (hr == force_close_hour)  # UTC 07:00 歐盤前夕強制清倉

            if pos != 0:  # 有持倉
                if pos == 1:  # 多單
                    if h >= entry_p * (1.0 + tp_ratio) or c >= df['MA'].iloc[i]:  # 止盈收租
                        pnl = 100000.0 * lot_size * tp_ratio - cost_per_trade; balance += pnl; wins += 1; win_dollars += pnl; pos = 0  # 結算
                    elif l <= entry_p * (1.0 - sl_ratio):  # 硬停損
                        pnl = -100000.0 * lot_size * sl_ratio - cost_per_trade; balance += pnl; losses += 1; loss_dollars += abs(pnl); pos = 0  # 結算
                    elif is_force_exit:  # 時間到強制清倉 (零隔夜)
                        pnl = (c - entry_p) / entry_p * 100000.0 * lot_size - cost_per_trade  # 按現價結算
                        balance += pnl  # 更新
                        if pnl > 0: wins += 1; win_dollars += pnl  # 贏
                        else: losses += 1; loss_dollars += abs(pnl)  # 輸
                        pos = 0  # 清倉
                elif pos == -1:  # 空單
                    if l <= entry_p * (1.0 - tp_ratio) or c <= df['MA'].iloc[i]:  # 止盈收租
                        pnl = 100000.0 * lot_size * tp_ratio - cost_per_trade; balance += pnl; wins += 1; win_dollars += pnl; pos = 0  # 結算
                    elif h >= entry_p * (1.0 + sl_ratio):  # 硬停損
                        pnl = -100000.0 * lot_size * sl_ratio - cost_per_trade; balance += pnl; losses += 1; loss_dollars += abs(pnl); pos = 0  # 結算
                    elif is_force_exit:  # 時間到強制清倉 (零隔夜)
                        pnl = (entry_p - c) / entry_p * 100000.0 * lot_size - cost_per_trade  # 按現價結算
                        balance += pnl  # 更新
                        if pnl > 0: wins += 1; win_dollars += pnl  # 贏
                        else: losses += 1; loss_dollars += abs(pnl)  # 輸
                        pos = 0  # 清倉

            if pos == 0 and is_night[i] and not is_force_exit:  # 空倉進場
                if c <= df['LB'].iloc[i] and df['RSI'].iloc[i] <= 35: pos, entry_p = 1, c  # 買多
                elif c >= df['UB'].iloc[i] and df['RSI'].iloc[i] >= 65: pos, entry_p = -1, c  # 賣空

            equity_curve.append(balance)  # 記錄

        tot = wins + losses  # 總筆數
        win_rate = (wins / tot * 100) if tot > 0 else 0.0  # 勝率
        pf = (win_dollars / (loss_dollars + 1e-9)) if loss_dollars > 0 else (99.0 if wins > 0 else 0.0)  # PF
        eq_ser = pd.Series(equity_curve)  # 轉 Series
        mdd = ((eq_ser - eq_ser.cummax()) / eq_ser.cummax() * 100).min()  # 最大回撤
        return {"Trades": tot, "WinRate": win_rate, "Profit": balance - 100000.0, "MDD": mdd, "PF": pf, "Equity": eq_ser}  # 回傳

    def run_5m_straddle(self, df_raw: pd.DataFrame, lot_size: float = 2.0, force_close_hour: int = 21) -> dict:  # 策略 2: 5m Synthetic Short Straddle (UTC 21:00 強制清倉)
        df = df_raw.copy()  # 複製表
        df['MA'] = df['close'].rolling(30).mean()  # 均值
        df['STD'] = df['close'].rolling(30).std()  # 標準差
        df['Z'] = (df['close'] - df['MA']) / (df['STD'] + 1e-9)  # Z 值

        pos = 0  # 倉位
        entry_p = 0.0  # 進場價
        balance = 100000.0  # 初始本金
        wins, losses = 0, 0  # 勝負
        win_dollars, loss_dollars = 0.0, 0.0  # 盈虧美金
        cost_per_trade = 5.0 * lot_size  # 2.0 手扣除手續費
        tp_ratio = 0.0005  # 5m 目標 5 pips
        sl_ratio = 0.0035  # 5m 硬停損 35 pips
        equity_curve = [balance]  # 淨值列表

        for i in range(len(df)):  # 遍歷 K 棒
            if i < 35: continue  # 預熱
            c = df['close'].iloc[i]  # 收盤價
            h = df['high'].iloc[i]  # 最高價
            l = df['low'].iloc[i]  # 最低價
            z = df['Z'].iloc[i]  # Z 值
            hr = df.index[i].hour  # 小時
            is_force_exit = (hr == force_close_hour)  # UTC 21:00 強制清倉

            if pos != 0:  # 有持倉
                if pos == 1:  # 多單
                    if z >= -0.2 or h >= entry_p * (1.0 + tp_ratio):  # 均值回歸收租
                        pnl = 100000.0 * lot_size * tp_ratio - cost_per_trade; balance += pnl; wins += 1; win_dollars += pnl; pos = 0  # 結算
                    elif z <= -3.8 or l <= entry_p * (1.0 - sl_ratio):  # 硬停損
                        pnl = -100000.0 * lot_size * sl_ratio - cost_per_trade; balance += pnl; losses += 1; loss_dollars += abs(pnl); pos = 0  # 結算
                    elif is_force_exit:  # 時間到強制清倉 (零隔夜)
                        pnl = (c - entry_p) / entry_p * 100000.0 * lot_size - cost_per_trade  # 按現價結算
                        balance += pnl  # 更新
                        if pnl > 0: wins += 1; win_dollars += pnl  # 贏
                        else: losses += 1; loss_dollars += abs(pnl)  # 輸
                        pos = 0  # 清倉
                elif pos == -1:  # 空單
                    if z <= 0.2 or l <= entry_p * (1.0 - tp_ratio):  # 均值回歸收租
                        pnl = 100000.0 * lot_size * tp_ratio - cost_per_trade; balance += pnl; wins += 1; win_dollars += pnl; pos = 0  # 結算
                    elif z >= 3.8 or h >= entry_p * (1.0 + sl_ratio):  # 硬停損
                        pnl = -100000.0 * lot_size * sl_ratio - cost_per_trade; balance += pnl; losses += 1; loss_dollars += abs(pnl); pos = 0  # 結算
                    elif is_force_exit:  # 時間到強制清倉 (零隔夜)
                        pnl = (entry_p - c) / entry_p * 100000.0 * lot_size - cost_per_trade  # 按現價結算
                        balance += pnl  # 更新
                        if pnl > 0: wins += 1; win_dollars += pnl  # 贏
                        else: losses += 1; loss_dollars += abs(pnl)  # 輸
                        pos = 0  # 清倉

            # 2. 開倉 (僅在日間活躍時段 UTC 07:00 - 20:00 允許進場)
            if pos == 0 and (7 <= hr <= 20) and not is_force_exit:  # 日間開倉
                if z <= -2.1: pos, entry_p = 1, c  # 賣 Put 等效
                elif z >= 2.1: pos, entry_p = -1, c  # 賣 Call 等效
            equity_curve.append(balance)  # 記錄

        tot = wins + losses  # 總單數
        win_rate = (wins / tot * 100) if tot > 0 else 0.0  # 勝率
        pf = (win_dollars / (loss_dollars + 1e-9)) if loss_dollars > 0 else (99.0 if wins > 0 else 0.0)  # PF
        eq_ser = pd.Series(equity_curve)  # 轉 Series
        mdd = ((eq_ser - eq_ser.cummax()) / eq_ser.cummax() * 100).min()  # 最大回撤
        return {"Trades": tot, "WinRate": win_rate, "Profit": balance - 100000.0, "MDD": mdd, "PF": pf, "Equity": eq_ser}  # 回傳

def run_5m_8pair_full_comparison():  # 執行 5m 全 8 商品回測與視覺化生成
    print("\n===============================================================================")  # 標頭
    print("      純日內 5 分鐘週期 (5m) 兩大策略 × 8 大首選標的 (各 2.0 Lots) 全矩陣精算      ")  # 標題
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
        res = engine.run_5m_scalper(df, lot_size=2.0, force_close_hour=7)  # 執行 2.0 手回測
        curves_scalper[sym] = res['Equity']  # 記錄
        summary_records.append({  # 記錄指標
            "策略名稱": "Asian Scalper (5m)", "交易品種": sym, "下單手數": "2.0 Lots",  # 基本
            "勝率 (%)": round(res['WinRate'], 1), "總交易筆數": res['Trades'],            # 統計
            "扣手續費純利 ($)": round(res['Profit'], 1), "獲利因子 (PF)": round(res['PF'], 2), # 收益
            "最大回撤 MDD (%)": round(res['MDD'], 2)                                      # 回撤
        })  # 結束

    print("\n--- [2. 正在回測 Strategy 2: Synthetic Short Straddle (5m) ] ---")  # 日誌
    for sym in straddle_pairs:  # 遍歷
        df = engine.fetch_5m_data(sym, n_bars=5000)  # 抓數據
        if df.empty or len(df) < 200: continue  # 檢查
        res = engine.run_5m_straddle(df, lot_size=2.0, force_close_hour=21)  # 執行 2.0 手回測
        curves_straddle[sym] = res['Equity']  # 記錄
        summary_records.append({  # 記錄指標
            "策略名稱": "Short Straddle (5m)", "交易品種": sym, "下單手數": "2.0 Lots", # 基本
            "勝率 (%)": round(res['WinRate'], 1), "總交易筆數": res['Trades'],            # 統計
            "扣手續費純利 ($)": round(res['Profit'], 1), "獲利因子 (PF)": round(res['PF'], 2), # 收益
            "最大回撤 MDD (%)": round(res['MDD'], 2)                                      # 回撤
        })  # 結束

    df_sum = pd.DataFrame(summary_records)  # 轉 DataFrame
    print("\n[ 純日內 5 分鐘 (5m) 8 大商品 (各 2.0 Lots) 實盤回測指標總表 ]")  # 標題
    print(df_sum.to_string(index=False))  # 格式化輸出

    # 繪製 5m 專用雙面板對比圖 (規格完全等同於 pure_intraday_timeframe_comparison / pure_intraday_multi_asset_comparison)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 11), sharex=False)  # 雙子圖
    
    # 子圖 1: 5m Asian Night Scalper (4 款標的)
    colors1 = {"NZDCAD": "#8e44ad", "AUDNZD": "#27ae60", "AUDCAD": "#2980b9", "EURGBP": "#d35400"}  # 配色
    for sym, eq in curves_scalper.items():  # 遍歷
        c = colors1.get(sym, "#16a085")  # 顏色
        ax1.plot(eq.values, label=f"{sym} (5m Scalper)", color=c, linewidth=2.4)  # 畫線
    ax1.set_title('Strategy 1: Pure Intraday Asian Night Scalper on 5-Minute (5m) Timeframe (Flat at UTC 07:00, 2.0 Lots)', fontsize=13, fontweight='bold')  # 標題
    ax1.set_ylabel('Account Balance ($)', fontsize=11)  # Y 軸
    ax1.grid(True, linestyle=':', alpha=0.6)  # 網格
    ax1.legend(loc='upper left', fontsize=10)  # 圖例

    # 子圖 2: 5m Synthetic Short Straddle (4 款標的)
    colors2 = {"EURJPY": "#c0392b", "EURGBP": "#d35400", "EURUSD": "#e84393", "EURCHF": "#16a085"}  # 配色
    for sym, eq in curves_straddle.items():  # 遍歷
        c = colors2.get(sym, "#f39c12")  # 顏色
        ax2.plot(eq.values, label=f"{sym} (5m Straddle)", color=c, linewidth=2.4)  # 畫線
    ax2.set_title('Strategy 2: Pure Intraday Synthetic Short Straddle on 5-Minute (5m) Timeframe (Flat at UTC 21:00, 2.0 Lots)', fontsize=13, fontweight='bold')  # 標題
    ax2.set_ylabel('Account Balance ($)', fontsize=11)  # Y 軸
    ax2.set_xlabel('Simulated 5-Minute Bar Steps', fontsize=11)  # X 軸
    ax2.grid(True, linestyle=':', alpha=0.6)  # 網格
    ax2.legend(loc='upper left', fontsize=10)  # 圖例

    plt.tight_layout()  # 自動排版
    out_chart = "pure_intraday_5m_8pair_comparison.png"  # 圖名
    plt.savefig(out_chart, dpi=300)  # 存檔
    print(f"\n[+] 5 分鐘 (5m) 8 大商品對比圖已輸出至: {out_chart}")  # 輸出日誌
    print("===============================================================================\n")  # 結尾

if __name__ == "__main__":  # 執行入口
    run_5m_8pair_full_comparison()  # 啟動
