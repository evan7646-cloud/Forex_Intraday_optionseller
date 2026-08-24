//+------------------------------------------------------------------+ // 檔案標頭註解
//|                        OptionSeller_SyntheticShortStraddle_5m.mq5 | // 檔案名稱
//|                                  Copyright 2026, Quant Fund Team | // 版權聲明
//|                    5m 純日內合成選擇權跨式賣方量化收租策略 (EA) | // 策略描述
//+------------------------------------------------------------------+ // 標頭結束
#property copyright "Copyright 2026, Quant Fund Team" // 設定版權資訊
#property link      "https://github.com/evan7646-cloud" // 設定專案連結
#property version   "1.00" // 設定版本號
#property description "5分鐘 (M5) 合成跨式賣方模型 (Short Straddle)，滾動 Z-Score 均值回歸，每日 UTC 21:00 強制清倉" // 策略功能簡介

#include <Trade\Trade.mqh> // 導入 MT5 官方交易類別庫
#include <Trade\PositionInfo.mqh> // 導入持倉查詢類別庫
#include <Trade\SymbolInfo.mqh> // 導入商品行情類別庫

//--- 策略外部可調參數矩陣 (Inputs)
input group "=== 1. 資金管理與手數配置 ===" // 參數分組 1
input double   InpLotSize             = 1.0;    // 交易下單手數 (固定 1.0 手，符合自營商風控)
input ulong    InpMagicNumber         = 500201; // 策略專屬 Magic Number 識別碼

input group "=== 2. 交易時段與零隔夜風控 (UTC 時間) ===" // 參數分組 2
input int      InpStartHour           = 7;      // 允許進場起始小時 (UTC 07:00 歐盤開盤)
input int      InpEndHour             = 20;     // 允許進場結束小時 (UTC 20:00 美盤尾聲)
input bool     InpForceIntradayClose  = true;   // 是否啟用純日內強制清倉 (零隔夜 Zero-Overnight)
input int      InpForceCloseHour      = 21;     // 強制清倉小時 (UTC 21:00 美盤收市前夕市價清空)

input group "=== 3. 滾動 Z-Score 統計模型參數 ===" // 參數分組 3
input int      InpLookbackPeriod      = 30;     // 滾動回看週期 (30 根 5m K 棒)
input double   InpZScoreEntry         = 2.1;    // 進場偏離閾值 (±2.1σ 賣出 OTM 兩翼收取權利金)
input double   InpZScoreExit          = 0.2;    // 均值回歸止盈閾值 (|Z| <= 0.2σ 收斂平倉落袋)
input double   InpZScoreHardStop      = 3.8;    // 極端偏離止損閾值 (|Z| >= 3.8σ 硬停損截斷單邊風險)

input group "=== 4. 點數止盈與停損備援配置 (Points) ===" // 參數分組 4
input int      InpTakeProfitPoints    = 50;     // 微小止盈點數 (50 Points = 5.0 pips)
input int      InpHardStopPoints      = 350;    // 硬停損點數 (350 Points = 35.0 pips)

//--- 全域物件與變數實例化
CTrade         m_trade;        // 建立交易操作物件
CPositionInfo  m_position;     // 建立持倉資訊物件
CSymbolInfo    m_symbol;       // 建立行情資訊物件

int            m_handle_ma;    // 30 週期 SMA 均值指標控制代碼 Handle
int            m_handle_std;   // 30 週期標準差指標控制代碼 Handle
datetime       m_last_bar_time;// 記錄最後執行的 K 棒開盤時間

