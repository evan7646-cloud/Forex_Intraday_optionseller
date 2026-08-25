//+------------------------------------------------------------------+ // 檔案標頭註解
//|                               OptionSeller_AsianNightScalper_5m.mq5 | // 檔案名稱
//|                                  Copyright 2026, Quant Fund Team | // 版權聲明
//|                           5m 純日內亞洲夜間極限收租剝頭皮量化策略 (EA) | // 策略描述
//+------------------------------------------------------------------+ // 標頭結束
#property copyright "Copyright 2026, Quant Fund Team" // 設定版權屬性
#property link      "https://github.com/evan7646-cloud" // 設定專案連結屬性
#property version   "2.20" // 設定版本號屬性 (內建自動日光節約時間 Auto-DST 引擎)
#property description "5分鐘 (M5) 亞洲夜間高勝率收租策略，內建自動 DST 夏冬令時區校準，每日 UTC 07:00 強制清倉" // 策略描述說明

#include <Trade\Trade.mqh> // 導入 MT5 官方交易標準類別庫
#include <Trade\PositionInfo.mqh> // 導入持倉資訊類別庫
#include <Trade\SymbolInfo.mqh> // 導入商品行情資訊類別庫

//--- 策略外部可調參數矩陣 (Inputs)
input group "=== 1. 資金管理與手數配置 ===" // 參數分組 1
input double   InpLotSize             = 1.0;    // 交易下單手數 (固定 1.0 手，符合自營商風控)
input ulong    InpMagicNumber         = 500101; // 策略專屬 Magic Number 識別碼
input int      InpMaxSpreadPoints     = 18;     // 最大容許點差 (18 Points = 1.8 pips，避開夜間換匯擴點)

input group "=== 2. 交易時段與自動夏冬令時區校準 (UTC / MT5 伺服器時間) ===" // 參數分組 2
input bool     InpAutoDST             = true;   // 是否啟用自動夏冬令時區偵測 (Auto-DST，實盤與回測全自動切換)
input int      InpBrokerGMTOffset     = 3;      // 經紀商手動 GMT 偏移 (若關閉 AutoDST 時使用，夏令為 +3，冬令為 +2)
input int      InpStartHour           = 22;     // 允許進場起始小時 (UTC 22:00 = MT5 01:00 亞盤夜間黃金窗口)
input int      InpEndHour             = 5;      // 允許進場結束小時 (UTC 05:00 = MT5 08:00 避開歐盤前夕波動)
input bool     InpForceIntradayClose  = true;   // 是否啟用純日內強制清倉 (零隔夜 Zero-Overnight)
input int      InpForceCloseHour      = 7;      // 強制清倉小時 (UTC 07:00 = MT5 10:00 歐盤開盤前無條件全平)

input group "=== 3. 布林通道 (Bollinger Bands) 參數 ===" // 參數分組 3
input int      InpBBPeriod            = 20;     // 布林通道均線週期 (20 根 5m K 棒)
input double   InpBBDeviation         = 2.2;    // 布林通道標準差倍數 (2.2σ 極限偏離)
input int      InpBBShift             = 0;      // 平移量 (預設 0)

input group "=== 4. RSI 指標參數 ===" // 參數分組 4
input int      InpRSI_Period          = 14;     // RSI 計算週期 (14)
input double   InpRSI_Overbought      = 65.0;   // RSI 超買閾值 (超買確認空頭訊號)
input double   InpRSI_Oversold        = 35.0;   // RSI 超賣閾值 (超賣確認多頭訊號)

input group "=== 5. 止盈與停損點數配置 (Points) ===" // 參數分組 5
input int      InpTakeProfitPoints    = 50;     // 微小止盈點數 (AUDCHF/EURCHF 建議 50, AUDCAD/USDCHF/USDCAD 建議 80)
input int      InpHardStopPoints      = 350;    // 硬停損點數 (建議 350~400 Points)
input bool     InpExitAtBBMiddle      = true;   // 是否在價格回歸布林中軌時主動止盈離場

//--- 全域全功能物件與變數實例化
CTrade         m_trade;        // 建立交易操作物件
CPositionInfo  m_position;     // 建立持倉資訊查詢物件
CSymbolInfo    m_symbol;       // 建立交易標的行情物件

