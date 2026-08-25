import os  # 導入作業系統模組
import time  # 導入時間模組
import datetime  # 導入日期時間處理模組
import pandas as pd  # 導入資料表格處理模組
import warnings  # 導入警告控制模組
from tvDatafeed import TvDatafeed, Interval  # 導入 TradingView 數據獲取介面庫

warnings.filterwarnings("ignore")  # 忽略無害警告訊息

# 設定執行環境時區為 UTC
os.environ['TZ'] = 'UTC'  # 設定系統時區環境變數為 UTC
if hasattr(time, 'tzset'):  # 若系統支援時區重設 (macOS / Linux)
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
                print(f"  [!] 第 {attempt} 次嘗試獲取 {exchange}:{symbol} 回傳為空，等待重試...")  # 輸出重試提示
                time.sleep(1.5)  # 等待 1.5 秒再重試
        except Exception as e:  # 捕捉連線中斷或逾時異常
            print(f"  [!] 第 {attempt} 次嘗試失敗 ({exchange}:{symbol}): {e}")  # 輸出錯誤
            time.sleep(2.0)  # 等待 2 秒
    return None  # 若所有重試均失敗則回傳 None

def main():  # 主程式進入點
    print("==========================================================================")  # 分隔線
    print(" 🚀 TradingView (PEPPERSTONE 券商源) 全品種歷史 K 線數據批次下載器")  # 標題
    print("==========================================================================")  # 分隔線
    
    print("\n[1/3] 初始化 TradingView 客戶端連線...")  # 步驟提示
    tv = TvDatafeed()  # 建立 TradingView 匿名連線實例

    # 建立下載資料夾
    output_dir = "data_pepperstone"  # 目標儲存目錄名稱
    os.makedirs(output_dir, exist_ok=True)  # 若目錄不存在則自動建立

    # 定義要從 PEPPERSTONE 券商下載的完整品種清單 (涵蓋 5m 策略核心標的、黃金與美元指數)
    assets = [  # 標的清單
        # 1. 本專案 5m 極限收租 5 大核心外匯貨幣對
        ("AUDCHF", "PEPPERSTONE", "5m 雙策略核心標的 (AUDCHF)"),  # AUDCHF
        ("EURCHF", "PEPPERSTONE", "5m 雙策略核心標的 (EURCHF)"),  # EURCHF
        ("AUDCAD", "PEPPERSTONE", "5m 雙策略核心標的 (AUDCAD)"),  # AUDCAD
        ("USDCHF", "PEPPERSTONE", "5m 雙策略核心標的 (USDCHF)"),  # USDCHF
        ("USDCAD", "PEPPERSTONE", "5m 雙策略核心標的 (USDCAD)"),  # USDCAD
        
        # 2. 黃金與美元指數 (Dollar & Gold)
        ("XAUUSD", "PEPPERSTONE", "現貨黃金 (Spot Gold)"),  # 黃金現貨
        ("USDX",   "PEPPERSTONE", "美元指數 (US Dollar Index)"),  # 美元指數
        
        # 3. 國際主流熱門貨幣對 (Major FX Pairs)
        ("EURUSD", "PEPPERSTONE", "歐元兌美元 (EURUSD)"),  # 歐美
        ("GBPUSD", "PEPPERSTONE", "英鎊兌美元 (GBPUSD)"),  # 鎊美
        ("USDJPY", "PEPPERSTONE", "美元兌日圓 (USDJPY)")   # 美日
    ]  # 清單結束

    # 定義要下載的時間週期 (可同時下載 5 分鐘高頻 K 線與日線)
    timeframes = [  # 週期設定列表
        ("5m", Interval.in_5_minute, 10000),  # 5 分鐘線 (最高 10,000 根 K 棒，供 5m 策略使用)
        ("daily", Interval.in_daily, 5000)    # 日線 (最高 5,000 根 K 棒，供長線趨勢參考)
    ]  # 週期結束

    print(f"\n[2/3] 開始下載 {len(assets)} 個品種之 5m 與 Daily 歷史數據...\n")  # 開始下載提示

    success_count = 0  # 成功計數器
    fail_count = 0  # 失敗計數器

    for symbol, exchange, desc in assets:  # 遍歷各個品種
        print(f"--------------------------------------------------------------------------")  # 標的分割線
        print(f"📊 正在處理: [{symbol}] ({desc}) | 來源券商: {exchange}")  # 顯示處理標的

        for tf_name, tf_interval, n_bars in timeframes:  # 遍歷各個週期
            print(f"  ⏳ 正在下載 {exchange}:{symbol} 的 [{tf_name}] K線資料 (目標: {n_bars} 根)...")  # 下載提示
            
            df = fetch_symbol_with_retry(tv, symbol, exchange, tf_interval, n_bars=n_bars)  # 執行下載
            
            if df is not None and not df.empty:  # 下載成功
                df = df.reset_index()  # 將 index (datetime) 轉為一般欄位
                
                # TradingView 回傳的原始時間為 UTC 時間
                utc_times = pd.to_datetime(df['datetime']).dt.tz_localize(None)  # 轉為純 UTC 格式
                
                # 同時計算出對應的 MT5 伺服器時間 (夏令+3 / 冬令+2) 與台北時間 (UTC+8)
                mt5_times = [t + datetime.timedelta(hours=get_mt5_offset_hours(t)) for t in utc_times]  # 計算 MT5 時間
                tpe_times = [t + datetime.timedelta(hours=8) for t in utc_times]  # 計算台北時間
                
                # 建立結構化欄位
                df_out = pd.DataFrame()  # 建立輸出表格
                df_out['timestamp_mt5'] = [t.strftime('%Y-%m-%d %H:%M:%S') for t in mt5_times]  # MT5 伺服器時間 (首選基準)
                df_out['timestamp_utc'] = [t.strftime('%Y-%m-%d %H:%M:%S') for t in utc_times]  # UTC 時間
                df_out['timestamp_tpe'] = [t.strftime('%Y-%m-%d %H:%M:%S') for t in tpe_times]  # 台北本地時間
                df_out['open'] = df['open']  # 開盤價
                df_out['high'] = df['high']  # 最高價
                df_out['low'] = df['low']  # 最低價
                df_out['close'] = df['close']  # 收盤價
                df_out['volume'] = df['volume']  # 成交量
                
                # 輸出 CSV 檔案至 data_pepperstone 目錄
                filename = f"{exchange.lower()}_{symbol.lower()}_{tf_name}.csv"  # 檔名
                filepath = os.path.join(output_dir, filename)  # 完整檔案路徑
                df_out.to_csv(filepath, index=False, encoding='utf-8')  # 儲存 CSV
                
                print(f"  ✅ 成功！獲取 {len(df_out)} 筆 K線 | 最新時間 (MT5): {df_out['timestamp_mt5'].iloc[-1]} | 已儲存至: {filepath}")  # 輸出成功日誌
                success_count += 1  # 累加成功數
            else:  # 下載失敗
                print(f"  ❌ 失敗！無法獲取 {exchange}:{symbol} 之 [{tf_name}] 資料")  # 輸出失敗提示
                fail_count += 1  # 累加失敗數
            
            time.sleep(0.3)  # 禮貌性微幅延遲避免觸發 TradingView 頻率限制

    print("\n==========================================================================")  # 分隔線
    print(f" 🎉 下載作業全部完成！成功: {success_count} 個檔案，失敗: {fail_count} 個檔案")  # 總結日誌
    print(f" 📁 所有 CSV 檔案均已妥善儲存於: ./{output_dir}/")  # 檔案位置
    print("==========================================================================")  # 分隔線

if __name__ == "__main__":  # 主程式執行判斷
    main()  # 啟動主程式
