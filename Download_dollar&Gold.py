import os  # 導入作業系統模組
import time  # 導入時間模組
import datetime  # 導入日期時間處理模組
import pandas as pd  # 導入資料表格處理模組
import warnings  # 導入警告控制模組
from tvDatafeed import TvDatafeed, Interval  # 導入 TradingView 數據獲取介面庫

warnings.filterwarnings("ignore")  # 忽略無害警告訊息

def get_mt5_offset_from_utc(dt_utc: datetime.datetime) -> int:  # 計算 MT5 經紀商夏冬令時差 (夏令 UTC+3 / 冬令 UTC+2)
    year = dt_utc.year  # 取得年份
    mar1 = datetime.datetime(year, 3, 1)  # 3月1日
    second_sun_mar = 1 + (6 - mar1.weekday()) % 7 + 7  # 3月第2個週日
    dst_start = datetime.datetime(year, 3, second_sun_mar, 2, 0, 0)  # 美國夏令開始時間

    nov1 = datetime.datetime(year, 11, 1)  # 11月1日
    first_sun_nov = 1 + (6 - nov1.weekday()) % 7  # 11月第1個週日
    dst_end = datetime.datetime(year, 11, first_sun_nov, 2, 0, 0)  # 美國冬令開始時間

    dt_naive = dt_utc.replace(tzinfo=None) if dt_utc.tzinfo else dt_utc  # 轉為無時區時間進行比較
    if dst_start <= dt_naive < dst_end:  # 若處於夏令時間區間內
        return 3  # 夏令 MT5 伺服器時間為 UTC+3
    else:  # 若處於冬令時間區間內
        return 2  # 冬令 MT5 伺服器時間為 UTC+2

def fetch_symbol_with_retry(tv: TvDatafeed, symbol: str, exchange: str, interval: Interval, n_bars: int = 5000, max_retries: int = 3) -> pd.DataFrame:  # 封裝具備重試機制的 TradingView 下載函數
    for attempt in range(1, max_retries + 1):  # 嘗試最多重試次數
        try:  # 嘗試抓取
            df = tv.get_hist(symbol=symbol, exchange=exchange, interval=interval, n_bars=n_bars)  # 發送 API 請求獲取歷史 K 線
            if df is not None and not df.empty:  # 若成功獲取非空資料
                return df  # 回傳資料表
            else:  # 若回傳為空
                time.sleep(1.0)  # 等待 1 秒
        except Exception as e:  # 捕捉異常
            time.sleep(1.5)  # 等待 1.5 秒
    return None  # 失敗回傳 None

