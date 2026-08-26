"""
大規模回測篩選：用方案 C 最新邏輯 (中軌+盈利條件, 空單扣點差)
掃描全部品種 × 15m/1h × DaytimeChannel/US_Afternoon × σ/ATR 組合
找出兩個策略各自最佳的品種與參數
"""
import os  # 作業系統模組
import glob  # 路徑匹配
import numpy as np  # 數值運算
import pandas as pd  # 表格分析
import warnings  # 警告控制
from itertools import product  # 笛卡爾積

warnings.filterwarnings("ignore")  # 忽略警告

# ═══════ 實盤成本參數 ═══════
SPREADS = {  # MT5 Market Watch 實盤點差 (Pips)
    "EURUSD": 0.3, "USDCAD": 0.6, "USDCHF": 0.6, "EURGBP": 0.7, "GBPUSD": 0.8,
    "NZDUSD": 0.9, "AUDCHF": 1.0, "USDJPY": 1.0, "CADCHF": 1.1, "EURCHF": 1.2,
    "EURJPY": 1.2, "AUDCAD": 1.4, "NZDCHF": 1.5, "EURAUD": 1.7, "GBPCHF": 1.7,
    "NZDCAD": 1.8, "AUDJPY": 1.9, "EURCAD": 1.9, "AUDNZD": 2.0, "GBPJPY": 2.1,
    "GBPCAD": 2.2, "GBPAUD": 2.7, "EURNZD": 2.8, "GBPNZD": 3.0, "CHFJPY": 1.5,
    "CADJPY": 1.6, "NZDJPY": 1.8
}  # 點差結束

QUOTE_TO_USD = {  # 計價幣換算
    "USD": 1.0, "CHF": 1.0/0.80218, "GBP": 1.36386,
    "CAD": 1.0/1.38452, "JPY": 1.0/159.178, "AUD": 0.71, "NZD": 0.60
}  # 匯率結束

DATA_DIR = os.path.join(os.path.dirname(__file__), "data_pepperstone")  # 數據目錄

def get_specs(sym):  # 點值計算
    if "JPY" in sym:  # 日圓對
        return 0.01, 100000.0 * 0.01 * QUOTE_TO_USD["JPY"]  # 回傳
    counter = sym[-3:]  # 計價幣
    return 0.0001, 100000.0 * 0.0001 * QUOTE_TO_USD.get(counter, 1.0)  # 回傳

def load_data(sym, tf):  # 載入數據
    f = os.path.join(DATA_DIR, f"pepperstone_{sym.lower()}_{tf}.csv")  # 路徑
    if not os.path.exists(f): return pd.DataFrame()  # 不存在
    df = pd.read_csv(f)  # 讀取
    if len(df) < 200: return pd.DataFrame()  # 資料不足
    df["mt5_time"] = pd.to_datetime(df["timestamp_mt5"])  # 時間轉換
    df = df.set_index("mt5_time")  # 設索引
    return df  # 回傳

