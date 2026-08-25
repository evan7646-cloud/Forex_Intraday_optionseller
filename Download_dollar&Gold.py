import os  # 導入作業系統模組
import time  # 導入時間模組
import datetime  # 導入日期時間處理模組
import pandas as pd  # 導入資料表格處理模組
import warnings  # 導入警告控制模組
from tvDatafeed import TvDatafeed, Interval  # 導入 TradingView 數據獲取介面庫

warnings.filterwarnings("ignore")  # 忽略無害警告訊息

os.environ['TZ'] = 'UTC'  # 設定系統時區環境變數為 UTC
if hasattr(time, 'tzset'):  # 若系統支援時區重設
    time.tzset()  # 立即套用 UTC 時區

def get_mt5_offset_hours(dt_utc: datetime.datetime) -> int:  # 計算 MT5 經紀商夏冬令時差 (夏令 UTC+3 / 冬令 UTC+2)
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
    print(" 🚀 TradingView (PEPPERSTONE) 全品種跨週期 (5m, 15m, 1h, Daily) 批次下載器")  # 標題
    print("==========================================================================")  # 分隔線
    
    tv = TvDatafeed()  # 建立 TradingView 連線實例
    output_dir = "data_pepperstone"  # 目標儲存目錄
    os.makedirs(output_dir, exist_ok=True)  # 自動建立資料夾

    # 定義要下載的全部主流標的
    assets = [  # 標的清單
        ("AUDCHF", "PEPPERSTONE", "AUDCHF"),  # AUDCHF
        ("EURCHF", "PEPPERSTONE", "EURCHF"),  # EURCHF
        ("AUDCAD", "PEPPERSTONE", "AUDCAD"),  # AUDCAD
        ("USDCHF", "PEPPERSTONE", "USDCHF"),  # USDCHF
        ("USDCAD", "PEPPERSTONE", "USDCAD"),  # USDCAD
        ("EURUSD", "PEPPERSTONE", "EURUSD"),  # EURUSD
        ("GBPUSD", "PEPPERSTONE", "GBPUSD"),  # GBPUSD
        ("USDJPY", "PEPPERSTONE", "USDJPY"),  # USDJPY
        ("GBPJPY", "PEPPERSTONE", "GBPJPY"),  # GBPJPY
        ("EURJPY", "PEPPERSTONE", "EURJPY"),  # EURJPY
        ("AUDUSD", "PEPPERSTONE", "AUDUSD"),  # AUDUSD
        ("NZDUSD", "PEPPERSTONE", "NZDUSD"),  # NZDUSD
        ("XAUUSD", "PEPPERSTONE", "XAUUSD"),  # 現貨黃金
        ("USDX",   "PEPPERSTONE", "USDX")     # 美元指數
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
            
            # 若檔案已存在且容量 > 10KB 則跳過下載以節省時間
            if os.path.exists(filepath) and os.path.getsize(filepath) > 10240:  # 檢查快取
                print(f"  ⚡ [{tf_name}] 已存在本地快取 ({os.path.getsize(filepath)//1024} KB)，略過下載")  # 略過日誌
                continue  # 跳過
                
            df = fetch_symbol_with_retry(tv, symbol, exchange, tf_interval, n_bars=n_bars)  # 抓取
            if df is not None and not df.empty:  # 成功
                df = df.reset_index()  # 轉一般欄位
                utc_times = pd.to_datetime(df['datetime']).dt.tz_localize(None)  # UTC 時間
                mt5_times = [t + datetime.timedelta(hours=get_mt5_offset_hours(t)) for t in utc_times]  # MT5 時間
                tpe_times = [t + datetime.timedelta(hours=8) for t in utc_times]  # 台北時間
                
                df_out = pd.DataFrame()  # 輸出表
                df_out['timestamp_mt5'] = [t.strftime('%Y-%m-%d %H:%M:%S') for t in mt5_times]  # MT5 時間
                df_out['timestamp_utc'] = [t.strftime('%Y-%m-%d %H:%M:%S') for t in utc_times]  # UTC 時間
                df_out['timestamp_tpe'] = [t.strftime('%Y-%m-%d %H:%M:%S') for t in tpe_times]  # 台北時間
                df_out['open'] = df['open']  # 開盤
                df_out['high'] = df['high']  # 最高
                df_out['low'] = df['low']  # 最低
                df_out['close'] = df['close']  # 收盤
                df_out['volume'] = df['volume']  # 成交量
                
                df_out.to_csv(filepath, index=False, encoding='utf-8')  # 儲存
                print(f"  ✅ [{tf_name}] 成功下載 {len(df_out)} 筆 K 線 -> {filepath}")  # 成功日誌
            else:  # 失敗
                print(f"  ❌ [{tf_name}] 下載失敗")  # 失敗
            time.sleep(0.3)  # 延遲

    print("\n[+] 全部數據下載與更新檢查完畢！")  # 完成

if __name__ == "__main__":  # 主入口
    main()  # 執行