def main():  # 主程式進入點
    print("==========================================================================")  # 分隔線
    print(" 🚀 TradingView (PEPPERSTONE) 全品種精準時區對齊下載器 (台北 UTC+8 -> MT5 UTC+3)")  # 標題
    print("==========================================================================")  # 分隔線
    
    tv = TvDatafeed()  # 建立 TradingView 連線實例
    output_dir = "data_pepperstone"  # 目標儲存目錄
    os.makedirs(output_dir, exist_ok=True)  # 自動建立資料夾

    # 包含 8 大核心及主要外匯標的
    assets = [  # 標的清單
        ("GBPCHF", "PEPPERSTONE", "GBPCHF"),  # GBPCHF
        ("EURGBP", "PEPPERSTONE", "EURGBP"),  # EURGBP
        ("GBPCAD", "PEPPERSTONE", "GBPCAD"),  # GBPCAD
        ("GBPUSD", "PEPPERSTONE", "GBPUSD"),  # GBPUSD
        ("EURAUD", "PEPPERSTONE", "EURAUD"),  # EURAUD
        ("CADCHF", "PEPPERSTONE", "CADCHF"),  # CADCHF
        ("GBPAUD", "PEPPERSTONE", "GBPAUD"),  # GBPAUD
        ("EURCHF", "PEPPERSTONE", "EURCHF"),  # EURCHF
        ("EURUSD", "PEPPERSTONE", "EURUSD"),  # EURUSD
        ("USDCAD", "PEPPERSTONE", "USDCAD"),  # USDCAD
        ("USDCHF", "PEPPERSTONE", "USDCHF"),  # USDCHF
        ("USDJPY", "PEPPERSTONE", "USDJPY"),  # USDJPY
        ("AUDCAD", "PEPPERSTONE", "AUDCAD"),  # AUDCAD
        ("AUDCHF", "PEPPERSTONE", "AUDCHF"),  # AUDCHF
        ("EURCAD", "PEPPERSTONE", "EURCAD")   # EURCAD
    ]  # 標的結束

    # 定義要下載的週期陣列
    timeframes = [  # 週期清單
        ("5m", Interval.in_5_minute, 6000),    # 5 分鐘線
        ("15m", Interval.in_15_minute, 5000),  # 15 分鐘線 (約 3 個月)
        ("1h", Interval.in_1_hour, 5000),      # 1 小時線 (約 10 個月)
        ("daily", Interval.in_daily, 5000)     # 日線 (約 15 年)
    ]  # 週期結束

    for symbol, exchange, desc in assets:  # 遍歷標的
        print(f"\n📊 正在下載 [{symbol}] ({desc}) 各週期數據...")  # 提示
        for tf_name, tf_interval, n_bars in timeframes:  # 遍歷週期
            filename = f"{exchange.lower()}_{symbol.lower()}_{tf_name}.csv"  # 檔名
            filepath = os.path.join(output_dir, filename)  # 完整路徑
            
            df = fetch_symbol_with_retry(tv, symbol, exchange, tf_interval, n_bars=n_bars)  # 抓取
            if df is not None and not df.empty:  # 成功
                df = df.reset_index()  # 轉一般欄位
                # tvDatafeed 回傳的是本機時間 (台北時間 UTC+8)
                tpe_times = pd.to_datetime(df['datetime'])  # 台北時間 (UTC+8)
                utc_times = [t - datetime.timedelta(hours=8) for t in tpe_times]  # 換算標準 UTC (台北-8小時)
                mt5_times = [u + datetime.timedelta(hours=get_mt5_offset_from_utc(u)) for u in utc_times]  # 換算 MT5 (UTC+3 / 台北-5小時)
                
                df_out = pd.DataFrame()  # 輸出表
                df_out['timestamp_mt5'] = [t.strftime('%Y-%m-%d %H:%M:%S') for t in mt5_times]  # MT5 伺服器時間 (UTC+3)
                df_out['timestamp_utc'] = [t.strftime('%Y-%m-%d %H:%M:%S') for t in utc_times]  # UTC 標準時間 (UTC+0)
                df_out['timestamp_tpe'] = [t.strftime('%Y-%m-%d %H:%M:%S') for t in tpe_times]  # 台北本地時間 (UTC+8)
                df_out['open'] = df['open']  # 開盤
                df_out['high'] = df['high']  # 最高
                df_out['low'] = df['low']  # 最低
                df_out['close'] = df['close']  # 收盤
                df_out['volume'] = df['volume']  # 成交量
                
                df_out.to_csv(filepath, index=False, encoding='utf-8')  # 儲存
                print(f"  ✅ [{tf_name}] 成功下載並精準校正時區 {len(df_out)} 筆 K 線 -> 最新 MT5: {df_out['timestamp_mt5'].iloc[-1]} (台北: {df_out['timestamp_tpe'].iloc[-1]})")  # 日誌
            else:  # 失敗
                print(f"  ❌ [{tf_name}] 下載失敗")  # 失敗
            time.sleep(0.2)  # 延遲

    print("\n[+] 全部數據下載與精確時區校正完畢！")  # 完成

if __name__ == "__main__":  # 主入口
    main()  # 執行
