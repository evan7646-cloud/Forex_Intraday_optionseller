import os  # 導入作業系統模組
import glob  # 導入檔案路徑搜尋模組
import datetime  # 導入日期時間處理模組
import numpy as np  # 導入數值運算庫
import pandas as pd  # 導入資料表格分析庫

# 定義 13 大品種的實盤點差 (Pips) 與每 Pip 美金價值換算
spreads = {  # 點差對照表
    "EURUSD": 0.2, "GBPUSD": 0.6, "USDJPY": 0.3, "USDCAD": 0.4, "USDCHF": 0.4,  # 主要貨幣對
    "AUDUSD": 0.4, "NZDUSD": 0.7, "AUDCAD": 1.1, "AUDCHF": 0.8, "EURCHF": 0.6,  # 交叉貨幣對
    "GBPJPY": 1.2, "EURJPY": 0.8, "XAUUSD": 1.5                                  # 貴金屬與日圓交叉
}  # 點差結束

quote_rates = {  # 計價貨幣美金匯率轉換
    "USD": 1.0, "CAD": 1.0/1.38, "CHF": 1.0/0.80, "JPY": 1.0/159.0,  # 匯率
    "GBP": 1.36, "NZD": 0.60, "AUD": 0.71                            # 匯率
}  # 匯率結束

def get_pip_specs(symbol: str):  # 取得商品的 Pip 最小單位與 1 手每 Pip 美金價值
    if symbol == "XAUUSD":  # 黃金
        return 0.1, 10.0  # 0.1 點為 $10 (100 oz)
    if "JPY" in symbol:  # 日圓貨幣對
        return 0.01, 100000.0 * 0.01 * quote_rates["JPY"]  # JPY 換算
    return 0.0001, 100000.0 * 0.0001 * quote_rates.get(symbol[-3:], 1.0)  # 一般貨幣對

data_dir = os.path.join(os.path.dirname(__file__), "data_pepperstone")  # 數據目錄

