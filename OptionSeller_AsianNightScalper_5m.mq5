//+------------------------------------------------------------------+ // 檔案標頭註解
//|                               OptionSeller_AsianNightScalper_5m.mq5 | // 檔案名稱
//|                                  Copyright 2026, Quant Fund Team | // 版權聲明
//|                           5m 純日內亞洲夜間極限收租剝頭皮量化策略 (EA) | // 策略描述
//+------------------------------------------------------------------+ // 標頭結束
#property copyright "Copyright 2026, Quant Fund Team" // 設定版權屬性
#property link      "https://github.com/evan7646-cloud" // 設定專案連結屬性
#property version   "1.00" // 設定版本號屬性
#property description "5分鐘 (M5) 亞洲夜間高勝率收租策略，每日 UTC 07:00 強制清倉 (Zero-Overnight)" // 策略描述說明

#include <Trade\Trade.mqh> // 導入 MT5 官方交易標準類別庫
#include <Trade\PositionInfo.mqh> // 導入持倉資訊類別庫
#include <Trade\SymbolInfo.mqh> // 導入商品行情資訊類別庫

//--- 策略外部可調參數矩陣 (Inputs)
input group "=== 1. 資金管理與手數配置 ===" // 參數分組 1
input double   InpLotSize             = 2.0;    // 交易下單手數 (固定手數，非馬丁)
input ulong    InpMagicNumber         = 500101; // 策略專屬 Magic Number 識別碼

input group "=== 2. 交易時段與零隔夜風控 (UTC 時間) ===" // 參數分組 2
input int      InpStartHour           = 21;     // 允許進場起始小時 (UTC 21:00 亞盤前夕)
input int      InpEndHour             = 6;      // 允許進場結束小時 (UTC 06:00 歐盤前夕)
input bool     InpForceIntradayClose  = true;   // 是否啟用純日內強制清倉 (零隔夜 Zero-Overnight)
input int      InpForceCloseHour      = 7;      // 強制清倉小時 (UTC 07:00 歐盤開盤前無條件全平)

input group "=== 3. 布林通道 (Bollinger Bands) 參數 ===" // 參數分組 3
input int      InpBBPeriod            = 20;     // 布林通道均線週期 (20 根 5m K 棒)
input double   InpBBDeviation         = 2.2;    // 布林通道標準差倍數 (2.2σ 極限偏離)
input int      InpBBShift             = 0;      // 平移量 (預設 0)

input group "=== 4. RSI 指標參數 ===" // 參數分組 4
input int      InpRSI_Period          = 14;     // RSI 計算週期 (14)
input double   InpRSI_Overbought      = 65.0;   // RSI 超買閾值 (超買確認空頭訊號)
input double   InpRSI_Oversold        = 35.0;   // RSI 超賣閾值 (超賣確認多頭訊號)

input group "=== 5. 止盈與停損點數配置 (Points) ===" // 參數分組 5
input int      InpTakeProfitPoints    = 50;     // 微小止盈點數 (50 Points = 5.0 pips)
input int      InpHardStopPoints      = 350;    // 硬停損點數 (350 Points = 35.0 pips)
input bool     InpExitAtBBMiddle      = true;   // 是否在價格回歸布林中軌時主動止盈離場

//--- 全域全功能物件與變數實例化
CTrade         m_trade;        // 建立交易操作物件
CPositionInfo  m_position;     // 建立持倉資訊查詢物件
CSymbolInfo    m_symbol;       // 建立交易標的行情物件

int            m_handle_bb;    // 布林通道指標控制代碼 Handle
int            m_handle_rsi;   // RSI 指標控制代碼 Handle
datetime       m_last_bar_time;// 記錄最後執行的 K 棒開盤時間 (避免單根 K 線重複觸發)

//+------------------------------------------------------------------+ // 函數分隔
//| Expert initialization function (EA 初始化函數)                    | // 初始化註解
//+------------------------------------------------------------------+ // 分隔線
int OnInit() // 初始化入口
{ // 區塊開始
   m_trade.SetExpertMagicNumber(InpMagicNumber); // 設定交易操作之 Magic Number
   m_trade.SetDeviationInPoints(10); // 設定最大容許滑點點數 (10 Points = 1 pip)
   m_trade.SetTypeFilling(ORDER_FILLING_FOK); // 預設委託成交模式為 FOK (或 IOC)
   
   if(!m_symbol.Name(_Symbol)) // 初始化商品行情資訊物件
   { // 驗證失敗
      Print("[-] 商品資訊初始化失敗: ", _Symbol); // 輸出錯誤日誌
      return(INIT_FAILED); // 中止並回傳失敗狀態
   } // 判斷結束
   
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

   // 1. 純日內強制清倉風控檢查 (Zero-Overnight Check, 每日 UTC 07:00 強制全平)
   MqlDateTime dt_struct; // 宣告時間結構體
   TimeGMT(dt_struct); // 取得當前標準 GMT/UTC 時間
   int current_utc_hour = dt_struct.hour; // 取得當前 UTC 小時

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

   // 檢查當前是否處於允許開倉的夜間時段 (UTC 21:00 ~ 06:00)
   bool is_in_entry_session = false; // 初始化時段旗標
   if(InpStartHour > InpEndHour) // 跨日夜間區間 (如 21:00 ~ 06:00)
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

   // 4. 進場訊號判定與下單執行
   // 做多訊號 (等效賣出 Put 收租)：收盤價 <= 下軌 且 RSI <= 35 (超賣鈍化確認)
   if(close_1 <= lower_1 && rsi_1 <= InpRSI_Oversold) // 符合多單條件
   { // 執行多單下單
      double ask_price = m_symbol.Ask(); // 取得當前最佳買入價 (Ask)
      double sl_price = (InpHardStopPoints > 0) ? ask_price - InpHardStopPoints * _Point : 0; // 計算停損價
      double tp_price = (InpTakeProfitPoints > 0) ? ask_price + InpTakeProfitPoints * _Point : 0; // 計算止盈價
      
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
      double sl_price = (InpHardStopPoints > 0) ? bid_price + InpHardStopPoints * _Point : 0; // 計算停損價
      double tp_price = (InpTakeProfitPoints > 0) ? bid_price - InpTakeProfitPoints * _Point : 0; // 計算止盈價

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
//| 管理當前持倉，執行中軌回歸出場邏輯                               | // 管理持倉註解
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

            if(m_position.PositionType() == POSITION_TYPE_BUY) // 若持有多單
            { // 多單檢查
               if(m_symbol.Bid() >= current_mid) // 當前現價已回歸或超越布林中軌
               { // 執行平倉
                  m_trade.PositionClose(m_position.Ticket()); // 市價平倉多單
                  Print("[+] 多單觸及布林中軌，主動獲利平倉收租! Ticket: ", m_position.Ticket()); // 輸出日誌
               } // 平倉結束
            } // 多單結束
            else if(m_position.PositionType() == POSITION_TYPE_SELL) // 若持有空單
            { // 空單檢查
               if(m_symbol.Ask() <= current_mid) // 當前現價已回歸或跌破布林中軌
               { // 執行平倉
                  m_trade.PositionClose(m_position.Ticket()); // 市價平倉空單
                  Print("[+] 空單觸及布林中軌，主動獲利平倉收租! Ticket: ", m_position.Ticket()); // 輸出日誌
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
            m_trade.PositionClose(m_position.Ticket()); // 市價全平
            Print("[*] 執行強制清倉 [", reason, "] Ticket: ", m_position.Ticket()); // 輸出日誌
         } // 結束
      } // 結束
   } // 遍歷結束
} // CloseAllPositions 結束
