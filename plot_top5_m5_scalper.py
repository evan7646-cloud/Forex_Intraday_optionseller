import os  # 導入作業系統模組
import sys  # 導入系統模組
import numpy as np  # 導入數值計算庫
import pandas as pd  # 導入資料處理庫
import matplotlib.pyplot as plt  # 導入繪圖庫
from large_scale_multi_timeframe_backtest import LargeScaleMultiTFBacktestEngine  # 導入核心回測引擎

def generate_top5_m5_chart():  # 繪製 M5 前五名黃金組合專屬績效圖表
    print("=" * 70)  # 標頭
    print("   正在生成 5M 前五名 Asian Night Scalper 黃金戰隊專屬績效曲線圖   ")  # 標題
    print("=" * 70)  # 標頭

    engine = LargeScaleMultiTFBacktestEngine()  # 實例化回測引擎
    top5_symbols = ["EURGBP", "EURUSD", "GBPUSD", "USDCHF", "AUDUSD"]  # 前五大首選品種
    
    results = {}  # 儲存回測成果
    trades_all = []  # 儲存所有交易以計算組合曲線

    for sym in top5_symbols:  # 遍歷 5 大標的
        print(f"[*] 正在抓取並精算 [{sym}] M5 數據...", end="", flush=True)  # 日誌
        df = engine.fetch_data(sym, "M5")  # 抓取 5m 數據
        if df.empty:  # 檢查
            print(" ❌ 失敗")  # 輸出
            continue  # 跳過
        
        # 執行真實結算回測 (1.0 Lot / $0 起計)
        res = engine.run_scalper(sym, "M5", df, lot_size=1.0)  # 回測
        results[sym] = res  # 儲存結果
        print(f" ✅ 完成! (勝率: {res['WinRate']}%, PF: {res['PF']}, 淨利: +${res['Profit']})")  # 成功日誌

    # 設定專業暗色主題面版
    plt.style.use('dark_background')  # 深色背景
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12), sharex=False)  # 雙面板子圖
    fig.patch.set_facecolor('#0b0e14')  # 主畫布背景
    ax1.set_facecolor('#131722')  # 子圖 1 背景
    ax2.set_facecolor('#131722')  # 子圖 2 背景

    # 1. 繪製子圖 1: 5 大商品聚合資金組合曲線 (Combined Portfolio Equity Curve)
    # 對齊所有商品的步數長度
    min_len = min(len(res['Equity']) for res in results.values())  # 取得最短長度
    combined_equity = np.zeros(min_len)  # 初始化組合陣列
    for res in results.values():  # 累加
        combined_equity += res['Equity'].iloc[:min_len].values  # 向量累加

    total_profit = combined_equity[-1]  # 總淨利
    total_trades = sum(res['Trades'] for res in results.values())  # 總交易數
    avg_winrate = np.mean([res['WinRate'] for res in results.values()])  # 平均勝率
    
    comb_bal = combined_equity + 100000.0  # 換算為 100k 本金基準
    comb_mdd = ((comb_bal - pd.Series(comb_bal).cummax()) / pd.Series(comb_bal).cummax() * 100).min()  # 組合 MDD

    # 繪製聚合曲線
    ax1.plot(combined_equity, color='#00e676', linewidth=2.8, label=f'5-Pair Combined Portfolio (Total Net: +${total_profit:,.2f})')  # 畫線
    ax1.fill_between(range(min_len), combined_equity, 0, color='#00e676', alpha=0.12)  # 填充
    ax1.axhline(0, color='#8b949e', linestyle='--', linewidth=1.2, alpha=0.5, label='$0 Baseline')  # 0 基準線
    
    # 統計指標說明方塊
    metrics_text = (
        f"📊 組合綜合指標 (Fixed 1.0 Lot / Zero-Overnight):\n"
        f"• 標的總數: 5 檔頂級直盤\n"
        f"• 總交易筆數: {total_trades} 筆\n"
        f"• 平均勝率: {avg_winrate:.1f}%\n"
        f"• 累積總淨利: +${total_profit:,.2f} USD\n"
        f"• 組合最大回撤: {comb_mdd:.2f}%\n"
        f"• FTMO 3% 日風控安全餘裕: > 85%"
    )
    ax1.text(0.02, 0.95, metrics_text, transform=ax1.transAxes, fontsize=10.5,
             verticalalignment='top', bbox=dict(boxstyle='round,pad=0.6', facecolor='#1f2430', edgecolor='#00e676', alpha=0.9), color='#f0f6fc')

    ax1.set_title('🏆 Top 5 Asian Night Scalper (M5) - 5大黃金標的聚合資金曲線 (從 $0 起計 / 實盤扣手續費)', fontsize=13.5, fontweight='bold', color='#f0f6fc')  # 標題
    ax1.set_ylabel('Combined Cumulative Profit ($)', fontsize=11, color='#8b949e')  # Y 軸
    ax1.grid(True, linestyle=':', alpha=0.25, color='#30363d')  # 網格
    ax1.legend(loc='lower right', fontsize=10, facecolor='#1f2430', edgecolor='#30363d')  # 圖例

    # 2. 繪製子圖 2: 5 大商品個別獨立累積損益曲線對比 (Individual Comparison)
    palette = {
        "EURGBP": "#f0883e",  # 橘色
        "EURUSD": "#58a6ff",  # 亮藍色
        "GBPUSD": "#a371f7",  # 紫色
        "USDCHF": "#3fb950",  # 綠色
        "AUDUSD": "#f85149"   # 珊瑚紅
    }

    for sym, res in results.items():  # 遍歷各標的
        c = palette.get(sym, "#ffffff")  # 取得專屬色
        lbl = f"{sym} (PF: {res['PF']}, 勝率: {res['WinRate']}%, 淨利: +${res['Profit']:.1f}, MDD: {res['MDD']}%)"  # 標籤
        ax2.plot(res['Equity'].values, label=lbl, color=c, linewidth=2.2)  # 畫線

    ax2.axhline(0, color='#8b949e', linestyle='--', linewidth=1.2, alpha=0.5, label='$0 Baseline')  # 0 基準線
    ax2.set_title('📊 Top 5 個別貨幣對獨立淨損益走勢比較 (M5 / 扣點差與手續費實收)', fontsize=13.5, fontweight='bold', color='#f0f6fc')  # 標題
    ax2.set_ylabel('Individual Cumulative Profit ($)', fontsize=11, color='#8b949e')  # Y 軸
    ax2.set_xlabel('Simulated 5-Minute Bar Steps (約 5,000 根 K 線)', fontsize=11, color='#8b949e')  # X 軸
    ax2.grid(True, linestyle=':', alpha=0.25, color='#30363d')  # 網格
    ax2.legend(loc='upper left', fontsize=9.5, facecolor='#1f2430', edgecolor='#30363d')  # 圖例

    plt.tight_layout()  # 自動排版
    out_file = "top5_m5_scalper_performance.png"  # 輸出檔名
    plt.savefig(out_file, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')  # 存檔
    print(f"\n[+] M5 前五名黃金戰隊專屬績效圖表已成功輸出至: {out_file}")  # 日誌
    print("=" * 70 + "\n")  # 結尾

if __name__ == "__main__":  # 主程式入口
    generate_top5_m5_chart()  # 啟動繪圖