def run_strategy_backtest(df_raw: pd.DataFrame, symbol: str, tf_name: str, strat_type: str, params: dict):  # 執行單一策略回測
    df = df_raw.copy()  # 複製
    pip_size, pip_val = get_pip_specs(symbol)  # 取得規格
    sp_dist = spreads.get(symbol, 1.0) * pip_size  # 點差距離
    cost_per_trade = 5.0  # 每手手續費 $5.00
    
    # 計算 ATR 14
    tr = np.maximum(df["high"] - df["low"], np.maximum(abs(df["high"] - df["close"].shift(1)), abs(df["low"] - df["close"].shift(1))))  # True Range
    df["ATR"] = tr.rolling(14).mean()  # 14 ATR
    
    # 計算 RSI 14
    delta = df["close"].diff()  # 差分
    gain = delta.where(delta > 0, 0).rolling(14).mean()  # 漲幅
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()  # 跌幅
    df["RSI"] = 100 - (100 / (1 + (gain / (loss + 1e-9))))  # RSI
    
    # 計算均線與通道
    df["MA20"] = df["close"].rolling(20).mean()  # 20 SMA
    df["STD20"] = df["close"].rolling(20).std()  # 20 STD
    df["UB"] = df["MA20"] + params.get("bb_mult", 2.0) * df["STD20"]  # 上軌
    df["LB"] = df["MA20"] - params.get("bb_mult", 2.0) * df["STD20"]  # 下軌
    
    df["EMA50"] = df["close"].ewm(span=50).mean()  # 50 EMA
    df["EMA200"] = df["close"].ewm(span=200).mean()  # 200 EMA
    
    pos = 0  # 倉位 (1: 多, -1: 空)
    entry_p = 0.0  # 進場價
    sl_p = 0.0  # 停損價
    tp_p = 0.0  # 止盈價
    be_triggered = False  # 是否已觸發保本
    trades = []  # 交易記錄
    balance = 100000.0  # 初始本金
    
    start_idx = 200 if "EMA200" in strat_type else 35  # 預熱索引
    for i in range(start_idx, len(df)):  # 遍歷 K 棒
        c = float(df["close"].iloc[i])  # 收盤
        h = float(df["high"].iloc[i])  # 最高
        l = float(df["low"].iloc[i])  # 最低
        atr = float(df["ATR"].iloc[i])  # ATR
        if np.isnan(atr) or atr <= 0: continue  # 檢查 ATR
        
        # 1. 處理持倉與平倉
        if pos != 0:  # 持有部位
            closed = False  # 標記平倉
            exit_price = 0.0  # 出場價
            
            if pos == 1:  # 多單
                # 保本檢查：若最高價達到進場 + be_atr 倍數，且尚未啟動保本
                be_mult = params.get("be_atr", 0.0)  # 保本觸發倍數
                if be_mult > 0 and not be_triggered and h >= entry_p + be_mult * atr:  # 達到保本條件
                    sl_p = entry_p + sp_dist  # 停損移至成本+點差
                    be_triggered = True  # 標記已保本
                
                # 止盈或停損
                if h >= tp_p:  # 觸及止盈
                    exit_price = tp_p - sp_dist  # 出場
                    closed = True  # 平倉
                elif l <= sl_p:  # 觸及停損
                    exit_price = sl_p - sp_dist  # 出場
                    closed = True  # 平倉
                elif params.get("exit_middle", False) and c >= df["MA20"].iloc[i] and c > entry_p:  # 中軌離場
                    exit_price = c - sp_dist  # 出場
                    closed = True  # 平倉
                    
                if closed:  # 結算
                    pnl_dollars = (exit_price - entry_p)/pip_size * pip_val - cost_per_trade  # 美金淨利
                    balance += pnl_dollars  # 更新餘額
                    trades.append({"pnl": pnl_dollars, "win": pnl_dollars > 0})  # 記錄
                    pos = 0  # 重設
                    
            elif pos == -1:  # 空單
                # 保本檢查
                be_mult = params.get("be_atr", 0.0)  # 保本倍數
                if be_mult > 0 and not be_triggered and l <= entry_p - be_mult * atr:  # 達到保本
                    sl_p = entry_p - sp_dist  # 移至成本
                    be_triggered = True  # 標記
                
                # 止盈或停損
                if l <= tp_p:  # 觸及止盈
                    exit_price = tp_p + sp_dist  # 出場
                    closed = True  # 平倉
                elif h >= sl_p:  # 觸及停損
                    exit_price = sl_p + sp_dist  # 出場
                    closed = True  # 平倉
                elif params.get("exit_middle", False) and c <= df["MA20"].iloc[i] and c < entry_p:  # 中軌離場
                    exit_price = c + sp_dist  # 出場
                    closed = True  # 平倉
                    
                if closed:  # 結算
                    pnl_dollars = (entry_p - exit_price)/pip_size * pip_val - cost_per_trade  # 美金淨利
                    balance += pnl_dollars  # 更新餘額
                    trades.append({"pnl": pnl_dollars, "win": pnl_dollars > 0})  # 記錄
                    pos = 0  # 重設
                    
        # 2. 開倉檢查
        if pos == 0:  # 空倉狀態
            if strat_type == "M15_Breakeven_Scalper":  # 策略 1: 15m 動態保本極限收租
                rsi_val = float(df["RSI"].iloc[i])  # RSI
                if c <= df["LB"].iloc[i] and rsi_val <= params.get("rsi_buy", 35):  # 觸及下軌且超賣
                    pos = 1  # 開多
                    entry_p = c + sp_dist  # 買進價
                    sl_p = entry_p - params.get("sl_atr", 1.8) * atr  # 停損
                    tp_p = entry_p + params.get("tp_atr", 1.5) * atr  # 止盈
                    be_triggered = False  # 重設保本
                elif c >= df["UB"].iloc[i] and rsi_val >= params.get("rsi_sell", 65):  # 觸及上軌且超買
                    pos = -1  # 開空
                    entry_p = c  # 賣出價
                    sl_p = entry_p + params.get("sl_atr", 1.8) * atr  # 停損
                    tp_p = entry_p - params.get("tp_atr", 1.5) * atr  # 止盈
                    be_triggered = False  # 重設保本
                    
            elif strat_type == "H1_Trend_Pullback_Swing":  # 策略 2: H1 順大勢回調波段收租
                ema50 = float(df["EMA50"].iloc[i])  # 50 EMA
                ema200 = float(df["EMA200"].iloc[i])  # 200 EMA
                rsi_val = float(df["RSI"].iloc[i])  # RSI
                
                # 多頭順勢: EMA50 > EMA200 且 RSI 回調到 45 以下且價格回踩 20SMA
                if ema50 > ema200 and rsi_val <= params.get("rsi_buy", 45) and c <= df["MA20"].iloc[i]:
                    pos = 1  # 開多
                    entry_p = c + sp_dist  # 買價
                    sl_p = entry_p - params.get("sl_atr", 1.5) * atr  # 停損
                    tp_p = entry_p + params.get("tp_atr", 2.2) * atr  # 止盈 (高盈虧比 1:1.5)
                    be_triggered = False  # 保本
                # 空頭順勢: EMA50 < EMA200 且 RSI 反彈到 55 以上且價格反彈到 20SMA
                elif ema50 < ema200 and rsi_val >= params.get("rsi_sell", 55) and c >= df["MA20"].iloc[i]:
                    pos = -1  # 開空
                    entry_p = c  # 賣價
                    sl_p = entry_p + params.get("sl_atr", 1.5) * atr  # 停損
                    tp_p = entry_p - params.get("tp_atr", 2.2) * atr  # 止盈
                    be_triggered = False  # 保本

    # 計算統計指標
    tot_trades = len(trades)  # 筆數
    if tot_trades < 10: return None  # 排除樣本過少
    wins = sum(1 for t in trades if t["win"])  # 獲利數
    win_rate = round(wins / tot_trades * 100, 1)  # 勝率
    total_pnl = round(sum(t["pnl"] for t in trades), 2)  # 總淨利
    win_dollars = sum(t["pnl"] for t in trades if t["pnl"] > 0)  # 總獲利
    loss_dollars = sum(abs(t["pnl"]) for t in trades if t["pnl"] < 0)  # 總虧損
    pf = round(win_dollars / (loss_dollars + 1e-9), 2) if loss_dollars > 0 else (99.0 if wins > 0 else 0.0)  # PF
    
    return {  # 回傳結果
        "symbol": symbol, "timeframe": tf_name, "strategy": strat_type,
        "trades": tot_trades, "wins": wins, "losses": tot_trades - wins,
        "win_rate": win_rate, "profit_factor": pf, "total_pnl_usd": total_pnl
    }

