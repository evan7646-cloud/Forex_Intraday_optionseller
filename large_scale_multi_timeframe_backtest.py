import os  # 導入作業系統模組
import glob  # 導入檔案路徑匹配模組
import json  # 導入 JSON 解析模組
import datetime  # 導入日期時間處理模組
import numpy as np  # 導入數值運算庫
import pandas as pd  # 導入資料表格分析庫
import warnings  # 導入警告控制模組

warnings.filterwarnings("ignore")  # 忽略無害警告訊息

# 100% 依據使用者 MT5 Market Watch 實盤截圖精準點差 (Pips)
EXACT_SPREADS = {  # 點差字典
    "EURUSD": 0.3, "USDCAD": 0.6, "USDCHF": 0.6, "EURGBP": 0.7, "GBPUSD": 0.8,
    "NZDUSD": 0.9, "AUDCHF": 1.0, "USDJPY": 1.0, "CADCHF": 1.1, "EURCHF": 1.2,
    "EURJPY": 1.2, "AUDCAD": 1.4, "NZDCHF": 1.5, "EURAUD": 1.7, "GBPCHF": 1.7,
    "NZDCAD": 1.8, "AUDJPY": 1.9, "EURCAD": 1.9, "AUDNZD": 2.0, "GBPJPY": 2.1,
    "GBPCAD": 2.2, "GBPAUD": 2.7, "EURNZD": 2.8, "GBPNZD": 3.0, "CHFJPY": 1.5, "CADJPY": 1.6
}  # 點差結束

# MT5 實盤計價幣別對美金即時匯率
QUOTE_TO_USD = {  # 匯率字典
    "USD": 1.00000,                  # 美金 $1.00000
    "CHF": 1.0 / 0.80218,            # 1 CHF = $1.24660 USD (每手每點 = $12.47 USD)
    "GBP": 1.36386,                  # 1 GBP = $1.36386 USD (每手每點 = $13.64 USD)
    "CAD": 1.0 / 1.38452,            # 1 CAD = $0.72227 USD (每手每點 = $7.22 USD)
    "JPY": 1.0 / 159.178,            # 1 JPY = $0.006282 USD (每手每點 = $6.28 USD)
    "AUD": 0.71000,                  # 1 AUD = $0.71000 USD (每手每點 = $7.10 USD)
    "NZD": 0.60000                   # 1 NZD = $0.60000 USD (每手每點 = $6.00 USD)
}  # 匯率結束

def get_specs(sym: str):  # 依據計價貨幣計算每點單位與換算美金價值
    if "JPY" in sym:  # 日圓貨幣對
        return 0.01, 100000.0 * 0.01 * QUOTE_TO_USD["JPY"]  # JPY
    counter_curr = sym[-3:]  # 計價貨幣
    return 0.0001, 100000.0 * 0.0001 * QUOTE_TO_USD.get(counter_curr, 1.0)  # 外匯

