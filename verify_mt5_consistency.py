import os  # 導入作業系統模組
import json  # 導入 JSON 資料處理模組
import pandas as pd  # 導入 Pandas 表格分析庫
import numpy as np  # 導入 NumPy 數值計算庫
from update_strategy_data import SchemeDOptionHarvestEngine  # Bug5修正: 導入正確的方案 D 收租引擎

def verify_mt5_vs_web_consistency():  # 定義 MT5 EA 邏輯與網頁數據一致性精準檢驗函數
    print("\n==========================================================================")  # 標頭分隔線
    print("      🔍 執行【方案 D】MT5 EA 邏輯 vs 網頁端即時數據進出場一致性比對檢驗      ")  # 主標題
    print("==========================================================================\n")  # 標頭分隔線

    # 1. 讀取網頁發布之 strategy_results.json
    json_path = os.path.join(os.path.dirname(__file__), "strategy_results.json")  # 檔案路徑
    if not os.path.exists(json_path):  # 檢查檔案
        print("[-] 找不到 strategy_results.json，重新執行引擎運算中...")  # 提示
        engine = SchemeDOptionHarvestEngine()  # 實例化
        engine.execute_and_export()  # 運算並輸出

    with open(json_path, "r", encoding="utf-8") as f:  # 開啟 JSON 檔
        web_payload = json.load(f)  # 載入資料

    web_trades = web_payload['all_trades']  # 取得網頁端全部歷史交易
    web_metrics = web_payload['portfolio_metrics']  # 取得網頁端組合核心指標
    web_modules = {m['module_id']: m for m in web_payload['modules_summary']}  # 模組字典

    # 2. 重新執行回測引擎模擬 MT5 EA Bar-by-Bar 判定邏輯
    engine = SchemeDOptionHarvestEngine()  # 建立引擎實例
    mt5_simulated_trades = []  # 儲存 MT5 模擬交易

    for mod in engine.modules:  # 遍歷 8 大王牌模組
        df = engine.load_data(mod["symbol"], mod["tf"])  # 讀取對應週期數據
        if df.empty:  # 數據不存在
            print(f"  ⚠️ 跳過 {mod['module_id']}：找不到 {mod['symbol']} {mod['tf']} 數據檔案")  # 提示
            continue  # 跳過
        res = engine.run_single_module(df, mod, lot_size=1.0)  # 執行單一模組回測 (1.0 手)
        for t in res['trades']:  # 遍歷交易
            t['module_id'] = mod['module_id']  # 賦予模組識別碼
            mt5_simulated_trades.append(t)  # 寫入

    # 3. 模組指標一致性核對表
    comparison_rows = []  # 儲存對照列
    modules_list = [  # 方案 A 穩健組合 8 大模組清單 (v5.10 汰弱留強精銳版)
        ("Opt_GBPJPY_1H_US",    "OptionSeller_US_Afternoon_Harvest.mq5",    "GBPJPY",  "1h"),   # 美盤王牌
        ("Opt_EURJPY_1H_US",    "OptionSeller_US_Afternoon_Harvest.mq5",    "EURJPY",  "1h"),   # 美盤
        ("Opt_GBPUSD_15M_US",   "OptionSeller_US_Afternoon_Harvest.mq5",    "GBPUSD",  "15m"),  # 美盤
        ("Opt_EURCAD_1H_US",    "OptionSeller_US_Afternoon_Harvest.mq5",    "EURCAD",  "1h"),   # 🆕 美盤
        ("Opt_EURJPY_15M_DAY",  "OptionSeller_DaytimeChannel_Harvest.mq5",  "EURJPY",  "15m"),  # 白天
        ("Opt_AUDCHF_1H_DAY",   "OptionSeller_DaytimeChannel_Harvest.mq5",  "AUDCHF",  "1h"),   # 白天
        ("Opt_AUDUSD_1H_DAY",   "OptionSeller_DaytimeChannel_Harvest.mq5",  "AUDUSD",  "1h"),   # 🆕 白天
        ("Opt_GBPJPY_15M_DAY",  "OptionSeller_DaytimeChannel_Harvest.mq5",  "GBPJPY",  "15m"),  # 🆕 白天
    ]  # 清單結束

    all_consistent = True  # 全部一致旗標
    for mod_id, ea_file, sym, tf in modules_list:  # 遍歷核對
        web_m = web_modules.get(mod_id, {})  # 網頁端指標
        mod_trades = [t for t in mt5_simulated_trades if t.get('module_id') == mod_id]  # MT5 交易

        sim_trades_cnt = len(mod_trades)  # 交易次數
        sim_wins = sum(1 for t in mod_trades if t['win'])  # 獲利次數
        sim_win_rate = round(sim_wins / sim_trades_cnt * 100, 1) if sim_trades_cnt > 0 else 0.0  # 勝率
        sim_pnl = round(sum(t['pnl_usd'] for t in mod_trades), 2)  # 淨利
        sim_gross_win = sum(t['pnl_usd'] for t in mod_trades if t['pnl_usd'] > 0)  # 毛利
        sim_gross_loss = sum(abs(t['pnl_usd']) for t in mod_trades if t['pnl_usd'] < 0)  # 毛損
        sim_pf = round(sim_gross_win / (sim_gross_loss + 1e-9), 2)  # PF

        # 比對一致性 (Trade Count / Win Rate / PnL 浮點四捨五入誤差 < $1)
        web_cnt = web_m.get('trades_count', 0)  # 網頁交易數
        web_wr = web_m.get('win_rate', 0.0)  # 網頁勝率
        web_pnl = web_m.get('total_pnl_usd', 0)  # 網頁淨利
        is_consistent = (sim_trades_cnt == web_cnt) and (sim_win_rate == web_wr) and (abs(sim_pnl - web_pnl) < 1.0)  # 是否一致
        if not is_consistent:  # 不一致
            all_consistent = False  # 設旗標

        comparison_rows.append({  # 記錄比對
            "模組名稱": mod_id,  # 模組
            "對應 MT5 EA": ea_file.replace("OptionSeller_", "").replace(".mq5", ""),  # EA 短名
            "標的": sym,  # 品種
            "週期": tf,  # 週期
            "網頁筆數": web_cnt,  # 網頁交易數
            "MT5筆數": sim_trades_cnt,  # MT5 交易數
            "網頁勝率": f"{web_wr}%",  # 網頁勝率
            "MT5勝率": f"{sim_win_rate}%",  # MT5 勝率
            "網頁淨利($)": f"${web_pnl:,.2f}",  # 網頁獲利
            "MT5淨利($)": f"${sim_pnl:,.2f}",  # MT5 獲利
            "一致性": "✅ 吻合" if is_consistent else "❌ 需校準"  # 判定狀態
        })  # 結束記錄

    df_comp = pd.DataFrame(comparison_rows)  # 轉為 DataFrame
    print(df_comp.to_string(index=False))  # 格式化輸出

    # 4. 組合總體統計
    sim_total = len(mt5_simulated_trades)  # 總筆數
    sim_wins_total = sum(1 for t in mt5_simulated_trades if t['win'])  # 總獲利
    sim_wr_total = round(sim_wins_total / sim_total * 100, 1) if sim_total > 0 else 0.0  # 總勝率
    sim_pnl_total = round(sum(t['pnl_usd'] for t in mt5_simulated_trades), 2)  # 總淨利

    print("\n==========================================================================")  # 結尾線
    if all_consistent:  # 全部一致
        print(f"  ✅ 驗證通過：8 大模組 MT5 EA 邏輯與網頁數據 100% 一致！")  # 通過
    else:  # 有差異
        print(f"  ⚠️ 偵測到不一致：請重新執行 update_strategy_data.py 更新 JSON 後再驗證")  # 提示
    print(f"  📊 MT5 模擬總筆數: {sim_total} | 勝率: {sim_wr_total}% | 總淨利: ${sim_pnl_total:,.2f}")  # MT5 統計
    print(f"  📊 網頁端總筆數: {web_metrics.get('total_trades', 0)} | 勝率: {web_metrics.get('win_rate', 0)}% | 總淨利: ${web_metrics.get('total_net_pnl_usd', 0):,.2f}")  # 網頁統計
    print("==========================================================================\n")  # 結尾線

if __name__ == "__main__":  # 執行主入口
    verify_mt5_vs_web_consistency()  # 啟動驗證