//+------------------------------------------------------------------+ // 函數分隔
//| Expert initialization function (EA 初始化函數)                    | // 初始化註解
//+------------------------------------------------------------------+ // 分隔線
int OnInit() // 初始化入口
{ // 區塊開始
   m_trade.SetExpertMagicNumber(InpMagicNumber); // 設定 Magic Number
   m_trade.SetDeviationInPoints(10); // 設定最大容許滑點點數 (10 Points)
   
   if(!m_symbol.Name(_Symbol)) // 初始化商品物件
   { // 失敗
      Print("[-] 商品資訊初始化失敗: ", _Symbol); // 印出錯誤
      return(INIT_FAILED); // 返回失敗
   } // 結束
   
   // [修復] 自動偵測經紀商支援的委託成交模式，避免 Prop Firm 因 FOK 不支援而 100% 拒單
   ENUM_SYMBOL_TRADE_EXECUTION exec_mode = (ENUM_SYMBOL_TRADE_EXECUTION)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_EXEMODE); // 取得經紀商撮合模式
   int filling_mode = (int)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE); // 取得支援的填充模式位掩碼
   if((filling_mode & SYMBOL_FILLING_FOK) != 0) // 若支援 FOK 模式
      m_trade.SetTypeFilling(ORDER_FILLING_FOK); // 使用 FOK 成交
   else if((filling_mode & SYMBOL_FILLING_IOC) != 0) // 若支援 IOC 模式
      m_trade.SetTypeFilling(ORDER_FILLING_IOC); // 使用 IOC 成交
   else // 其餘情況 (Exchange 模式)
      m_trade.SetTypeFilling(ORDER_FILLING_RETURN); // 使用 RETURN 成交
   Print("[*] 偵測到經紀商填充模式: ", EnumToString(exec_mode), " -> 使用: ", filling_mode); // 輸出偵測結果
   
   // 建立 5 分鐘週期 (PERIOD_M5) 的 30 週期移動平均線 (SMA) 指標 Handle
   m_handle_ma = iMA(_Symbol, PERIOD_M5, InpLookbackPeriod, 0, MODE_SMA, PRICE_CLOSE); // 建立 MA Handle
   if(m_handle_ma == INVALID_HANDLE) // 檢查 Handle
   { // 失敗
      Print("[-] 建立 SMA 指標 Handle 失敗! 錯誤代碼: ", GetLastError()); // 印出錯誤
      return(INIT_FAILED); // 返回失敗
   } // 結束

   // 建立 5 分鐘週期 (PERIOD_M5) 的 30 週期標準差 (Standard Deviation) 指標 Handle
   m_handle_std = iStdDev(_Symbol, PERIOD_M5, InpLookbackPeriod, 0, MODE_SMA, PRICE_CLOSE); // 建立 StdDev Handle
   if(m_handle_std == INVALID_HANDLE) // 檢查 Handle
   { // 失敗
      Print("[-] 建立 StdDev 指標 Handle 失敗! 錯誤代碼: ", GetLastError()); // 印出錯誤
      return(INIT_FAILED); // 返回失敗
   } // 結束

   m_last_bar_time = 0; // 重設時間戳
   Print("[+] 5m Synthetic Short Straddle EA 初始化成功! 週期: M5, 標的: ", _Symbol); // 輸出成功訊息
   return(INIT_SUCCEEDED); // 返回成功
} // OnInit 結束

//+------------------------------------------------------------------+ // 函數分隔
//| Expert deinitialization function (EA 釋放資源函數)                | // 反初始化註解
//+------------------------------------------------------------------+ // 分隔線
void OnDeinit(const int reason) // 反初始化入口
{ // 區塊開始
   IndicatorRelease(m_handle_ma); // 釋放均線指標記憶體
   IndicatorRelease(m_handle_std); // 釋放標準差指標記憶體
   Print("[*] EA 已移除，跨式賣方指標資源已釋放。原因代碼: ", reason); // 輸出訊息
} // OnDeinit 結束

//+------------------------------------------------------------------+ // 函數分隔
//| 計算當前或指定 K 棒之動態波動偏離度 Z-Score                        | // 計算 Z-Score 註解
//+------------------------------------------------------------------+ // 分隔線
double CalculateZScore(int bar_index) // Z-Score 計算函數
{ // 區塊開始
   double ma_arr[], std_arr[]; // 宣告緩衝陣列
   ArraySetAsSeries(ma_arr, true); // 倒序索引
   ArraySetAsSeries(std_arr, true); // 倒序索引

   if(CopyBuffer(m_handle_ma, 0, bar_index, 1, ma_arr) <= 0) return(0.0); // 複製 MA 數值
   if(CopyBuffer(m_handle_std, 0, bar_index, 1, std_arr) <= 0) return(0.0); // 複製 Std 數值

   double close_p = iClose(_Symbol, PERIOD_M5, bar_index); // 取得指定 K 棒收盤價
   double ma_val  = ma_arr[0]; // 均值 μ
   double std_val = std_arr[0]; // 標準差 σ

   if(std_val <= 1e-9) return(0.0); // 避免除以零
   return((close_p - ma_val) / std_val); // 回傳動態 Z-Score: (P - μ) / σ
} // CalculateZScore 結束