def run_backtest(df_raw, sym, tf, sigma, sl_atr, session, force_hr=22):  # 核心回測 (方案C邏輯)
    """
    session:
        "DAY"  = 白天全天通道 (MT5 01:15 ~ e_hr:59)
        "US"   = 晚間美盤午後 (MT5 13:00 ~ e_hr:59)
    """
    df = df_raw.copy()  # 複製
    pip_size, pip_val = get_specs(sym)  # 點值
    sp_pips = SPREADS.get(sym, 2.0)  # 點差
    sp_dist = sp_pips * pip_size  # 距離
    cost = 5.0  # 手續費

    # 指標
    df["MA20"] = df["close"].rolling(20).mean()  # SMA
    df["STD20"] = df["close"].rolling(20).std()  # STD
    df["UB"] = df["MA20"] + sigma * df["STD20"]  # 上軌
    df["LB"] = df["MA20"] - sigma * df["STD20"]  # 下軌
    tr = np.maximum(df["high"]-df["low"], np.maximum(abs(df["high"]-df["close"].shift(1)), abs(df["low"]-df["close"].shift(1))))  # TR
    df["ATR"] = tr.rolling(14).mean()  # ATR
    delta = df["close"].diff()  # 差分
    gain = delta.where(delta > 0, 0).rolling(14).mean()  # 漲幅
    loss_s = (-delta.where(delta < 0, 0)).rolling(14).mean()  # 跌幅
    df["RSI"] = 100 - (100 / (1 + (gain / (loss_s + 1e-9))))  # RSI

    pos = 0  # 倉位
    trades = []  # 記錄
    entry_p = 0.0  # 進場價
    entry_bar = 0  # 進場索引
    bar_mins = 60 if tf == "1h" else 15  # 分鐘

    # 時段設定
    if session == "DAY":  # 白天組
        s_hr, e_hr = 1, 18  # MT5 01:15 ~ 17:59
    else:  # 美盤組
        s_hr, e_hr = 13, 18  # MT5 13:00 ~ 18:59

    for i in range(35, len(df)):  # 遍歷
        dt = df.index[i]  # 時間
        hr = dt.hour  # 小時
        minute = dt.minute  # 分鐘
        c = float(df["close"].iloc[i])  # 收盤
        h = float(df["high"].iloc[i])  # 最高
        l = float(df["low"].iloc[i])  # 最低
        atr = float(df["ATR"].iloc[i])  # ATR
        ma20 = float(df["MA20"].iloc[i])  # 中軌

        # 開倉時間判斷
        if session == "DAY":  # 白天組
            is_entry = (hr == s_hr and minute >= 15) or (2 <= hr <= e_hr)  # 01:15 ~ 18:59
        else:  # 美盤組
            is_entry = (s_hr <= hr <= e_hr)  # 13:00 ~ 18:59

        is_force = (hr >= force_hr or hr == 0)  # 強制清倉

        if pos != 0:  # 持倉中
            closed = False  # 平倉標記
            exit_price = 0.0  # 出場價
            exit_reason = ""  # 原因

            if pos == 1:  # 多單
                if c >= ma20 and c > entry_p:  # 碰中軌+盈利 (方案C)
                    exit_price = c - sp_dist  # 扣差
                    exit_reason = "Mid"  # 原因
                    closed = True  # 平倉
                elif l <= entry_p - sl_atr * atr or is_force:  # SL/清倉
                    if l <= entry_p - sl_atr * atr:  # SL
                        exit_price = entry_p - sl_atr * atr - sp_dist  # SL價
                        exit_reason = "SL"  # 原因
                    else:  # 清倉
                        exit_price = c - sp_dist  # 清倉價
                        exit_reason = "Cut"  # 原因
                    closed = True  # 平倉
                if closed:  # 結算
                    pnl_pips = (exit_price - entry_p) / pip_size  # 點數
                    pnl_usd = pnl_pips * pip_val - cost  # 美金
                    trades.append({"pnl_usd": round(pnl_usd, 2), "win": pnl_usd > 0,
                                   "reason": exit_reason, "dur": (i - entry_bar) * bar_mins})  # 記錄
                    pos = 0  # 重設

            elif pos == -1:  # 空單
                if c <= ma20 and c < entry_p:  # 碰中軌+盈利 (方案C)
                    exit_price = c + sp_dist  # 扣差
                    exit_reason = "Mid"  # 原因
                    closed = True  # 平倉
                elif h >= entry_p + sl_atr * atr or is_force:  # SL/清倉
                    if h >= entry_p + sl_atr * atr:  # SL
                        exit_price = entry_p + sl_atr * atr + sp_dist  # SL價
                        exit_reason = "SL"  # 原因
                    else:  # 清倉
                        exit_price = c + sp_dist  # 清倉價
                        exit_reason = "Cut"  # 原因
                    closed = True  # 平倉
                if closed:  # 結算
                    pnl_pips = (entry_p - exit_price) / pip_size  # 點數
                    pnl_usd = pnl_pips * pip_val - cost  # 美金
                    trades.append({"pnl_usd": round(pnl_usd, 2), "win": pnl_usd > 0,
                                   "reason": exit_reason, "dur": (i - entry_bar) * bar_mins})  # 記錄
                    pos = 0  # 重設

        if pos == 0 and is_entry and not is_force:  # 開倉
            if c <= df["LB"].iloc[i] and df["RSI"].iloc[i] <= 32:  # 做多
                pos = 1  # 買
                entry_p = c + sp_dist  # 買價 (Ask)
                entry_bar = i  # 索引
            elif c >= df["UB"].iloc[i] and df["RSI"].iloc[i] >= 68:  # 做空
                pos = -1  # 賣
                entry_p = c - sp_dist  # 賣價 (Bid) — 方案C修正
                entry_bar = i  # 索引

    return trades  # 回傳