def backtest_single_asset(filepath: str, sl_atr: float = 2.0, adx_thresh: float = 30.0, lot_size: float = 1.0):  # 單一資產與週期回測
    filename = os.path.basename(filepath)  # 檔名
    parts = filename.replace(".csv", "").split("_")  # 分割檔名
    if len(parts) < 3: return None  # 格式檢查
    sym = parts[1].upper()  # 標的代碼
    tf = parts[2].lower()  # 週期
    if sym not in EXACT_SPREADS: return None  # 點差檢查
    
    df = pd.read_csv(filepath)  # 讀取 CSV
    if len(df) < 200: return None  # 資料量檢查
    
    pip_size, pip_val_usd = get_specs(sym)  # 規格
    sp_pips = EXACT_SPREADS[sym]  # 點差
    sp_dist = sp_pips * pip_size  # 點差距離
    cost_per_trade = 5.0 * lot_size  # 每手進出固定扣除 $5.00 手續費
    
    # 指標運算
    df["MA20"] = df["close"].rolling(20).mean()  # 20 SMA
    df["STD20"] = df["close"].rolling(20).std()  # 20 STD
    df["UB"] = df["MA20"] + 2.2 * df["STD20"]  # 上軌 (2.2σ)
    df["LB"] = df["MA20"] - 2.2 * df["STD20"]  # 下軌 (2.2σ)
    
    tr = np.maximum(df["high"] - df["low"], np.maximum(abs(df["high"] - df["close"].shift(1)), abs(df["low"] - df["close"].shift(1))))  # TR
    df["ATR"] = tr.rolling(14).mean()  # ATR
    
    plus_dm = (df["high"] - df["high"].shift(1)).clip(lower=0)  # +DM
    minus_dm = (df["low"].shift(1) - df["low"]).clip(lower=0)  # -DM
    plus_di = 100 * (plus_dm.ewm(span=14).mean() / (df["ATR"] + 1e-9))  # +DI
    minus_di = 100 * (minus_dm.ewm(span=14).mean() / (df["ATR"] + 1e-9))  # -DI
    dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9))  # DX
    df["ADX"] = dx.ewm(span=14).mean()  # ADX
    
    delta = df["close"].diff()  # 差分
    gain = delta.where(delta > 0, 0).rolling(14).mean()  # 漲幅
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()  # 跌幅
    df["RSI"] = 100 - (100 / (1 + (gain / (loss + 1e-9))))  # RSI
    
    df["mt5_time"] = pd.to_datetime(df["timestamp_mt5"])  # MT5 伺服器時間
    pos = 0  # 倉位
    trades = []  # 交易記錄
    entry_p = 0.0  # 進場價
    entry_time = None  # 進場時間
    
    for i in range(35, len(df)):  # 遍歷 K 棒
        dt = df["mt5_time"].iloc[i]  # 時間
        hr = dt.hour  # 小時 (MT5)
        minute = dt.minute  # 分鐘 (MT5)
        c = float(df["close"].iloc[i])  # 收盤
        h = float(df["high"].iloc[i])  # 最高
        l = float(df["low"].iloc[i])  # 最低
        atr = float(df["ATR"].iloc[i])  # ATR
        adx = float(df["ADX"].iloc[i])  # ADX
        
        is_force = (hr >= 9)  # MT5 09:00 (台北 14:00) 歐洲盤前強制全平 (Zero-Overnight)
        
        if pos != 0:  # 持倉中
            closed = False  # 平倉標記
            exit_price = 0.0  # 出場價
            
            if pos == 1:  # 多單
                if c >= df["MA20"].iloc[i] and c > entry_p:  # 碰中軌且高於成本
                    exit_price = c - sp_dist  # 扣點差
                    closed = True  # 平倉
                elif l <= entry_p - sl_atr * atr or is_force:  # 停損或強平
                    exit_price = (entry_p - sl_atr * atr - sp_dist) if l <= entry_p - sl_atr * atr else (c - sp_dist)  # 出場價
                    closed = True  # 平倉
                if closed:  # 結算
                    pnl_pips = (exit_price - entry_p)/pip_size  # 點數
                    pnl_usd = pnl_pips * pip_val_usd - cost_per_trade  # 美金淨利 (已扣手續費)
                    trades.append({"pnl_usd": pnl_usd, "win": pnl_usd > 0, "time": dt})  # 記錄
                    pos = 0  # 重設
                    
            elif pos == -1:  # 空單
                if c <= df["MA20"].iloc[i] and c < entry_p:  # 碰中軌且低於成本
                    exit_price = c + sp_dist  # 扣點差
                    closed = True  # 平倉
                elif h >= entry_p + sl_atr * atr or is_force:  # 停損或強平
                    exit_price = (entry_p + sl_atr * atr + sp_dist) if h >= entry_p + sl_atr * atr else (c + sp_dist)  # 出場價
                    closed = True  # 平倉
                if closed:  # 結算
                    pnl_pips = (entry_p - exit_price)/pip_size  # 點數
                    pnl_usd = pnl_pips * pip_val_usd - cost_per_trade  # 美金淨利 (已扣手續費)
                    trades.append({"pnl_usd": pnl_usd, "win": pnl_usd > 0, "time": dt})  # 記錄
                    pos = 0  # 重設
                    
        # 開倉條件：MT5 00:15 ~ 07:45 亞洲夜間靜態盤 且 ADX < 30
        is_entry = (0 <= hr <= 7) and not (hr == 0 and minute < 15) and adx < adx_thresh and not is_force  # 條件
        if pos == 0 and is_entry:  # 開倉檢查
            if c <= df["LB"].iloc[i] and df["RSI"].iloc[i] <= 32:  # 跌破下軌做多 (賣 Put)
                pos = 1  # 買多
                entry_p = c + sp_dist  # 買價
            elif c >= df["UB"].iloc[i] and df["RSI"].iloc[i] >= 68:  # 突破上軌做空 (賣 Call)
                pos = -1  # 賣空
                entry_p = c  # 賣價
                
    if len(trades) < 8: return None  # 樣本過少排除
    
    tot = len(trades)  # 總筆數
    wins = sum(1 for t in trades if t["win"])  # 獲利數
    losses = tot - wins  # 虧損數
    wr = round(wins / tot * 100, 2)  # 勝率
    pnl = round(sum(t["pnl_usd"] for t in trades), 2)  # 實質總淨利
    win_d = sum(t["pnl_usd"] for t in trades if t["pnl_usd"] > 0)  # 毛利
    loss_d = sum(abs(t["pnl_usd"]) for t in trades if t["pnl_usd"] < 0)  # 毛損
    pf = round(win_d / (loss_d + 1e-9), 2) if loss_d > 0 else 99.0  # PF
    
    # 計算 MDD 與夏普
    df_t = pd.DataFrame(trades).sort_values(by="time").reset_index(drop=True)  # 表格
    bal = 100000.0 + df_t["pnl_usd"].cumsum()  # 淨值
    cum_max = bal.cummax()  # 新高
    dd_usd = cum_max - bal  # 回撤金額
    max_dd_usd = round(dd_usd.max(), 2)  # 最大回撤美金
    max_dd_pct = round((dd_usd / cum_max * 100).max(), 2)  # 最大回撤百分比
    
    duration_days = max((df_t["time"].iloc[-1] - df_t["time"].iloc[0]).total_seconds() / 86400.0, 1.0)  # 天數
    ann_roi = round((pnl / 100000.0) * 100.0 * (365.0 / duration_days), 2)  # 年化報酬
    
    trade_ret = df_t["pnl_usd"] / 100000.0  # 報酬
    mean_r = trade_ret.mean()  # 平均
    std_r = trade_ret.std()  # 標準差
    trades_yr = tot * (365.0 / duration_days)  # 年交易次數
    sharpe = round((mean_r * trades_yr - 0.02) / (std_r * np.sqrt(trades_yr) + 1e-9), 2) if std_r > 0 else 0.0  # 夏普
    calmar = round(ann_roi / (max_dd_pct + 1e-9), 2) if max_dd_pct > 0 else 99.0  # 卡瑪
    
    return {  # 回傳分析字典
        "symbol": sym, "timeframe": tf, "spread_pips": sp_pips, "trades": tot,
        "wins": wins, "losses": losses, "win_rate": wr, "total_pnl": pnl, "annualized_roi": ann_roi,
        "profit_factor": pf, "max_dd_pct": max_dd_pct, "max_dd_usd": max_dd_usd,
        "sharpe_ratio": sharpe, "calmar_ratio": calmar, "trades_list": trades
    }  # 字典結束