int            m_handle_bb;    // 布林通道指標控制代碼 Handle
int            m_handle_rsi;   // RSI 指標控制代碼 Handle
datetime       m_last_bar_time;// 記錄最後執行的 K 棒開盤時間

//+------------------------------------------------------------------+ // 函數分隔
//| 自動判定經紀商動態 GMT 偏移 (完整支援實盤即時校準與回測美國夏冬令 DST)   | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
int GetDynamicGMTOffset(datetime time_to_check) // 動態 GMT 偏移計算函數
{ // 區塊開始
   if(!InpAutoDST) return InpBrokerGMTOffset; // 若未啟用自動 DST 則回傳手動設定值
   
   // 1. 實盤與模擬即時運作環境：直接比對經紀商 Server Time 與 GMT Time
   if(MQLInfoInteger(MQL_TESTER) == 0 && MQLInfoInteger(MQL_OPTIMIZATION) == 0) // 非測試器環境
   { // 實盤環境
      int diff_hours = (int)MathRound((double)(TimeCurrent() - TimeGMT()) / 3600.0); // 計算即時時差 (夏令為 +3, 冬令為 +2)
      return diff_hours; // 直接回傳即時真實偏移量
   } // 實盤結束
   
   // 2. 歷史回測環境 (Strategy Tester)：依據全球外匯經紀商標準紐約 5 PM 收盤之 US DST 規則自動判定
   MqlDateTime dt; // 宣告時間結構
   TimeToStruct(time_to_check, dt); // 解析歷史時間
   
   if(dt.mon > 3 && dt.mon < 11) return 3; // 4 月 ~ 10 月必然為美國夏令時間 (UTC+3)
   if(dt.mon < 3 || dt.mon > 11) return 2; // 12 月 ~ 2 月必然為美國冬令時間 (UTC+2)
   
   if(dt.mon == 3) // 3 月份 (3 月第 2 個星期日切換為夏令)
   { // 3 月判定
      int first_day_of_week = (dt.day_of_week - (dt.day - 1) % 7 + 7) % 7; // 計算 3/1 星期幾 (0=週日)
      int second_sunday = (first_day_of_week == 0) ? 8 : (15 - first_day_of_week); // 計算第 2 個星期日日期
      if(dt.day > second_sunday || (dt.day == second_sunday && dt.hour >= 2)) return 3; // 進入夏令 (UTC+3)
      return 2; // 尚在冬令 (UTC+2)
   } // 3 月結束
   
   if(dt.mon == 11) // 11 月份 (11 月第 1 個星期日切換為冬令)
   { // 11 月判定
      int first_day_of_week = (dt.day_of_week - (dt.day - 1) % 7 + 7) % 7; // 計算 11/1 星期幾
      int first_sunday = (first_day_of_week == 0) ? 1 : (8 - first_day_of_week); // 計算第 1 個星期日日期
      if(dt.day < first_sunday || (dt.day == first_sunday && dt.hour < 2)) return 3; // 尚在夏令 (UTC+3)
      return 2; // 進入冬令 (UTC+2)
   } // 11 月結束
   
   return 3; // 預設夏令
} // GetDynamicGMTOffset 結束