def calc_metrics(trades):  # 績效計算
    if len(trades) < 5: return None  # 樣本不足
    tot = len(trades)  # 總數
    wins = sum(1 for t in trades if t["win"])  # 勝
    wr = round(wins/tot*100, 1)  # 勝率
    pnl = round(sum(t["pnl_usd"] for t in trades), 2)  # 淨利
    win_d = sum(t["pnl_usd"] for t in trades if t["pnl_usd"] > 0)  # 毛利
    loss_d = sum(abs(t["pnl_usd"]) for t in trades if t["pnl_usd"] < 0)  # 毛損
    pf = round(win_d / (loss_d + 1e-9), 2)  # PF
    avg_win = round(win_d / max(wins, 1), 2)  # 平均獲利
    avg_loss = round(loss_d / max(tot - wins, 1), 2)  # 平均虧損
    expectancy = round(pnl / tot, 2)  # 期望值
    mid_pct = round(sum(1 for t in trades if t["reason"] == "Mid") / tot * 100, 1)  # 中軌出場%
    avg_dur = round(np.mean([t["dur"] for t in trades]), 1)  # 平均持倉

    # MDD
    bal = 100000.0  # 初始
    peak = 100000.0  # 峰值
    max_dd = 0.0  # 回撤
    for t in trades:  # 遍歷
        bal += t["pnl_usd"]  # 累加
        if bal > peak: peak = bal  # 更新
        dd = (peak - bal) / peak * 100  # 回撤%
        if dd > max_dd: max_dd = dd  # 更新
    return {"trades": tot, "wr": wr, "pf": pf, "pnl": pnl, "mdd": round(max_dd, 2),
            "avg_win": avg_win, "avg_loss": avg_loss, "exp": expectancy,
            "mid_pct": mid_pct, "avg_dur": avg_dur}

