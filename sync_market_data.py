import os  # 導入作業系統模組以處理檔案路徑
import datetime  # 導入日期時間處理模組
import pandas as pd  # 導入資料表格處理模組
import yfinance as yf  # 導入 Yahoo Finance 介面庫

def get_mt5_offset_from_utc(dt_utc: datetime.datetime) -> int:  # 計算 MT5 經紀商夏冬令時差 (夏令 UTC+3 / 冬令 UTC+2)
    year = dt_utc.year  # 取得年份
    mar1 = datetime.datetime(year, 3, 1)  # 3月1日基準
    second_sun_mar = 1 + (6 - mar1.weekday()) % 7 + 7  # 計算 3 月第 2 個週日
    dst_start = datetime.datetime(year, 3, second_sun_mar, 2, 0, 0)  # 美國夏令開始時間
    nov1 = datetime.datetime(year, 11, 1)  # 11月1日基準
    first_sun_nov = 1 + (6 - nov1.weekday()) % 7  # 計算 11 月第 1 個週日
    dst_end = datetime.datetime(year, 11, first_sun_nov, 2, 0, 0)  # 美國冬令開始時間
    dt_naive = dt_utc.replace(tzinfo=None) if dt_utc.tzinfo else dt_utc  # 轉為無時區時間進行判斷
    if dst_start <= dt_naive < dst_end:  # 若處於夏令時間區間內
        return 3  # 夏令 MT5 伺服器時間為 UTC+3
    else:  # 若處於冬令時間區間內
        return 2  # 冬令 MT5 伺服器時間為 UTC+2

def update_single_pair(symbol: str, tf_name: str, yf_interval: str, yf_period: str, output_dir: str):  # 下載並合併單一商品週期數據
    filename = f"pepperstone_{symbol.lower()}_{tf_name}.csv"  # 目標 CSV 檔名
    filepath = os.path.join(output_dir, filename)  # 完整 CSV 檔案路徑
    
    yf_symbol = f"{symbol}=X"  # Yahoo Finance 外匯代碼格式
    if symbol == "XAUUSD":  # 黃金代碼
        yf_symbol = "GC=F"  # 黃金期貨/現貨
    elif symbol == "USDX":  # 美元指數代碼
        yf_symbol = "DX-Y.NYB"  # 美元指數
        
    try:  # 嘗試下載與合併
        ticker = yf.Ticker(yf_symbol)  # 建立 Ticker 實例
        df_yf = ticker.history(period=yf_period, interval=yf_interval)  # 獲取最新行情
        if df_yf is None or df_yf.empty:  # 若無數據
            print(f"⚠️ {symbol} {tf_name}: 無法從 Yahoo Finance 獲取數據")  # 印出提示
            return  # 結束
            
        df_yf = df_yf.reset_index()  # 重設索引
        time_col = "Datetime" if "Datetime" in df_yf.columns else "Date"  # 識別時間欄位名稱
        df_yf["dt_utc"] = pd.to_datetime(df_yf[time_col]).dt.tz_convert("UTC")  # 轉換為標準 UTC 時間
        
        digits = 3 if "JPY" in symbol else 5  # 設定適當小數位數
        df_new = pd.DataFrame()  # 建立標準格式新資料表
        df_new["timestamp_mt5"] = df_yf["dt_utc"].apply(lambda u: (u + datetime.timedelta(hours=get_mt5_offset_from_utc(u))).strftime("%Y-%m-%d %H:%M:%S"))  # MT5 伺服器時間
        df_new["timestamp_utc"] = df_yf["dt_utc"].dt.strftime("%Y-%m-%d %H:%M:%S")  # UTC 標準時間
        df_new["timestamp_tpe"] = df_yf["dt_utc"].apply(lambda u: (u + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"))  # 台北本地時間
        df_new["open"] = df_yf["Open"].round(digits)  # 開盤價
        df_new["high"] = df_yf["High"].round(digits)  # 最高價
        df_new["low"] = df_yf["Low"].round(digits)  # 最低價
        df_new["close"] = df_yf["Close"].round(digits)  # 收盤價
        df_new["volume"] = df_yf["Volume"].fillna(0.0)  # 成交量
        
        if os.path.exists(filepath):  # 若原 CSV 檔案存在
            df_old = pd.read_csv(filepath)  # 讀取原有歷史資料
            # 合併新舊資料並依 MT5 時間去重
            df_combined = pd.concat([df_old, df_new], ignore_index=True)  # 上下拼接
            df_combined = df_combined.drop_duplicates(subset=["timestamp_mt5"], keep="last")  # 遇重複保留最新
            df_combined = df_combined.sort_values(by="timestamp_mt5").reset_index(drop=True)  # 依時間升序排列
        else:  # 若檔案不存在
            df_combined = df_new.sort_values(by="timestamp_mt5").reset_index(drop=True)  # 直接使用新資料
            
        df_combined.to_csv(filepath, index=False)  # 寫入 CSV 檔案
        print(f"✅ 成功更新 {symbol} ({tf_name}): 最新時間 {df_combined['timestamp_mt5'].iloc[-1]} (共 {len(df_combined)} 筆)")  # 提示成功
        
    except Exception as e:  # 捕捉異常
        print(f"❌ 更新 {symbol} {tf_name} 失敗: {e}")  # 印出錯誤

def main():  # 主程式進入點
    print("==========================================================================")  # 分隔線
    print(" 🚀 啟動 Yahoo Finance 行情即時同步器 (對齊 Pepperstone MT5 UTC+3)")  # 標題
    print("==========================================================================")  # 分隔線
    
    data_dir = os.path.join(os.path.dirname(__file__), "data_pepperstone")  # 資料夾路徑
    os.makedirs(data_dir, exist_ok=True)  # 建立資料夾
    
    # 核心 8 大模組及熱門貨幣對清單
    symbols = [  # 商品陣列
        "GBPJPY", "EURJPY", "GBPUSD", "EURCAD", "AUDCHF", "AUDUSD",  # 方案 D 8 大王牌模組標的
        "EURUSD", "USDJPY", "USDCAD", "USDCHF", "EURGBP", "EURAUD",  # 其他熱門直盤與交叉盤
        "GBPCHF", "GBPAUD", "GBPCAD", "AUDCAD", "AUDNZD", "CADCHF",  # 其他主要交叉盤
        "CADJPY", "CHFJPY", "AUDJPY", "NZDJPY", "NZDUSD", "NZDCHF",  # 日圓交叉盤與紐幣盤
        "NZDCAD", "EURNZD", "GBPNZD"  # 紐幣相關交叉盤
    ]  # 清單結束
    
    configs = [  # 週期設定清單
        ("1h", "1h", "60d"),   # 1 小時線 (獲取近 60 天)
        ("15m", "15m", "30d"), # 15 分鐘線 (獲取近 30 天)
        ("5m", "5m", "10d")    # 5 分鐘線 (獲取近 10 天)
    ]  # 設定結束
    
    for sym in symbols:  # 遍歷所有貨幣對
        for tf_name, yf_interval, yf_period in configs:  # 遍歷週期
            update_single_pair(sym, tf_name, yf_interval, yf_period, data_dir)  # 執行更新

if __name__ == "__main__":  # 主程式判斷
    main()  # 執行主程式