//+------------------------------------------------------------------+ // 函數分隔
//| Expert initialization function (EA 初始化函數)                    | // 初始化註解
//+------------------------------------------------------------------+ // 分隔線
int OnInit() // 初始化入口
{ // 區塊開始
   m_trade.SetExpertMagicNumber(InpMagicNumber); // 設定交易操作之 Magic Number
   m_trade.SetDeviationInPoints(10); // 設定最大容許滑點點數 (10 Points = 1 pip)
   
   if(!m_symbol.Name(_Symbol)) // 初始化商品行情資訊物件
   { // 驗證失敗
      Print("[-] 商品資訊初始化失敗: ", _Symbol); // 輸出錯誤日誌
      return(INIT_FAILED); // 中止並回傳失敗狀態
   } // 判斷結束
   
   // 自動偵測經紀商支援的委託成交模式，避免 Prop Firm 因 FOK 不支援而拒單
   ENUM_SYMBOL_TRADE_EXECUTION exec_mode = (ENUM_SYMBOL_TRADE_EXECUTION)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_EXEMODE); // 取得經紀商撮合模式
   int filling_mode = (int)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE); // 取得支援的填充模式位掩碼
   if((filling_mode & SYMBOL_FILLING_FOK) != 0) // 若支援 FOK 模式
      m_trade.SetTypeFilling(ORDER_FILLING_FOK); // 使用 FOK 成交
   else if((filling_mode & SYMBOL_FILLING_IOC) != 0) // 若支援 IOC 模式
      m_trade.SetTypeFilling(ORDER_FILLING_IOC); // 使用 IOC 成交
   else // 其餘情況 (Exchange 模式)
      m_trade.SetTypeFilling(ORDER_FILLING_RETURN); // 使用 RETURN 成交
   
   int current_offset = GetDynamicGMTOffset(TimeCurrent()); // 取得當前動態 GMT 偏移
   Print("[*] 偵測到經紀商填充模式: ", EnumToString(exec_mode), " | 當前伺服器 GMT 時差: UTC+", current_offset); // 輸出偵測結果
   
   // 建立 5 分鐘週期 (PERIOD_M5) 的布林通道指標
   m_handle_bb = iBands(_Symbol, PERIOD_M5, InpBBPeriod, InpBBShift, InpBBDeviation, PRICE_CLOSE); // 建立 BB Handle
   if(m_handle_bb == INVALID_HANDLE) // 檢查指標建立是否成功
   { // 若建立失敗
      Print("[-] 建立布林通道指標 Handle 失敗! 錯誤代碼: ", GetLastError()); // 印出錯誤碼
      return(INIT_FAILED); // 回傳初始化失敗
   } // 判斷結束

   // 建立 5 分鐘週期 (PERIOD_M5) 的 RSI 指標
   m_handle_rsi = iRSI(_Symbol, PERIOD_M5, InpRSI_Period, PRICE_CLOSE); // 建立 RSI Handle
   if(m_handle_rsi == INVALID_HANDLE) // 檢查 RSI 建立狀態
   { // 若建立失敗
      Print("[-] 建立 RSI 指標 Handle 失敗! 錯誤代碼: ", GetLastError()); // 印出錯誤碼
      return(INIT_FAILED); // 回傳失敗
   } // 判斷結束

   m_last_bar_time = 0; // 重設最後處理之 K 棒時間
   Print("[+] 5m Asian Night Scalper EA 初始化成功! 週期: M5, 標的: ", _Symbol); // 輸出成功訊息
   return(INIT_SUCCEEDED); // 回傳初始化成功狀態
} // OnInit 結束

//+------------------------------------------------------------------+ // 函數分隔
//| Expert deinitialization function (EA 移除釋放資源函數)            | // 反初始化註解
//+------------------------------------------------------------------+ // 分隔線
void OnDeinit(const int reason) // 移除反初始化入口
{ // 區塊開始
   IndicatorRelease(m_handle_bb); // 釋放布林通道指標佔用記憶體
   IndicatorRelease(m_handle_rsi); // 釋放 RSI 指標佔用記憶體
   Print("[*] EA 已移除，指標資源已全數安全釋放。移除原因代碼: ", reason); // 輸出移除訊息
} // OnDeinit 結束