def main():  # 主程式
    print("==========================================================================")  # 分隔線
    print(" 🔬 PEPPERSTONE 全品種 × 跨週期 (15m, 1H) 最佳抗摩擦穩健策略矩陣搜尋")  # 標題
    print("==========================================================================")  # 分隔線

    all_csvs = glob.glob(os.path.join(data_dir, "pepperstone_*_*.csv"))  # 搜尋所有 CSV
    print(f"[+] 找到 {len(all_csvs)} 個 PEPPERSTONE 本地歷史數據檔案，開始全量回測...")  # 提示

    results = []  # 儲存結果

    # 1. 測試 M15 動態保本收租策略
    m15_csvs = [f for f in all_csvs if "_15m.csv" in f]  # 抽取 15m 檔案
    for csv_file in m15_csvs:  # 遍歷 15m
        sym = os.path.basename(csv_file).split("_")[1].upper()  # 取得品種代碼
        df = pd.read_csv(csv_file)  # 讀取
        for tp_atr in [1.2, 1.5, 1.8]:  # 測試 TP
            for sl_atr in [1.5, 2.0]:  # 測試 SL
                for be_atr in [0.8, 1.0]:  # 測試保本觸發
                    r = run_strategy_backtest(df, sym, "15m", "M15_Breakeven_Scalper", {
                        "tp_atr": tp_atr, "sl_atr": sl_atr, "be_atr": be_atr, "bb_mult": 2.2, "rsi_buy": 35, "rsi_sell": 65
                    })  # 回測
                    if r and r["total_pnl_usd"] > 0:  # 保留獲利者
                        r["params"] = f"TP={tp_atr}ATR, SL={sl_atr}ATR, BE={be_atr}ATR"  # 參數
                        results.append(r)  # 加入

    # 2. 測試 H1 順大勢回調波段收租策略
    h1_csvs = [f for f in all_csvs if "_1h.csv" in f]  # 抽取 1H 檔案
    for csv_file in h1_csvs:  # 遍歷 1H
        sym = os.path.basename(csv_file).split("_")[1].upper()  # 取得品種代碼
        df = pd.read_csv(csv_file)  # 讀取
        for tp_atr in [1.8, 2.2, 2.5]:  # 測試 TP
            for sl_atr in [1.2, 1.5]:  # 測試 SL
                for be_atr in [1.0, 1.2]:  # 測試保本
                    r = run_strategy_backtest(df, sym, "1H", "H1_Trend_Pullback_Swing", {
                        "tp_atr": tp_atr, "sl_atr": sl_atr, "be_atr": be_atr, "rsi_buy": 45, "rsi_sell": 55
                    })  # 回測
                    if r and r["total_pnl_usd"] > 0:  # 保留獲利者
                        r["params"] = f"TP={tp_atr}ATR, SL={sl_atr}ATR, BE={be_atr}ATR"  # 參數
                        results.append(r)  # 加入

    df_res = pd.DataFrame(results)  # 轉為 DataFrame
    if df_res.empty:  # 若為空
        print("未找到符合條件之獲利模型")  # 提示
        return  # 結束

    df_res = df_res.sort_values(by="total_pnl_usd", ascending=False)  # 依淨利降序
    print("\n==========================================================================")  # 分隔線
    print(" 🏆 PEPPERSTONE 數據源【前 20 大最佳抗摩擦高勝率獲利策略排行】")  # 排行標題
    print("==========================================================================")  # 分隔線
    print(df_res.head(20).to_string(index=False))  # 輸出前 20 名

    # 輸出 CSV
    out_csv = os.path.join(os.path.dirname(__file__), "top_robust_multi_tf_strategies.csv")  # 輸出路徑
    df_res.to_csv(out_csv, index=False, encoding="utf-8-sig")  # 儲存
    print(f"\n[+] 完整優化排行已儲存至: {out_csv}")  # 提示

if __name__ == "__main__":  # 主入口
    main()  # 執行
