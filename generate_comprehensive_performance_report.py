import os  # 導入作業系統模組
import json  # 導入 JSON 解析模組
import datetime  # 導入日期時間處理模組
import numpy as np  # 導入數值運算庫
import pandas as pd  # 導入資料表格處理庫

def calculate_metrics_for_trades(trades_list, initial_capital=100000.0):  # 計算單一模組或組合的完整量化風控與報酬指標
    if not trades_list or len(trades_list) == 0:  # 無交易檢查
        return None  # 回傳空
    
    df_t = pd.DataFrame(trades_list)  # 轉為 DataFrame
    df_t["exit_dt"] = pd.to_datetime(df_t["exit_time"])  # 出場時間
    df_t = df_t.sort_values(by="exit_dt").reset_index(drop=True)  # 依出場時間正序排列
    
    tot_trades = len(df_t)  # 總交易筆數
    wins = (df_t["pnl_usd"] > 0).sum()  # 獲利筆數
    losses = (df_t["pnl_usd"] <= 0).sum()  # 虧損筆數
    win_rate = round(wins / tot_trades * 100, 2)  # 勝率 (%)
    
    total_pnl = round(df_t["pnl_usd"].sum(), 2)  # 實質總淨利 (USD)
    win_dollars = df_t[df_t["pnl_usd"] > 0]["pnl_usd"].sum()  # 總獲利金額
    loss_dollars = abs(df_t[df_t["pnl_usd"] < 0]["pnl_usd"].sum())  # 總虧損金額
    profit_factor = round(win_dollars / (loss_dollars + 1e-9), 2) if loss_dollars > 0 else 99.0  # 獲利因子 (PF)
    
    avg_win = win_dollars / wins if wins > 0 else 0.0  # 平均獲利金額
    avg_loss = loss_dollars / losses if losses > 0 else 0.0  # 平均虧損金額
    payoff_ratio = round(avg_win / (avg_loss + 1e-9), 2) if avg_loss > 0 else 99.0  # 盈虧比 (Payoff Ratio)
    avg_trade_pnl = round(total_pnl / tot_trades, 2)  # 每筆交易期望值 (USD)
    
    # 計算資金權益曲線與最大回撤 (MDD)
    df_t["equity"] = initial_capital + df_t["pnl_usd"].cumsum()  # 累計帳戶淨值
    peak_series = df_t["equity"].cummax()  # 淨值歷史新高序列
    dd_usd_series = peak_series - df_t["equity"]  # 回撤美金金額序列
    dd_pct_series = (dd_usd_series / peak_series) * 100.0  # 回撤百分比序列
    
    max_dd_usd = round(dd_usd_series.max(), 2)  # 歷史最大回撤金額 ($)
    max_dd_pct = round(dd_pct_series.max(), 2)  # 歷史最大回撤百分比 (%)
    
    # 計算年化報酬率 (以樣本時間跨度計算年化因子)
    start_time = df_t["exit_dt"].iloc[0]  # 起始時間
    end_time = df_t["exit_dt"].iloc[-1]  # 結束時間
    duration_days = max((end_time - start_time).total_seconds() / 86400.0, 1.0)  # 總天數
    
    total_roi_pct = (total_pnl / initial_capital) * 100.0  # 總投報率 (%)
    annualized_return_pct = round(total_roi_pct * (365.0 / duration_days), 2)  # 年化投報率 (%)
    
    # 計算夏普比率 (Sharpe Ratio, 年化無風險利率設為 2.0%)
    # 以每筆交易報酬率標準差進行年化 (每年預估交易筆數 = tot_trades * (365 / duration_days))
    trade_returns = df_t["pnl_usd"] / initial_capital  # 每筆收益率
    mean_ret = trade_returns.mean()  # 平均每筆收益率
    std_ret = trade_returns.std()  # 每筆收益率標準差
    trades_per_year = tot_trades * (365.0 / duration_days)  # 預估年交易次數
    
    if std_ret > 0:  # 標準差大於 0
        sharpe_ratio = round((mean_ret * trades_per_year - 0.02) / (std_ret * np.sqrt(trades_per_year) + 1e-9), 2)  # 年化夏普比率
    else:  # 標準差為 0
        sharpe_ratio = 0.0  # 夏普為 0
        
    # 計算索提諾比率 (Sortino Ratio，僅考慮下行波動)
    downside_returns = trade_returns[trade_returns < 0]  # 虧損交易
    downside_std = downside_returns.std() if len(downside_returns) > 1 else std_ret  # 下行標準差
    if downside_std > 0:  # 下行標準差大於 0
        sortino_ratio = round((mean_ret * trades_per_year - 0.02) / (downside_std * np.sqrt(trades_per_year) + 1e-9), 2)  # 年化索提諾比率
    else:  # 否則
        sortino_ratio = 99.0  # 極佳
        
    # 計算卡瑪比率 (Calmar Ratio = 年化報酬率 / 最大回撤%)
    if max_dd_pct > 0:  # 最大回撤大於 0
        calmar_ratio = round(annualized_return_pct / max_dd_pct, 2)  # 卡瑪比率
    else:  # 無回撤
        calmar_ratio = 99.0  # 卡瑪比率 99
        
    return {  # 回傳字典
        "total_trades": tot_trades, "wins": wins, "losses": losses, "win_rate_pct": win_rate,
        "total_pnl_usd": total_pnl, "total_roi_pct": round(total_roi_pct, 2), "annualized_return_pct": annualized_return_pct,
        "profit_factor": profit_factor, "payoff_ratio": payoff_ratio, "avg_trade_pnl_usd": avg_trade_pnl,
        "max_drawdown_usd": max_dd_usd, "max_drawdown_pct": max_dd_pct,
        "sharpe_ratio": sharpe_ratio, "sortino_ratio": sortino_ratio, "calmar_ratio": calmar_ratio,
        "duration_days": round(duration_days, 1)
    }  # 字典結束