def main():  # 主程式
    print("==========================================================================")  # 分隔線
    print(" 🚀 啟動【全市場大規模跨商品與跨週期 (5m, 15m, 1h)】期權賣方收租回測篩選...")  # 標題
    print("==========================================================================")  # 分隔線
    
    csv_files = glob.glob("data_pepperstone/pepperstone_*.csv")  # 取得所有數據檔案
    all_results = []  # 結果清單
    
    for f in csv_files:  # 遍歷檔案
        res = backtest_single_asset(f)  # 執行回測
        if res:  # 有結果
            all_results.append(res)  # 寫入清單
            
    df_rank = pd.DataFrame(all_results)  # 轉為 DataFrame
    df_rank_clean = df_rank.drop(columns=["trades_list"])  # 移除交易明細方便檢視
    df_rank_clean = df_rank_clean.sort_values(by="total_pnl", ascending=False).reset_index(drop=True)  # 依淨利排序
    
    print("\n🏆【全市場跨週期 (5m / 15m / 1h) 全量篩選排行榜前 25 名】")  # 標題
    print(df_rank_clean.head(25).to_string(index=True))  # 輸出前 25 名
    
    # 挑選出勝率 >= 60%、PF >= 1.4、夏普 >= 1.0 的頂級模組
    elite_modules = df_rank[
        (df_rank["win_rate"] >= 60.0) &
        (df_rank["profit_factor"] >= 1.5) &
        (df_rank["total_pnl"] > 250.0) &
        (df_rank["sharpe_ratio"] > 1.0)
    ].sort_values(by="total_pnl", ascending=False).reset_index(drop=True)  # 篩選王牌
    
    print("\n" + "="*80)  # 分隔線
    print(f" 👑【通過機構級嚴格濾網 (勝率>=60%, PF>=1.5, 夏普>1.0) 的終極王牌收租模組: 共 {len(elite_modules)} 款】")  # 標題
    print("="*80)  # 分隔線
    print(elite_modules.drop(columns=["trades_list"]).to_string(index=True))  # 輸出王牌清單
    
    # 計算終極王牌組合的合併總體績效
    combined_trades = []  # 組合交易
    for idx, row in elite_modules.iterrows():  # 遍歷王牌
        for t in row["trades_list"]:  # 遍歷交易
            t["symbol"] = row["symbol"]  # 標記標的
            t["tf"] = row["timeframe"]  # 標記週期
            combined_trades.append(t)  # 加入總表
            
    df_comb = pd.DataFrame(combined_trades).sort_values(by="time").reset_index(drop=True)  # 依時間排序
    c_tot = len(df_comb)  # 總筆數
    c_wins = sum(1 for t in combined_trades if t["win"])  # 獲利數
    c_wr = round(c_wins / c_tot * 100, 2)  # 勝率
    c_pnl = round(sum(t["pnl_usd"] for t in combined_trades), 2)  # 淨利
    c_win_d = sum(t["pnl_usd"] for t in combined_trades if t["pnl_usd"] > 0)  # 毛利
    c_loss_d = sum(abs(t["pnl_usd"]) for t in combined_trades if t["pnl_usd"] < 0)  # 毛損
    c_pf = round(c_win_d / (c_loss_d + 1e-9), 2)  # PF
    
    c_bal = 100000.0 + df_comb["pnl_usd"].cumsum()  # 淨值
    c_peak = c_bal.cummax()  # 新高
    c_dd_usd = c_peak - c_bal  # 回撤
    c_max_dd_usd = round(c_dd_usd.max(), 2)  # 最大回撤美金
    c_max_dd_pct = round((c_dd_usd / c_peak * 100).max(), 2)  # 最大回撤百分比
    
    c_days = max((df_comb["time"].iloc[-1] - df_comb["time"].iloc[0]).total_seconds() / 86400.0, 1.0)  # 天數
    c_ann_roi = round((c_pnl / 100000.0) * 100.0 * (365.0 / c_days), 2)  # 年化投報
    
    c_ret = df_comb["pnl_usd"] / 100000.0  # 報酬
    c_sharpe = round((c_ret.mean() * (c_tot * 365.0 / c_days) - 0.02) / (c_ret.std() * np.sqrt(c_tot * 365.0 / c_days) + 1e-9), 2)  # 夏普
    c_calmar = round(c_ann_roi / (c_max_dd_pct + 1e-9), 2)  # 卡瑪
    
    print("\n" + "="*80)  # 分隔線
    print(" 🏆【終極精選王牌收租旗艦組合總合績效】")  # 標題
    print(f" • 總交易筆數: {c_tot} 筆 (勝: {c_wins}W / 負: {c_tot-c_wins}L)")  # 筆數
    print(f" • 綜合勝率 (Win Rate):       {c_wr}%")  # 勝率
    print(f" • 獲利因子 (Profit Factor):   {c_pf}")  # PF
    print(f" • 實質總淨利 (Total Net PnL): +${c_pnl:,.2f} USD")  # 淨利
    print(f" • 預估年化報酬率:             {c_ann_roi}%")  # 年化報酬
    print(f" • 歷史最大回撤 (Max DD):      -{c_max_dd_pct}% (-${c_max_dd_usd:,.2f} USD)")  # MDD
    print(f" • 年化夏普比率 (Sharpe):      {c_sharpe}")  # 夏普
    print(f" • 卡瑪比率 (Calmar):          {c_calmar}")  # 卡瑪
    print("="*80 + "\n")  # 分隔線
    
    # 匯出全量篩選結果至 CSV
    out_csv = "large_scale_screening_ranking_results.csv"  # 檔名
    df_rank_clean.to_csv(out_csv, index=False, encoding="utf-8-sig")  # 儲存
    print(f"[+] 全量篩選排行榜已成功匯出至: {out_csv}")  # 日誌

if __name__ == "__main__":  # 主入口
    main()  # 執行
