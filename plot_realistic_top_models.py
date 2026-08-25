import os  # 導入作業系統模組
import pandas as pd  # 導入數據分析庫
import numpy as np  # 導入數值計算庫
import matplotlib.pyplot as plt  # 導入繪圖庫
from realistic_multitf_screening import RealisticMultiTFScreeningEngine  # 導入回測引擎

# 設定支援繁體中文的字型
plt.rcParams['font.sans-serif'] = ['Hiragino Sans TC', 'PingFang HK', 'Hiragino Sans GB', 'Arial Unicode MS', 'DejaVu Sans', 'sans-serif']  # 設定中文字型
plt.rcParams['axes.unicode_minus'] = False  # 正常顯示負號

def plot_top6_realistic_models():  # 繪製前 6 大實盤可獲利模型圖表
    engine = RealisticMultiTFScreeningEngine()  # 實例化引擎
    top_picks = [  # 前 6 大配置清單
        ("H1_Swing_Harvest", "GBPAUD", "H4", "1h", "730d", 2.5),  # 第 1 名
        ("H1_Swing_Harvest", "CADJPY", "H4", "1h", "730d", 1.5),  # 第 2 名
        ("H1_Swing_Harvest", "EURJPY", "H4", "1h", "730d", 1.3),  # 第 3 名
        ("H1_Swing_Harvest", "AUDUSD", "H4", "1h", "730d", 1.0),  # 第 4 名
        ("London_NY_TrendBreak", "USDJPY", "M30", "30m", "60d", 0.9),  # 第 5 名
        ("London_NY_TrendBreak", "GBPUSD", "M30", "30m", "60d", 1.0)   # 第 6 名
    ]  # 清單結束

    plt.style.use("dark_background")  # 深色主題
    fig, axes = plt.subplots(3, 2, figsize=(18, 14), sharex=False)  # 3x2 子圖
    fig.patch.set_facecolor("#0d1117")  # 畫布背景色
    axes_flat = axes.flatten()  # 展平
    colors = ["#3fb950", "#58a6ff", "#d2a8ff", "#00e676", "#f0883e", "#79c0ff"]  # 專屬色彩

    for idx, (m_type, sym, tf_name, interval, period, spread) in enumerate(top_picks):  # 遍歷
        ax = axes_flat[idx]  # 取得子圖
        ax.set_facecolor("#161b22")  # 背景色
        df = engine.fetch_data(sym, interval, period)  # 抓取數據
        if tf_name == "H4":  # 若為 H4 進行重採樣
            df = df.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()  # 重採樣
        
        if m_type == "H1_Swing_Harvest":  # 模型 3
            res = engine.run_model_h1_swing_harvest(sym, df, tf_name)  # 回測
        elif m_type == "London_NY_TrendBreak":  # 模型 2
            res = engine.run_model_london_trend(sym, df, tf_name)  # 回測
            
        eq = res["Equity"]  # 權益曲線
        c = colors[idx]  # 顏色
        ax.plot(eq.values, color=c, linewidth=2.4, label=f"{sym} [{tf_name}]")  # 繪線
        ax.fill_between(range(len(eq)), eq.values, 0, color=c, alpha=0.15)  # 漸層填充
        ax.axhline(0, color="#8b949e", linestyle="--", linewidth=1.0, alpha=0.6)  # 0 基準線
        
        m_name = "大波段波動均值回歸 (H4)" if m_type == "H1_Swing_Harvest" else "倫敦/紐約順勢突破 (M30)"  # 中文名稱
        p_val = res["Profit"]  # 純利
        ax.set_title(f"Rank {idx+1}: [{m_name}] {sym} ({tf_name}) - 扣點差實質純利: +${p_val:,.1f} USD", fontsize=12.0, fontweight="bold", color="#f0f6fc")  # 標題
        ax.set_ylabel("實質累積淨利 ($)", fontsize=10.5, color="#8b949e")  # Y 軸
        ax.grid(True, linestyle=":", alpha=0.25, color="#30363d")  # 網格
        
        info = (  # 資訊看板
            f"標的: {sym} ({tf_name})\n"
            f"實盤扣除點差: {spread} pips\n"
            f"勝率: {res['WinRate']}%\n"
            f"獲利因子 (PF): {res['PF']}\n"
            f"總交易筆數: {res['Trades']} 筆\n"
            f"最大回撤 (MDD): {res['MDD']}%\n"
            f"每手手續費: 扣除 $5"
        )
        ax.text(0.03, 0.93, info, transform=ax.transAxes, fontsize=9.5,
                verticalalignment="top", bbox=dict(boxstyle="round,pad=0.5", facecolor="#21262d", edgecolor=c, alpha=0.85), color="#f0f6fc")  # 繪製方塊
        ax.tick_params(colors="#8b949e", labelsize=9)  # 刻度顏色
        ax.set_xlabel("K 線步數", fontsize=9.5, color="#8b949e")  # X 軸

    plt.tight_layout()  # 自動排版
    out_file = "realistic_profitable_top_models.png"  # 檔名
    plt.savefig(out_file, dpi=300, facecolor=fig.get_facecolor(), edgecolor="none")  # 存檔
    print(f"[+] Top 6 實盤獲利圖表已成功輸出至: {out_file}")  # 輸出提示

if __name__ == "__main__":  # 主入口
    plot_top6_realistic_models()  # 啟動繪圖