//+------------------------------------------------------------------+ // 函數分隔
//| Expert tick function (每當有最新報價 Tick 抵達時觸發)              | // Tick 註解
//+------------------------------------------------------------------+ // 分隔線
void OnTick() // 報價觸發主函數
{ // 區塊開始
   if(!m_symbol.RefreshRates()) return; // 刷新最新買賣報價，失敗則跳過

   datetime current_bar_time = iTime(_Symbol, PERIOD_M5, 0); // 取得當前 5m K 棒開盤時間
   bool is_new_bar = (current_bar_time != m_last_bar_time); // 判定是否形成新 5m K 棒

   // 1. 純日內與週五週末強制清倉風控檢查 (透過動態 DST 自動換算標準 UTC 時間)
   datetime current_server_time = TimeCurrent(); // 取得伺服器當前即時/回測時間
   int gmt_offset = GetDynamicGMTOffset(current_server_time); // 動態取得夏令/冬令時差 (+3 或 +2)
   datetime gmt_time = current_server_time - (gmt_offset * 3600); // 扣除動態時區偏移換算為標準 UTC 時間
   MqlDateTime dt_struct; // 宣告時間結構體
   TimeToStruct(gmt_time, dt_struct); // 解析時間結構
   int current_utc_hour = dt_struct.hour; // 取得當前標準 UTC 小時

   // 週五週末防護：週五 (day_of_week == 5) UTC 20:00 後禁止持倉跨週末，徹底規避週末跳空與自營商違規
   if(dt_struct.day_of_week == 5 && current_utc_hour >= 20) // 週五晚間
   { // 執行週末前強制清倉
      CloseAllPositions("Zero-Overnight: 週五週末收市前強制清倉 (避免跨週跳空)"); // 清空部位
      return; // 本輪結束
   } // 判斷結束

   if(InpForceIntradayClose && current_utc_hour == InpForceCloseHour) // 觸達 UTC 07:00 強制清倉時段
   { // 執行清倉
      CloseAllPositions("Zero-Overnight: UTC 07:00 強制清倉"); // 關閉所有持倉避免隔夜與歐盤單邊風險
      return; // 本輪結束
   } // 判斷結束

   // 2. 檢查已開倉部位之出場與中軌止盈邏輯 (每 Tick 實時監控)
   ManageOpenPositions(); // 監控並執行出場判定

   // 3. 進場訊號檢查 (嚴格於「新 5m K 棒形成」時確認上一根 K 棒收盤價與指標)
   if(!is_new_bar) return; // 若非新 K 棒則不重複開倉
   m_last_bar_time = current_bar_time; // 更新最後處理的 K 棒時間

   // 4. 夜間換匯擴點防護 (Rollover Spread Filter)
   long current_spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD); // 取得即時點差 (Points)
   if(InpMaxSpreadPoints > 0 && current_spread > InpMaxSpreadPoints) // 若點差超過容許上限
   { // 點差過大
      Print("[!] 當前點差過大 (", current_spread, " Points > ", InpMaxSpreadPoints, " Points)，跳過開倉以防點差滑價磨損"); // 輸出日誌
      return; // 拒絕開倉
   } // 判斷結束

   // 檢查當前是否處於允許開倉的夜間時段 (UTC 22:00 ~ 05:00)
   bool is_in_entry_session = false; // 初始化時段旗標
   if(InpStartHour > InpEndHour) // 跨日夜間區間 (如 22:00 ~ 05:00)
   { // 跨日計算
      if(current_utc_hour >= InpStartHour || current_utc_hour <= InpEndHour) is_in_entry_session = true; // 符合
   } // 跨日結束
   else // 同日區間
   { // 同日計算
      if(current_utc_hour >= InpStartHour && current_utc_hour <= InpEndHour) is_in_entry_session = true; // 符合
   } // 判斷結束

   if(!is_in_entry_session) return; // 若非開倉時段則不開新單

   // 檢查是否已有本策略的未平倉持倉 (維持單一標的僅持有一單，不加倍加倉)
   if(GetPositionCount() > 0) return; // 已有持倉則等待平倉

   // 取得上一根已收盤的 5m K 棒 (Index 1) 之指標數據與收盤價
   double bb_upper[], bb_middle[], bb_lower[]; // 宣告布林通道緩衝區陣列
   double rsi_val[]; // 宣告 RSI 緩衝區陣列
   
   ArraySetAsSeries(bb_upper, true); // 設定陣列依時間倒序索引
   ArraySetAsSeries(bb_middle, true); // 設定陣列依時間倒序索引
   ArraySetAsSeries(bb_lower, true); // 設定陣列依時間倒序索引
   ArraySetAsSeries(rsi_val, true); // 設定陣列依時間倒序索引

   if(CopyBuffer(m_handle_bb, 0, 1, 2, bb_middle) <= 0) return; // 複製中軌數據
   if(CopyBuffer(m_handle_bb, 1, 1, 2, bb_upper) <= 0) return; // 複製上軌數據
   if(CopyBuffer(m_handle_bb, 2, 1, 2, bb_lower) <= 0) return; // 複製下軌數據
   if(CopyBuffer(m_handle_rsi, 0, 1, 2, rsi_val) <= 0) return; // 複製 RSI 數據

   double close_1 = iClose(_Symbol, PERIOD_M5, 1); // 取得 Index 1 的已收盤價
   double upper_1 = bb_upper[0]; // 上軌數值 (Index 1)
   double lower_1 = bb_lower[0]; // 下軌數值 (Index 1)
   double rsi_1   = rsi_val[0];  // RSI 數值 (Index 1)

   // 5. 進場訊號判定與下單執行
   // 做多訊號 (等效賣出 Put 收租)：收盤價 <= 下軌 且 RSI <= 35 (超賣鈍化確認)
   if(close_1 <= lower_1 && rsi_1 <= InpRSI_Oversold) // 符合多單條件
   { // 執行多單下單
      double ask_price = m_symbol.Ask(); // 取得當前最佳買入價 (Ask)
      double sl_price = (InpHardStopPoints > 0) ? NormalizeDouble(ask_price - InpHardStopPoints * _Point, _Digits) : 0; // 計算停損價並正規化精度
      double tp_price = (InpTakeProfitPoints > 0) ? NormalizeDouble(ask_price + InpTakeProfitPoints * _Point, _Digits) : 0; // 計算止盈價並正規化精度
      
      if(m_trade.Buy(InpLotSize, _Symbol, ask_price, sl_price, tp_price, "Scalper 5m Buy (Short Put)")) // 送出市價買單
      { // 下單成功
         Print("[+] 做多開倉成功! 價格: ", ask_price, " SL: ", sl_price, " TP: ", tp_price); // 輸出日誌
      } // 成功結束
      else // 下單失敗
      { // 輸出失敗資訊
         Print("[-] 做多開倉失敗! 錯誤: ", m_trade.ResultRetcode(), " 說明: ", m_trade.ResultRetcodeDescription()); // 印出錯誤
      } // 失敗結束
   } // 多單結束
   // 做空訊號 (等效賣出 Call 收租)：收盤價 >= 上軌 且 RSI >= 65 (超買鈍化確認)
   else if(close_1 >= upper_1 && rsi_1 >= InpRSI_Overbought) // 符合空單條件
   { // 執行空單下單
      double bid_price = m_symbol.Bid(); // 取得當前最佳賣出價 (Bid)
      double sl_price = (InpHardStopPoints > 0) ? NormalizeDouble(bid_price + InpHardStopPoints * _Point, _Digits) : 0; // 計算停損價並正規化精度
      double tp_price = (InpTakeProfitPoints > 0) ? NormalizeDouble(bid_price - InpTakeProfitPoints * _Point, _Digits) : 0; // 計算止盈價並正規化精度

      if(m_trade.Sell(InpLotSize, _Symbol, bid_price, sl_price, tp_price, "Scalper 5m Sell (Short Call)")) // 送出市價賣單
      { // 下單成功
         Print("[+] 做空開倉成功! 價格: ", bid_price, " SL: ", sl_price, " TP: ", tp_price); // 輸出日誌
      } // 成功結束
      else // 下單失敗
      { // 輸出失敗資訊
         Print("[-] 做空開倉失敗! 錯誤: ", m_trade.ResultRetcode(), " 說明: ", m_trade.ResultRetcodeDescription()); // 印出錯誤
      } // 失敗結束
   } // 空單結束
} // OnTick 結束

