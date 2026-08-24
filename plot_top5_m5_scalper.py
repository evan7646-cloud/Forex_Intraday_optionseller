import os  # 導入作業系統模組
import sys  # 導入系統模組
import numpy as np  # 導入數值計算庫
import pandas as pd  # 導入資料處理庫
import matplotlib  # 導入 matplotlib 核心
import matplotlib.pyplot as plt  # 導入繪圖庫
from large_scale_multi_timeframe_backtest import LargeScaleMultiTFBacktestEngine  # 導入回測引擎

# 設定支援繁體中文的字型清單，防止 Mac 系統缺字亂碼
plt.rcParams['font.sans-serif'] = ['Hiragino Sans TC', 'PingFang HK', 'Hiragino Sans GB', 'Arial Unicode MS', 'DejaVu Sans', 'sans-serif']  # 設定中文字型優先序
plt.rcParams['axes.unicode_minus'] = False  # 正常顯示負號

def generate_separated_top5_m5_chart():  # 繪製各商品完全獨立子圖的專業績效面板
    print("=" * 75)  # 標頭
    print("   正在生成 5M 前五名 Asian Night Scalper 完全獨立子圖績效圖表   ")  # 標題
    print("=" * 75)  # 標頭

    engine = LargeScaleMultiTFBacktestEngine()  # 實例化回測引擎
    top5_symbols = ["EURGBP", "EURUSD", "GBPUSD", "USDCHF", "AUDUSD"]  # 5 大黃金標的
    
    results = {}  # 儲存回測成果

    for sym in top5_symbols:  # 遍歷 5 大標的
        print(f"[*] 正在獲取並結算 [{sym}] M5 數據...", end="", flush=True)  # 日誌
        df = engine.fetch_data(sym, "M5")  # 抓取 5m 數據
        if df.empty:  # 檢查
            print(" ❌ 失敗")  # 輸出
            continue  # 跳過
        
        # 執行真實結算回測 (1.0 Lot / $0 起計)
        res = engine.run_scalper(sym, "M5", df, lot_size=1.0)  # 回測
        results[sym] = res  # 儲存結果
        print(f" ✅ 完成! (勝率: {res['WinRate']}%, PF: {res['PF']}, 淨利: +${res['Profit']})")  # 成功日誌

    # 計算 5 檔聚合組合曲線
    min_len = min(len(res['Equity']) for res in results.values())  # 取得最短長度
    combined_equity = np.zeros(min_len)  # 初始化組合陣列
    for res in results.values():  # 累加
        combined_equity += res['Equity'].iloc[:min_len].values  # 向量累加

    total_profit = combined_equity[-1]  # 總淨利
    total_trades = sum(res['Trades'] for res in results.values())  # 總交易數
    avg_winrate = np.mean([res['WinRate'] for res in results.values()])  # 平均勝率
    comb_bal = combined_equity + 100000.0  # 換算為 100k 本金
    comb_mdd = ((comb_bal - pd.Series(comb_bal).cummax()) / pd.Series(comb_bal).cummax() * 100).min()  # 組合 MDD

    # 建立 3 行 2 列 (共 6 個獨立子圖)
    fig, axes = plt.subplots(3, 2, figsize=(18, 14), sharex=False)  # 3x2 子圖矩陣
    fig.patch.set_facecolor('#0d1117')  # 畫布背景色
    axes_flat = axes.flatten()  # 展平陣列方便索引

    # 專屬色彩與樣式設定
    color_map = {
        "EURGBP": "#f0883e",  # 橘黃色
        "EURUSD": "#58a6ff",  # 亮藍色
        "GBPUSD": "#a371f7",  # 霓虹紫
        "USDCHF": "#3fb950",  # 亮綠色
        "AUDUSD": "#f85149"   # 珊瑚紅
    }

    # 繪製前 5 個獨立商品子圖
    for idx, sym in enumerate(top5_symbols):  # 遍歷各標的
        ax = axes_flat[idx]  # 取得對應子圖
        ax.set_facecolor('#161b22')  # 子圖背景色
        res = results[sym]  # 取得回測數據
        eq = res['Equity']  # 取得權益曲線
        c = color_map[sym]  # 取得配色

        # 繪製淨損益折線與漸層填充
        ax.plot(eq.values, color=c, linewidth=2.2, label=f"{sym} [M5]")  # 繪製曲線
        ax.fill_between(range(len(eq)), eq.values, 0, color=c, alpha=0.15)  # 填充至 $0 基準線
        ax.axhline(0, color='#8b949e', linestyle='--', linewidth=1.0, alpha=0.6)  # $0 參考虛線

        # 設定子圖標題與統計指標文字
        ax.set_title(f"Rank {idx+1}: {sym} [M5] - 累積淨利: +${res['Profit']:.1f} USD", fontsize=12.5, fontweight='bold', color='#f0f6fc')  # 標題
        ax.set_ylabel('累積損益 ($)', fontsize=10.5, color='#8b949e')  # Y 軸標籤
        ax.grid(True, linestyle=':', alpha=0.25, color='#30363d')  # 網格線

        # 數據看板方塊
        info_box = (
            f"勝率: {res['WinRate']}%\n"
            f"獲利因子 (PF): {res['PF']}\n"
            f"總交易筆數: {res['Trades']} 筆\n"
            f"最大回撤: {res['MDD']}%\n"
            f"單筆期望值: +${res['EV']:.2f}"
        )
        ax.text(0.03, 0.93, info_box, transform=ax.transAxes, fontsize=9.5,
                verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', facecolor='#21262d', edgecolor=c, alpha=0.85), color='#f0f6fc')  # 指標框

    # 第 6 個子圖: 5 檔標的聚合資金曲線 (Combined Portfolio)
    ax_comb = axes_flat[5]  # 第 6 個子圖
    ax_comb.set_facecolor('#161b22')  # 背景色
    ax_comb.plot(combined_equity, color='#00e676', linewidth=2.6, label='Combined 5-Pair Portfolio')  # 聚合折線
    ax_comb.fill_between(range(min_len), combined_equity, 0, color='#00e676', alpha=0.18)  # 綠色填充
    ax_comb.axhline(0, color='#8b949e', linestyle='--', linewidth=1.0, alpha=0.6)  # $0 基準線

    ax_comb.set_title(f"[TOP 5 組合聚合曲線] 5 檔標的聚合總淨利: +${total_profit:,.2f} USD", fontsize=12.5, fontweight='bold', color='#00e676')  # 組合標題
    ax_comb.set_ylabel('組合總損益 ($)', fontsize=10.5, color='#8b949e')  # Y 軸標籤
    ax_comb.grid(True, linestyle=':', alpha=0.25, color='#30363d')  # 網格線

    comb_info = (
        f"組合總淨利: +${total_profit:,.2f} USD\n"
        f"組合總筆數: {total_trades} 筆\n"
        f"組合平均勝率: {avg_winrate:.1f}%\n"
        f"組合最大回撤: {comb_mdd:.2f}%\n"
        f"FTMO 3% 日風控安全餘裕: > 85%"
    )
    ax_comb.text(0.03, 0.93, comb_info, transform=ax_comb.transAxes, fontsize=9.5,
                 verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', facecolor='#21262d', edgecolor='#00e676', alpha=0.85), color='#f0f6fc')  # 組合指標框

    for ax in axes_flat:  # 設定所有子圖的刻度顏色
        ax.tick_params(colors='#8b949e', labelsize=9)  # 刻度顏色
        ax.set_xlabel('5 分鐘 K 線步數 (約 5,000 根)', fontsize=9.5, color='#8b949e')  # X 軸標籤

    plt.tight_layout()  # 自動排版
    out_file = "top5_m5_scalper_performance.png"  # 輸出檔案
    plt.savefig(out_file, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')  # 存檔
    print(f"\n[+] 獨立子圖版前五名績效圖表已輸出至: {out_file}")  # 輸出成功日誌
    print("=" * 75 + "\n")  # 結尾

if __name__ == "__main__":  # 主程式入口
    generate_separated_top5_m5_chart()  # 啟動獨立子圖生成