def main():  # 主程式
    print("==========================================================================")  # 分隔線
    print(" 📊 開始生成【純期權賣方收租量化旗艦組合】深度績效與風控指標分析報告...")  # 標題
    print("==========================================================================")  # 分隔線
    
    json_path = os.path.join(os.path.dirname(__file__), "strategy_results.json")  # JSON 路徑
    if not os.path.exists(json_path):  # 檔案檢查
        print("❌ 未找到 strategy_results.json，請先執行 update_strategy_data.py！")  # 錯誤
        return  # 退出
        
    with open(json_path, "r", encoding="utf-8") as f:  # 讀取
        data = json.load(f)  # 解析
        
    all_trades = data.get("all_trades", [])  # 總交易
    modules_meta = data.get("modules_summary", [])  # 模組元數據
    
    rows = []  # 報表列陣列
    
    # 1. 逐一計算 10 大獨立模組之指標
    for mod in modules_meta:  # 遍歷模組
        mod_id = mod["module_id"]  # ID
        sym = mod["symbol"]  # 品種
        tf = mod["timeframe"]  # 週期
        strat_name = mod["strategy"]  # 名稱
        
        mod_trades = [t for t in all_trades if t.get("module_id") == mod_id or t.get("symbol") == sym]  # 抽取該模組交易
        m = calculate_metrics_for_trades(mod_trades, initial_capital=100000.0)  # 計算指標
        if not m: continue  # 檢查
        
        rows.append({  # 加入列
            "類型": "獨立模組", "模組識別碼": mod_id, "交易品種": sym, "週期": tf,
            "總交易次數": m["total_trades"], "獲利筆數(W)": m["wins"], "虧損筆數(L)": m["losses"],
            "勝率(%)": f"{m['win_rate_pct']}%", "實質總淨利(USD)": f"${m['total_pnl_usd']:,.2f}",
            "總投報率(%)": f"{m['total_roi_pct']}%", "預估年化報酬(%)": f"{m['annualized_return_pct']}%",
            "獲利因子(PF)": m["profit_factor"], "盈虧比(Payoff)": m["payoff_ratio"], "每筆期望值(USD)": f"${m['avg_trade_pnl_usd']}",
            "最大回撤金額($)": f"-${m['max_drawdown_usd']:,.2f}", "最大回撤百分比(%)": f"-{m['max_drawdown_pct']}%",
            "夏普比率(Sharpe)": m["sharpe_ratio"], "索提諾比率(Sortino)": m["sortino_ratio"], "卡瑪比率(Calmar)": m["calmar_ratio"]
        })  # 結束
        
    # 2. 計算全組合旗艦整體指標
    p = calculate_metrics_for_trades(all_trades, initial_capital=100000.0)  # 組合指標
    if p:  # 若計算成功
        rows.append({  # 加入組合總結列
            "類型": "🏆 全旗艦組合", "模組識別碼": "PORTFOLIO_TOTAL", "交易品種": "10大交叉對組合", "週期": "5M / 15M",
            "總交易次數": p["total_trades"], "獲利筆數(W)": p["wins"], "虧損筆數(L)": p["losses"],
            "勝率(%)": f"{p['win_rate_pct']}%", "實質總淨利(USD)": f"${p['total_pnl_usd']:,.2f}",
            "總投報率(%)": f"{p['total_roi_pct']}%", "預估年化報酬(%)": f"{p['annualized_return_pct']}%",
            "獲利因子(PF)": p["profit_factor"], "盈虧比(Payoff)": p["payoff_ratio"], "每筆期望值(USD)": f"${p['avg_trade_pnl_usd']}",
            "最大回撤金額($)": f"-${p['max_drawdown_usd']:,.2f}", "最大回撤百分比(%)": f"-{p['max_drawdown_pct']}%",
            "夏普比率(Sharpe)": p["sharpe_ratio"], "索提諾比率(Sortino)": p["sortino_ratio"], "卡瑪比率(Calmar)": p["calmar_ratio"]
        })  # 結束
        
    df_report = pd.DataFrame(rows)  # 轉為 DataFrame
    
    # 輸出 CSV 檔案 (UTF-8 with BOM 防 Excel 亂碼)
    csv_out_path = os.path.join(os.path.dirname(__file__), "portfolio_performance_analysis_report.csv")  # 輸出路徑
    df_report.to_csv(csv_out_path, index=False, encoding="utf-8-sig")  # 儲存
    print(f"\n[+] 完整績效風控分析報告已成功儲存至: {csv_out_path}")  # 日誌
    
    # 終端輸出完整漂亮表格
    print("\n==========================================================================")  # 分隔線
    print(" 🏆【純期權賣方收租 10 大模組與旗艦組合深度績效報告】")  # 標題
    print("==========================================================================")  # 分隔線
    print(df_report.to_string(index=False))  # 輸出表格

if __name__ == "__main__":  # 主入口
    main()  # 執行