//+------------------------------------------------------------------+ // 函數分隔
//| 管理當前持倉，執行中軌回歸出場邏輯 (確認高於成本線方才止盈出場)       | // 管理持倉註解
//+------------------------------------------------------------------+ // 分隔線
void ManageOpenPositions() // 持倉管理函數
{ // 區塊開始
   if(!InpExitAtBBMiddle) return; // 若未開啟中軌出場則返回

   for(int i = PositionsTotal() - 1; i >= 0; i--) // 倒序遍歷所有持倉
   { // 遍歷迴圈
      if(m_position.SelectByIndex(i)) // 選取持倉
      { // 選取成功
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber) // 確認商品與 Magic Number
         { // 符合條件
            double bb_mid[]; // 宣告中軌陣列
            ArraySetAsSeries(bb_mid, true); // 倒序索引
            if(CopyBuffer(m_handle_bb, 0, 0, 1, bb_mid) <= 0) return; // 取得當前中軌最新值
            double current_mid = bb_mid[0]; // 當前中軌價
            double open_price = m_position.PriceOpen(); // 取得進場成本價

            if(m_position.PositionType() == POSITION_TYPE_BUY) // 若持有多單
            { // 多單檢查
               // 多單要求：現價觸碰或超過中軌 且 現價高於進場成本 (確保是獲利收租，非逆向提前認賠)
               if(m_symbol.Bid() >= current_mid && m_symbol.Bid() > open_price) // 符合中軌獲利收租
               { // 執行平倉
                  if(!m_trade.PositionClose(m_position.Ticket())) // 市價平倉多單，檢查返回值
                     Print("[!] 多單中軌止盈平倉失敗，將在下一 Tick 重試! Err: ", m_trade.ResultRetcode()); // 失敗則記錄待重試
                  else // 平倉成功
                     Print("[+] 多單觸及布林中軌且處於獲利狀態，主動獲利平倉收租! Ticket: ", m_position.Ticket()); // 輸出日誌
               } // 平倉結束
            } // 多單結束
            else if(m_position.PositionType() == POSITION_TYPE_SELL) // 若持有空單
            { // 空單檢查
               // 空單要求：現價觸碰或跌破中軌 且 現價低於進場成本 (確保是獲利收租，非逆向提前認賠)
               if(m_symbol.Ask() <= current_mid && m_symbol.Ask() < open_price) // 符合中軌獲利收租
               { // 執行平倉
                  if(!m_trade.PositionClose(m_position.Ticket())) // 市價平倉空單，檢查返回值
                     Print("[!] 空單中軌止盈平倉失敗，將在下一 Tick 重試! Err: ", m_trade.ResultRetcode()); // 失敗則記錄待重試
                  else // 平倉成功
                     Print("[+] 空單觸及布林中軌且處於獲利狀態，主動獲利平倉收租! Ticket: ", m_position.Ticket()); // 輸出日誌
               } // 平倉結束
            } // 空單結束
         } // 符合結束
      } // 選取結束
   } // 遍歷結束
} // ManageOpenPositions 結束