def main():  # 主程式
    print("=" * 100)  # 分隔
    print("  🚀 大規模回測篩選：方案C邏輯 × 全品種 × 15m/1h × DaytimeChannel/US_Afternoon × σ/ATR 組合")  # 標題
    print("=" * 100)  # 分隔

    # 掃描所有可用品種
    all_files = glob.glob(os.path.join(DATA_DIR, "pepperstone_*_15m.csv"))  # 取 15m 檔
    all_symbols = sorted(set(os.path.basename(f).split("_")[1].upper() for f in all_files))  # 提取品種
    all_symbols = [s for s in all_symbols if s in SPREADS]  # 過濾有點差的
    print(f"\n  找到 {len(all_symbols)} 個品種: {', '.join(all_symbols)}")  # 品種清單

    # 參數矩陣
    timeframes = ["15m", "1h"]  # 週期
    sessions = [  # 時段
        ("DAY", "☀️ 白天全天通道 (MT5 01:15~18:59)"),
        ("US",  "🌙 晚間美盤午後 (MT5 13:00~18:59)")
    ]
    sigmas = [2.0, 2.2, 2.5, 2.8, 3.0]  # σ
    sl_atrs = [1.5, 2.0, 2.5]  # ATR SL

    total_combos = len(all_symbols) * len(timeframes) * len(sessions) * len(sigmas) * len(sl_atrs)  # 總組合數
    print(f"  總掃描組合數: {total_combos}")  # 組合數

    results = []  # 結果
    done = 0  # 計數

    for sym in all_symbols:  # 遍歷品種
        for tf in timeframes:  # 遍歷週期
            df = load_data(sym, tf)  # 載入
            if df.empty: continue  # 跳過

            for sess_code, sess_name in sessions:  # 遍歷時段
                for sigma in sigmas:  # 遍歷 σ
                    for sl in sl_atrs:  # 遍歷 ATR SL
                        trades = run_backtest(df, sym, tf, sigma, sl, sess_code)  # 回測
                        metrics = calc_metrics(trades)  # 計算
                        done += 1  # 計數

                        if metrics and metrics["trades"] >= 8:  # 有效結果
                            results.append({  # 記錄
                                "symbol": sym, "tf": tf, "session": sess_code,
                                "sigma": sigma, "sl_atr": sl, "spread": SPREADS.get(sym, 2.0),
                                **metrics
                            })  # 記錄結束

            if done % 100 == 0:  # 進度
                print(f"  ... 已完成 {done}/{total_combos} 組合 ({done/total_combos*100:.0f}%)")  # 輸出

    print(f"\n  ✅ 掃描完成！有效結果: {len(results)} 組")  # 完成

    df_all = pd.DataFrame(results)  # 轉 DataFrame
    if df_all.empty:  # 空
        print("  ❌ 沒有有效結果")  # 提示
        return  # 結束

    # ═══════ 1. 各品種各時段最佳參數 ═══════
    print("\n" + "=" * 100)  # 分隔
    print("  📊 各品種 × 各時段最佳參數組合 (依淨利排序)")  # 標題
    print("=" * 100)  # 分隔

    for sess_code, sess_name in sessions:  # 遍歷時段
        df_sess = df_all[df_all["session"] == sess_code].copy()  # 過濾
        if df_sess.empty: continue  # 跳過

        # 每品種取最高淨利的參數
        best_per_sym = df_sess.loc[df_sess.groupby(["symbol", "tf"])["pnl"].idxmax()]  # 最佳
        best_per_sym = best_per_sym.sort_values("pnl", ascending=False)  # 排序

        print(f"\n  {sess_name}")  # 標題
        print(f"  {'品種':<8} {'週期':>4} {'σ':>4} {'ATR_SL':>6} {'點差':>5} {'筆數':>5} {'勝率':>6} {'PF':>6} {'淨利($)':>12} {'MDD%':>6} {'期望值':>8} {'中軌出%':>7} {'平均持倉':>8}")
        print("  " + "─" * 95)  # 分隔
        for _, r in best_per_sym.iterrows():  # 遍歷
            pnl_str = f"+${r['pnl']:,.0f}" if r['pnl'] >= 0 else f"-${abs(r['pnl']):,.0f}"  # 格式化
            marker = " ✨" if r["pnl"] > 500 and r["wr"] >= 55 and r["pf"] >= 1.3 else ""  # 標記
            print(f"  {r['symbol']:<8} {r['tf']:>4} {r['sigma']:>4.1f} {r['sl_atr']:>6.1f} {r['spread']:>5.1f} {r['trades']:>5} {r['wr']:>5.1f}% {r['pf']:>6.2f} {pnl_str:>12} {r['mdd']:>5.2f}% {r['exp']:>7.2f} {r['mid_pct']:>6.1f}% {r['avg_dur']:>7.1f}m{marker}")

    # ═══════ 2. 嚴格篩選：勝率>=55%, PF>=1.3, 淨利>$200, MDD<5% ═══════
    print("\n" + "=" * 100)  # 分隔
    print("  👑 通過嚴格篩選的王牌模組 (WR>=55%, PF>=1.3, PnL>$200, MDD<5%)")  # 標題
    print("=" * 100)  # 分隔

    elite = df_all[
        (df_all["wr"] >= 55) &
        (df_all["pf"] >= 1.3) &
        (df_all["pnl"] > 200) &
        (df_all["mdd"] < 5.0) &
        (df_all["trades"] >= 10)
    ].copy()  # 篩選

    # 每品種×時段×週期只保留最佳
    if not elite.empty:  # 有結果
        best_elite = elite.loc[elite.groupby(["symbol", "tf", "session"])["pnl"].idxmax()]  # 去重
        best_elite = best_elite.sort_values("pnl", ascending=False)  # 排序

        for sess_code, sess_name in sessions:  # 分組輸出
            sess_elite = best_elite[best_elite["session"] == sess_code]  # 過濾
            if sess_elite.empty: continue  # 跳過
            print(f"\n  {sess_name} — 精選 {len(sess_elite)} 款")  # 標題
            print(f"  {'品種':<8} {'週期':>4} {'σ':>4} {'ATR_SL':>6} {'點差':>5} {'筆數':>5} {'勝率':>6} {'PF':>6} {'淨利($)':>12} {'MDD%':>6} {'期望值':>8}")
            print("  " + "─" * 80)  # 分隔
            for _, r in sess_elite.iterrows():  # 遍歷
                pnl_str = f"+${r['pnl']:,.0f}" if r['pnl'] >= 0 else f"-${abs(r['pnl']):,.0f}"  # 格式化
                print(f"  {r['symbol']:<8} {r['tf']:>4} {r['sigma']:>4.1f} {r['sl_atr']:>6.1f} {r['spread']:>5.1f} {r['trades']:>5} {r['wr']:>5.1f}% {r['pf']:>6.2f} {pnl_str:>12} {r['mdd']:>5.2f}% {r['exp']:>7.2f}")

    # ═══════ 3. 推薦組合 ═══════
    print("\n" + "=" * 100)  # 分隔
    print("  🏆 最終推薦組合 (各時段 Top 5，不重複品種)")  # 標題
    print("=" * 100)  # 分隔

    for sess_code, sess_name in sessions:  # 分組
        if elite.empty: continue  # 跳過
        sess_elite = elite[elite["session"] == sess_code].copy()  # 過濾
        if sess_elite.empty: continue  # 跳過

        # 每品種取最佳，然後取 Top 5
        best = sess_elite.loc[sess_elite.groupby("symbol")["pnl"].idxmax()]  # 每品種最佳
        top5 = best.nlargest(5, "pnl")  # Top 5

        print(f"\n  {sess_name} — Top 5 推薦")  # 標題
        total_pnl = 0  # 累計
        for _, r in top5.iterrows():  # 遍歷
            pnl_str = f"+${r['pnl']:,.0f}"  # 格式化
            total_pnl += r["pnl"]  # 累加
            print(f"    ✅ {r['symbol']} ({r['tf']}) | σ={r['sigma']} | SL={r['sl_atr']}ATR | 勝率{r['wr']}% | PF {r['pf']} | {pnl_str} | MDD {r['mdd']}%")
        print(f"    📈 Top 5 合計淨利: +${total_pnl:,.0f}")  # 合計

    # ═══════ 4. 輸出完整 CSV ═══════
    out_csv = os.path.join(os.path.dirname(__file__), "large_scale_planC_screening.csv")  # 路徑
    df_all.sort_values("pnl", ascending=False).to_csv(out_csv, index=False, encoding="utf-8-sig")  # 儲存
    print(f"\n  [+] 全量篩選結果已輸出至: {out_csv}")  # 日誌
    print("=" * 100)  # 分隔

if __name__ == "__main__":  # 主入口
    main()  # 執行