//+------------------------------------------------------------------+ // 函數分隔
//| Expert tick function (每當有最新報價 Tick 抵達時觸發)              | // Tick 註解
//+------------------------------------------------------------------+ // 分隔線
void OnTick() // 報價主函數
{ // 區塊開始
   if(!m_symbol.RefreshRates()) return; // 刷新報價

   datetime current_bar_time = iTime(_Symbol, PERIOD_M5, 0); // 取得當前 5m K 棒時間
   bool is_new_bar = (current_bar_time != m_last_bar_time); // 判定是否為新 K 棒

   // 1. 純日內強制清倉風控 (Zero-Overnight Check, 每日 UTC 21:00 美盤尾聲全平)
   MqlDateTime dt_struct; // 宣告時間結構
   TimeGMT(dt_struct); // 取得 GMT/UTC 時間
   int current_utc_hour = dt_struct.hour; // 當前 UTC 小時

   if(InpForceIntradayClose && current_utc_hour == InpForceCloseHour) // 觸達 UTC 21:00
   { // 執行清倉
      CloseAllPositions("Zero-Overnight: UTC 21:00 強制清倉"); // 清空所有跨式部位確保 Swap 支出為 $0.00
      return; // 本輪結束
   } // 判斷結束

   // 2. 實時管理持倉 (每 Tick 監控 Z-Score 均值回歸與極端停損)
   ManageOpenPositions(); // 執行出場判定

   // 3. 進場訊號檢查 (新 5m K 棒形成時判定 Index 1)
   if(!is_new_bar) return; // 非新 K 棒跳過
   m_last_bar_time = current_bar_time; // 更新時間戳

   // 檢查開倉時段 (UTC 07:00 ~ 20:00)
   bool is_in_entry_session = (current_utc_hour >= InpStartHour && current_utc_hour <= InpEndHour); // 判定
   if(!is_in_entry_session) return; // 非開倉時段返回

   // 檢查是否有未平倉持倉 (維持單一標的單一單)
   if(GetPositionCount() > 0) return; // 已有部位則不重複開倉

   // 取得上一根已收盤 5m K 棒 (Index 1) 之 Z-Score
   double z_score_1 = CalculateZScore(1); // 計算 Index 1 的 Z-Score

   // 4. 進出場訊號規則
   // 賣出跨式左翼做多 (Short OTM Put 側買多)：Z <= -2.1σ
   if(z_score_1 <= -InpZScoreEntry) // 符合賣 Put 多單條件
   { // 執行買入
       double ask_price = m_symbol.Ask(); // 買入價
       double sl_price = (InpHardStopPoints > 0) ? NormalizeDouble(ask_price - InpHardStopPoints * _Point, _Digits) : 0; // [修復] 停損價正規化精度
       double tp_price = (InpTakeProfitPoints > 0) ? NormalizeDouble(ask_price + InpTakeProfitPoints * _Point, _Digits) : 0; // [修復] 止盈價正規化精度

      if(m_trade.Buy(InpLotSize, _Symbol, ask_price, sl_price, tp_price, "Short Straddle Buy (Short Put Wing)")) // 送出買單
      { // 成功
         Print("[+] 跨式左翼做多開倉成功! Z-Score: ", DoubleToString(z_score_1, 2), " 價格: ", ask_price); // 印出訊息
      } // 結束
      else // 失敗
      { // 輸出失敗
         Print("[-] 做多開倉失敗! 錯誤: ", m_trade.ResultRetcode(), " 說明: ", m_trade.ResultRetcodeDescription()); // 印出錯誤
      } // 結束
   } // 多單結束
   // 賣出跨式右翼做空 (Short OTM Call 側賣空)：Z >= +2.1σ
   else if(z_score_1 >= InpZScoreEntry) // 符合賣 Call 空單條件
   { // 執行賣出
       double bid_price = m_symbol.Bid(); // 賣出價
       double sl_price = (InpHardStopPoints > 0) ? NormalizeDouble(bid_price + InpHardStopPoints * _Point, _Digits) : 0; // [修復] 停損價正規化精度
       double tp_price = (InpTakeProfitPoints > 0) ? NormalizeDouble(bid_price - InpTakeProfitPoints * _Point, _Digits) : 0; // [修復] 止盈價正規化精度

      if(m_trade.Sell(InpLotSize, _Symbol, bid_price, sl_price, tp_price, "Short Straddle Sell (Short Call Wing)")) // 送出賣單
      { // 成功
         Print("[+] 跨式右翼做空開倉成功! Z-Score: ", DoubleToString(z_score_1, 2), " 價格: ", bid_price); // 印出訊息
      } // 結束
      else // 失敗
      { // 輸出失敗
         Print("[-] 做空開倉失敗! 錯誤: ", m_trade.ResultRetcode(), " 說明: ", m_trade.ResultRetcodeDescription()); // 印出錯誤
      } // 結束
   } // 空單結束
} // OnTick 結束