//+------------------------------------------------------------------+ // 函數分隔
//| 取得本策略當前未平倉訂單數量                                     | // 統計持倉註解
//+------------------------------------------------------------------+ // 分隔線
int GetPositionCount() // 持倉統計函數
{ // 區塊開始
   int count = 0; // 初始化計數
   for(int i = PositionsTotal() - 1; i >= 0; i--) // 遍歷持倉
   { // 迴圈
      if(m_position.SelectByIndex(i)) // 選取
      { // 成功
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber) // 匹配商品與 Magic
         { // 匹配
            count++; // 計數加 1
         } // 結束
      } // 結束
   } // 遍歷結束
   return(count); // 回傳總數
} // GetPositionCount 結束

//+------------------------------------------------------------------+ // 函數分隔
//| 清倉本策略所有部位 (Zero-Overnight 強制平倉)                      | // 全平倉註解
//+------------------------------------------------------------------+ // 分隔線
void CloseAllPositions(string reason) // 全平倉函數
{ // 區塊開始
   for(int i = PositionsTotal() - 1; i >= 0; i--) // 倒序遍歷
   { // 迴圈
      if(m_position.SelectByIndex(i)) // 選取
      { // 成功
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber) // 匹配
         { // 執行平倉
            ulong ticket = m_position.Ticket(); // 先暫存 Ticket 避免迴圈中物件狀態變更
            if(!m_trade.PositionClose(ticket)) // 檢查平倉是否成功
            { // 平倉失敗
               Print("[!] 強制清倉失敗 [", reason, "] Ticket: ", ticket, " Err: ", m_trade.ResultRetcode(), " 將在下一 Tick 重試"); // 記錄失敗日誌
            } // 失敗結束
            else // 平倉成功
            { // 成功
               Print("[*] 執行強制清倉成功 [", reason, "] Ticket: ", ticket); // 輸出成功日誌
            } // 成功結束
         } // 結束
      } // 結束
   } // 結束
} // CloseAllPositions 結束