//+------------------------------------------------------------------+ // 函數分隔
//| 實時管理持倉：監控 Z-Score 均值回歸收租與極端停損                 | // 持倉管理註解
//+------------------------------------------------------------------+ // 分隔線
void ManageOpenPositions() // 持倉管理函數
{ // 區塊開始
   double current_z = CalculateZScore(0); // 計算當前最新 K 棒的 Z-Score

   for(int i = PositionsTotal() - 1; i >= 0; i--) // 倒序遍歷持倉
   { // 迴圈
      if(m_position.SelectByIndex(i)) // 選取
      { // 成功
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber) // 匹配
         { // 匹配成功
            if(m_position.PositionType() == POSITION_TYPE_BUY) // 若持有多單 (Short Put 側)
            { // 多單檢查
               // 止盈收租：Z >= -0.2σ (均值回歸達成)
               if(current_z >= -InpZScoreExit) // 觸達均值回歸
               { // 平倉
                  m_trade.PositionClose(m_position.Ticket()); // 市價止盈
                  Print("[+] 多單均值回歸止盈收租 (Z >= -0.2)! Z: ", DoubleToString(current_z, 2), " Ticket: ", m_position.Ticket()); // 日誌
               } // 結束
               // 極端停損：Z <= -3.8σ (單邊暴跌突破)
               else if(current_z <= -InpZScoreHardStop) // 觸達極端偏離
               { // 平倉
                  m_trade.PositionClose(m_position.Ticket()); // 市價止損
                  Print("[-] 多單觸及極端偏離停損 (Z <= -3.8)! Z: ", DoubleToString(current_z, 2), " Ticket: ", m_position.Ticket()); // 日誌
               } // 結束
            } // 多單結束
            else if(m_position.PositionType() == POSITION_TYPE_SELL) // 若持有空單 (Short Call 側)
            { // 空單檢查
               // 止盈收租：Z <= +0.2σ (均值回歸達成)
               if(current_z <= InpZScoreExit) // 觸達均值回歸
               { // 平倉
                  m_trade.PositionClose(m_position.Ticket()); // 市價止盈
                  Print("[+] 空單均值回歸止盈收租 (Z <= +0.2)! Z: ", DoubleToString(current_z, 2), " Ticket: ", m_position.Ticket()); // 日誌
               } // 結束
               // 極端停損：Z >= +3.8σ (單邊暴漲突破)
               else if(current_z >= InpZScoreHardStop) // 觸達極端偏離
               { // 平倉
                  m_trade.PositionClose(m_position.Ticket()); // 市價止損
                  Print("[-] 空單觸及極端偏離停損 (Z >= +3.8)! Z: ", DoubleToString(current_z, 2), " Ticket: ", m_position.Ticket()); // 日誌
               } // 結束
            } // 空單結束
         } // 匹配結束
      } // 選取結束
   } // 遍歷結束
} // ManageOpenPositions 結束

//+------------------------------------------------------------------+ // 函數分隔
//| 取得本策略當前未平倉訂單數量                                     | // 統計持倉註解
//+------------------------------------------------------------------+ // 分隔線
int GetPositionCount() // 統計函數
{ // 區塊開始
   int count = 0; // 計數器
   for(int i = PositionsTotal() - 1; i >= 0; i--) // 遍歷
   { // 迴圈
      if(m_position.SelectByIndex(i)) // 選取
      { // 成功
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber) // 匹配
         { // 匹配
            count++; // 計數累加
         } // 結束
      } // 結束
   } // 遍歷結束
   return(count); // 回傳
} // GetPositionCount 結束

//+------------------------------------------------------------------+ // 函數分隔
//| 清倉本策略所有部位 (Zero-Overnight 強制清倉)                      | // 全平倉註解
//+------------------------------------------------------------------+ // 分隔線
void CloseAllPositions(string reason) // 全平倉函數
{ // 區塊開始
   for(int i = PositionsTotal() - 1; i >= 0; i--) // 倒序遍歷
   { // 迴圈
      if(m_position.SelectByIndex(i)) // 選取
      { // 成功
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber) // 匹配
         { // 執行平倉
            ulong ticket = m_position.Ticket(); // [修復] 先暫存 Ticket 避免迴圈中物件狀態變更
            if(!m_trade.PositionClose(ticket)) // [修復] 檢查平倉是否成功
            { // 平倉失敗
               Print("[!] 強制清倉失敗 [", reason, "] Ticket: ", ticket, " Err: ", m_trade.ResultRetcode(), " 將在下一 Tick 重試"); // 記錄失敗日誌
            } // 失敗結束
            else // 平倉成功
            { // 成功
               Print("[*] 執行強制清倉成功 [", reason, "] Ticket: ", ticket); // 輸出成功日誌
            } // 成功結束
         } // 結束
      } // 結束
   } // 遍歷結束
} // CloseAllPositions 結束
