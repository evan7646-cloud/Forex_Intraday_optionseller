//+------------------------------------------------------------------+ // 檔案標頭宣告
//|                     OptionSeller_DualSession_MultiTF_Harvest.mq5 | // 檔案名稱
//|                                  Copyright 2026, Quant Fund Team | // 版權宣告
//|             方案 D【全天分工收租旗艦 8 大王牌模組】MT5 官方自動化交易 EA | // 策略描述說明
//+------------------------------------------------------------------+ // 標頭結束
#property copyright "Copyright 2026, Quant Fund Team" // 版權設定
#property link      "https://github.com/evan7646-cloud" // 專案網址
#property version   "3.10" // 策略版本號 (方案 D 全天分工雙時段旗艦 Debug 版)
#property description "方案 D 全天分工收租旗艦 EA：白天通道避險 (MT5 01:15~18:00) + 晚間美盤收斂 (MT5 13:00~19:00)，100% 避開 04:45~06:15 換日擴點" // 描述

#include <Trade\Trade.mqh> // 導入 MT5 交易執行標準庫
#include <Trade\PositionInfo.mqh> // 導入持倉資訊查詢標準庫
#include <Trade\SymbolInfo.mqh> // 導入商品規格與行情標準庫

//--- 策略運作模式枚舉
enum ENUM_STRATEGY_MODE // 策略運作模式枚舉型態
{ // 枚舉開始
   MODE_AUTO_DETECT     = 0, // 👑 自動模式：依據圖表貨幣對自動適配時段與參數
   MODE_DAY_CHANNEL     = 1, // ☀️ 白天通道組：MT5 01:15 ~ 18:00 (台北 06:15 ~ 23:00)
   MODE_US_AFTERNOON    = 2  // 🌙 晚間美盤組：MT5 13:00 ~ 19:00 (台北 18:00 ~ 00:00)
}; // 枚舉結束

//--- 外部可調參數設定 (Inputs)
input group "=== 1. 策略模式與交易品種配置 ===" // 參數分組 1
input ENUM_STRATEGY_MODE InpStrategyMode      = MODE_AUTO_DETECT; // 策略時段運作模式 (預設自動識別)
input double             InpLotSize           = 1.0;              // 交易下單手數 (自營商風控 100K 設 1.0, 10K 設 0.1)
input ulong              InpMagicNumber       = 800801;           // 策略專屬 Magic Number 識別碼
input int                InpMaxSpreadPoints   = 25;               // 最大容許點差 (25 Points = 2.5 pips，超過禁止開倉)

input group "=== 2. 交易時間與換日防禦機制 (MT5 伺服器時間 UTC+3) ===" // 參數分組 2
input int                InpDayStartHour      = 1;                // 白天組開倉起始小時 (MT5 01:00 = 台北 06:00)
input int                InpDayStartMin       = 15;               // 白天組開倉起始分鐘 (MT5 01:15，等換日完全結束)
input int                InpDayEndHour        = 18;               // 白天組開倉結束小時 (MT5 18:00 = 台北 23:00)
input int                InpUSStartHour       = 13;               // 美盤組開倉起始小時 (MT5 13:00 = 台北 18:00)
input int                InpUSEndHour         = 18;               // 美盤組開倉結束小時 (MT5 18:59 = 台北 23:59)
input bool               InpForceDailyClose   = true;             // 啟用每日強制清倉離場 (零隔夜 Zero-Overnight)
input int                InpForceCloseHour    = 22;               // 強制全平小時 (MT5 22:00 = 台北 03:00，換日前全平)

input group "=== 3. 布林通道 (Bollinger Bands) 參數 ===" // 參數分組 3
input bool               InpAutoParams        = true;             // 是否啟用 8 大品種最佳標準差/止損參數自動適配
input int                InpBBPeriod          = 20;               // 布林通道均線週期 (20 SMA)
input double             InpBBMandatorySigma  = 2.2;              // 自訂布林標準差 (若關閉自動適配時生效)
input bool               InpExitAtBBMiddle    = true;             // 價格回歸布林中軌時是否立即止盈平倉

input group "=== 4. RSI 與動能過濾參數 ===" // 參數分組 4
input int                InpRSI_Period        = 14;               // RSI 計算週期 (14)
input double             InpRSI_Overbought    = 68.0;             // RSI 超買閾值 (>= 68 確認空單訊號)
input double             InpRSI_Oversold      = 32.0;             // RSI 超賣閾值 (<= 32 確認多單訊號)

input group "=== 5. ATR 動態停損參數 ===" // 參數分組 5
input int                InpATR_Period        = 14;               // ATR 週期 (14)
input double             InpATR_Multiplier    = 2.0;              // 自訂 ATR 止損倍數 (若關閉自動適配時生效)

//--- 全域物件與控制變數
CTrade         m_trade;          // MT5 交易執行物件實例
CPositionInfo  m_position;       // 持倉資訊查詢物件實例
CSymbolInfo    m_symbol;         // 標的規格與即時行情物件實例

int            m_handle_bb;      // 布林通道指標控制代碼 Handle
int            m_handle_rsi;     // RSI 指標控制代碼 Handle
int            m_handle_atr;     // ATR 指標控制代碼 Handle
datetime       m_last_bar_time;  // 記錄最後執行的 K 棒開盤時間

//+------------------------------------------------------------------+ // 函數分隔
//| 自動設定 ECN 經紀商訂單填充模式 (避免 Error 4756 Unsupported filling)   | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
void SetTradeFillingMode() // 填充模式設定函數
{ // 區塊開始
   uint filling = (uint)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE); // 讀取商品支援的填充模式
   if((filling & SYMBOL_FILLING_IOC) != 0) // 支援 IOC 模式
   { // IOC
      m_trade.SetTypeFilling(ORDER_FILLING_IOC); // 設定為 IOC
   } // IOC 結束
   else if((filling & SYMBOL_FILLING_FOK) != 0) // 支援 FOK 模式
   { // FOK
      m_trade.SetTypeFilling(ORDER_FILLING_FOK); // 設定為 FOK
   } // FOK 結束
   else // 預設模式
   { // RETURN
      m_trade.SetTypeFilling(ORDER_FILLING_RETURN); // 設定為 RETURN
   } // RETURN 結束
} // SetTradeFillingMode 結束

//+------------------------------------------------------------------+ // 函數分隔
//| 依據當前商品自動獲取最佳布林標準差倍數                                  | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
double GetOptimalSigma(string sym) // 自動獲取標準差倍數
{ // 區塊開始
   if(!InpAutoParams) return InpBBMandatorySigma; // 若未啟用自動適配則回傳手動值
   
   if(sym == "EURJPY") return 3.0; // EURJPY 最佳為 3.0σ
   if(sym == "EURAUD" || sym == "AUDCHF") return 2.8; // EURAUD / AUDCHF 最佳為 2.8σ
   if(sym == "GBPJPY" || sym == "GBPUSD" || sym == "AUDUSD" || sym == "USDCAD") return 2.2; // 最佳為 2.2σ
   if(sym == "EURUSD") return 2.0; // EURUSD 最佳為 2.0σ
   
   return 2.2; // 預設回傳 2.2σ
} // GetOptimalSigma 結束

//+------------------------------------------------------------------+ // 函數分隔
//| 依據當前商品自動獲取最佳 ATR 停損倍數                                   | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
double GetOptimalATRStop(string sym) // 自動獲取 ATR 停損倍數
{ // 區塊開始
   if(!InpAutoParams) return InpATR_Multiplier; // 若未啟用自動適配則回傳手動值
   
   if(sym == "AUDCHF" || sym == "AUDUSD" || sym == "USDCAD") return 2.5; // 最佳為 2.5 ATR
   if(sym == "GBPUSD" || sym == "EURUSD" || sym == "EURJPY") return 2.0; // 最佳為 2.0 ATR
   if(sym == "GBPJPY" || sym == "EURAUD") return 1.5; // 最佳為 1.5 ATR
   
   return 2.0; // 預設回傳 2.0 ATR
} // GetOptimalATRStop 結束

//+------------------------------------------------------------------+ // 函數分隔
//| 依據當前商品判定所屬策略時段模式                                      | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
int GetEffectiveStrategyMode(string sym) // 判定時段模式函數
{ // 區塊開始
   if(InpStrategyMode != MODE_AUTO_DETECT) return InpStrategyMode; // 若手動指定則依手動設定
   
   if(sym == "AUDCHF" || sym == "EURJPY" || sym == "USDCAD") // 白天品種
   { // 白天通道
      return MODE_DAY_CHANNEL; // 回傳白天通道模式
   } // 白天結束
   
   return MODE_US_AFTERNOON; // 預設為晚間美盤收斂模式
} // GetEffectiveStrategyMode 結束

//+------------------------------------------------------------------+ // 函數分隔
//| Expert initialization function (EA 初始化函數)                    | // 初始化註解
//+------------------------------------------------------------------+ // 分隔線
int OnInit() // 初始化入口函數
{ // 區塊開始
   m_trade.SetExpertMagicNumber(InpMagicNumber); // 設定交易專屬 Magic Number
   m_trade.SetDeviationInPoints(10); // 設定最大允許滑點 (10 Points = 1 pip)
   SetTradeFillingMode(); // 自動配置 ECN 訂單填充模式 (避免 Error 4756)
   
   if(!m_symbol.Name(_Symbol)) // 載入商品資訊
   { // 載入失敗
      Print("❌ 載入商品資訊失敗: ", _Symbol); // 輸出錯誤日誌
      return INIT_FAILED; // 回傳失敗
   } // 判斷結束
   
   double active_sigma = GetOptimalSigma(_Symbol); // 取得當前標的最佳標準差
   double active_atr_sl = GetOptimalATRStop(_Symbol); // 取得當前標的最佳 ATR 止損
   int active_mode = GetEffectiveStrategyMode(_Symbol); // 取得當前時段模式
   
   // 建立技術指標 Handles
   m_handle_bb = iBands(_Symbol, _Period, InpBBPeriod, 0, active_sigma, PRICE_CLOSE); // 建立布林通道指標
   m_handle_rsi = iRSI(_Symbol, _Period, InpRSI_Period, PRICE_CLOSE); // 建立 RSI 指標
   m_handle_atr = iATR(_Symbol, _Period, InpATR_Period); // 建立 ATR 指標
   
   if(m_handle_bb == INVALID_HANDLE || m_handle_rsi == INVALID_HANDLE || m_handle_atr == INVALID_HANDLE) // 檢查控制代碼
   { // 指標建立失敗
      Print("❌ 建立技術指標 Handles 失敗！"); // 輸出日誌
      return INIT_FAILED; // 回傳失敗
   } // 判斷結束
   
   m_last_bar_time = 0; // 重設 K 棒時間
   
   Print("=========================================================================="); // 分隔線
   Print(" 👑【方案 D 全天分工收租旗艦 EA】成功啟動！標的: ", _Symbol, " | 週期: ", EnumToString(_Period)); // 啟動提示
   Print(" • 運作時段模式: ", (active_mode == MODE_DAY_CHANNEL ? "☀️ 白天全天通道組 (MT5 01:15~18:00)" : "🌙 晚間美盤收斂組 (MT5 13:00~19:00)")); // 模式提示
   Print(" • 布林通道參數: 20 SMA / ", DoubleToString(active_sigma, 1), "σ | 止損: ", DoubleToString(active_atr_sl, 1), " ATR"); // 參數提示
   Print(" • 每日強制全平: MT5 22:00 (台北 03:00) | 換日休市保護: MT5 23:45~01:15"); // 風控提示
   Print("=========================================================================="); // 分隔線
   
   return INIT_SUCCEEDED; // 初始化成功
} // OnInit 結束

//+------------------------------------------------------------------+ // 函數分隔
//| Expert deinitialization function (EA 釋放卸載函數)                | // 卸載註解
//+------------------------------------------------------------------+ // 分隔線
void OnDeinit(const int reason) // 卸載入口函數
{ // 區塊開始
   IndicatorRelease(m_handle_bb); // 釋放布林通道指標資源
   IndicatorRelease(m_handle_rsi); // 釋放 RSI 指標資源
   IndicatorRelease(m_handle_atr); // 釋放 ATR 指標資源
   Print("🔌 方案 D 全天分工收租 EA 已卸載。"); // 輸出日誌
} // OnDeinit 結束

//+------------------------------------------------------------------+ // 函數分隔
//| 檢查當前是否處於允許開倉時間窗口                                        | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
bool IsWithinAllowedEntryWindow() // 允許開倉判定函數
{ // 區塊開始
   MqlDateTime dt; // 宣告時間結構
   TimeToStruct(TimeCurrent(), dt); // 解析當前 MT5 伺服器時間
   
   int mode = GetEffectiveStrategyMode(_Symbol); // 取得當前標的時段模式
   
   if(mode == MODE_DAY_CHANNEL) // ☀️ 白天全天通道組 (MT5 01:15 ~ 17:59:59)
   { // 白天時段判定
      if(dt.hour == InpDayStartHour && dt.min < InpDayStartMin) return false; // 換日剛結束前 15 分鐘不進場
      if(dt.hour >= InpDayStartHour && dt.hour < InpDayEndHour) return true; // 符合白天窗口 (01:15 ~ 17:59)
      return false; // 否則禁止
   } // 白天結束
   else // 🌙 晚間美盤午後收斂組 (MT5 13:00 ~ 18:59:59)
   { // 美盤時段判定
      if(dt.hour >= InpUSStartHour && dt.hour <= InpUSEndHour) return true; // 符合美盤窗口
      return false; // 否則禁止
   } // 美盤結束
} // IsWithinAllowedEntryWindow 結束

//+------------------------------------------------------------------+ // 函數分隔
//| 檢查是否到達每日強制清倉時間 (MT5 22:00 = 台北 03:00，換日前 100% 全平) | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
bool IsForceCloseTime() // 強制清倉判定函數
{ // 區塊開始
   if(!InpForceDailyClose) return false; // 若未啟用強制清倉則跳過
   
   MqlDateTime dt; // 宣告時間結構
   TimeToStruct(TimeCurrent(), dt); // 解析當前時間
   
   if(dt.hour >= InpForceCloseHour || dt.hour == 0) return true; // MT5 22:00 後至 00:59 強制全平
   return false; // 否則為非清倉時間
} // IsForceCloseTime 結束

//+------------------------------------------------------------------+ // 函數分隔
//| 強制平倉當前標的之所有在途部位 (Zero-Overnight 日內清倉)              | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
void CloseAllPositions(string reason_text) // 全平函數
{ // 區塊開始
   for(int i = PositionsTotal() - 1; i >= 0; i--) // 倒序遍歷持倉
   { // 遍歷
      if(m_position.SelectByIndex(i)) // 選取持倉
      { // 選取成功
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber) // 比對標的與 Magic
         { // 符合條件
            m_trade.PositionClose(m_position.Ticket()); // 執行平倉
            Print("🛑 [強制清倉] 執行全平部位 #", m_position.Ticket(), " | 原因: ", reason_text); // 輸出日誌
         } // 判斷結束
      } // 選取結束
   } // 遍歷結束
} // CloseAllPositions 結束

//+------------------------------------------------------------------+ // 函數分隔
//| Expert tick function (即時行情跳動核心函數)                       | // 主迴圈註解
//+------------------------------------------------------------------+ // 分隔線
void OnTick() // 即時行情入口
{ // 區塊開始
   // 1. 每日換日前強制清倉檢查
   if(IsForceCloseTime()) // 若到達清倉時間
   { // 執行清倉
      CloseAllPositions("每日換日前強制清倉 (MT5 22:00 / 台北 03:00)"); // 執行平倉
      return; // 終止後續開倉
   } // 清倉結束
   
   // 2. 檢查是否有新 K 棒生成 (以 K 棒收盤為基準)
   datetime current_bar_time = iTime(_Symbol, _Period, 0); // 取得當前 K 棒開盤時間
   if(current_bar_time == m_last_bar_time) return; // 若非新 K 棒則直接退出
   
   // 3. 讀取指標數值 (取第 1 根已封閉 K 棒之指標)
   double bb_upper[], bb_middle[], bb_lower[]; // 布林通道緩衝陣列
   double rsi_val[]; // RSI 緩衝陣列
   double atr_val[]; // ATR 緩衝陣列
   
   ArraySetAsSeries(bb_upper, true); // 設定為倒序陣列
   ArraySetAsSeries(bb_middle, true); // 設定為倒序陣列
   ArraySetAsSeries(bb_lower, true); // 設定為倒序陣列
   ArraySetAsSeries(rsi_val, true); // 設定為倒序陣列
   ArraySetAsSeries(atr_val, true); // 設定為倒序陣列
   
   if(CopyBuffer(m_handle_bb, 1, 1, 2, bb_upper) < 2 || // 複製上軌
      CopyBuffer(m_handle_bb, 0, 1, 2, bb_middle) < 2 || // 複製中軌
      CopyBuffer(m_handle_bb, 2, 1, 2, bb_lower) < 2 || // 複製下軌
      CopyBuffer(m_handle_rsi, 0, 1, 2, rsi_val) < 2 || // 複製 RSI
      CopyBuffer(m_handle_atr, 0, 1, 2, atr_val) < 2) // 複製 ATR
   { // 複製失敗
      return; // 退出
   } // 判斷結束
   
   MqlRates rates[]; // 宣告 K 線行情陣列
   ArraySetAsSeries(rates, true); // 設為倒序
   if(CopyRates(_Symbol, _Period, 1, 2, rates) < 2) return; // 複製前一根已收盤 K 棒
   
   double closed_price = rates[0].close; // 前一根收盤價
   double prev_bb_mid = bb_middle[0]; // 前一根布林中軌
   double prev_bb_upper = bb_upper[0]; // 前一根布林上軌
   double prev_bb_lower = bb_lower[0]; // 前一根布林下軌
   double prev_rsi = rsi_val[0]; // 前一根 RSI
   double prev_atr = atr_val[0]; // 前一根 ATR
   double active_atr_sl = GetOptimalATRStop(_Symbol); // 取得該商品最佳 ATR 止損倍數
   
   // 4. 持倉管理與布林中軌止盈平倉判定 (修正: 移除 PriceOpen 限制)
   bool has_position = false; // 是否持倉標記
   for(int i = PositionsTotal() - 1; i >= 0; i--) // 遍歷現有持倉
   { // 遍歷
      if(m_position.SelectByIndex(i)) // 選取持倉
      { // 選取成功
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber) // 比對
         { // 符合
            has_position = true; // 設為持倉中
            
            // 多單持倉檢查 (Short Put 買多)
            if(m_position.PositionType() == POSITION_TYPE_BUY) // 多單
            { // 多單邏輯
               if(InpExitAtBBMiddle && closed_price >= prev_bb_mid) // 觸及或突破中軌
               { // 止盈出場
                  m_trade.PositionClose(m_position.Ticket()); // 執行平倉
                  Print("🎉 [多單中軌止盈] 觸及布林中軌平倉！Ticket: ", m_position.Ticket(), " | 獲利: $", m_position.Profit()); // 日誌
                  has_position = false; // 重設標記
               } // 止盈結束
            } // 多單結束
            
            // 空單持倉檢查 (Short Call 賣空)
            else if(m_position.PositionType() == POSITION_TYPE_SELL) // 空單
            { // 空單邏輯
               if(InpExitAtBBMiddle && closed_price <= prev_bb_mid) // 觸及或跌破中軌
               { // 止盈出場
                  m_trade.PositionClose(m_position.Ticket()); // 執行平倉
                  Print("🎉 [空單中軌止盈] 觸及布林中軌平倉！Ticket: ", m_position.Ticket(), " | 獲利: $", m_position.Profit()); // 日誌
                  has_position = false; // 重設標記
               } // 止盈結束
            } // 空單結束
         } // 符合結束
      } // 選取結束
   } // 持倉管理結束
   
   // 5. 開倉訊號判定 (修正: 價格標準化 NormalizeDouble，靜態 TP=0 依賴動態中軌平倉)
   if(!has_position && IsWithinAllowedEntryWindow()) // 無持倉且時段允許
   { // 開倉檢查
      if(!m_symbol.RefreshRates()) return; // 刷新即時行情
      
      // 點差保護檢查
      if(m_symbol.Spread() > InpMaxSpreadPoints) // 點差過大
      { // 放棄開倉
         Print("⚠️ 當前點差 (", m_symbol.Spread(), " pts) 超過上限 (", InpMaxSpreadPoints, " pts)，暫停開倉！"); // 警告日誌
         m_last_bar_time = current_bar_time; // 更新時間
         return; // 退出
      } // 點差結束
      
      // 多單進場訊號：收盤跌破布林下軌 + RSI <= 32 極度超賣
      if(closed_price <= prev_bb_lower && prev_rsi <= InpRSI_Oversold) // 多頭進場條件
      { // 執行做多
         double ask = m_symbol.Ask(); // 取得即時買價
         double sl_price = NormalizeDouble(ask - (active_atr_sl * prev_atr), _Digits); // 價格標準化 ATR 動態止損價
         
         if(m_trade.Buy(InpLotSize, _Symbol, ask, sl_price, 0, "SchemeD_ShortPut_Buy")) // 發送多單 (TP=0)
         { // 成功
            Print("🚀 [做多開倉] 突破布林下軌觸發賣出 Put (Buy)！價格: ", ask, " | SL: ", sl_price, " | RSI: ", prev_rsi); // 日誌
         } // 成功結束
      } // 做多結束
      
      // 空單進場訊號：收盤衝破布林上軌 + RSI >= 68 極度超買
      else if(closed_price >= prev_bb_upper && prev_rsi >= InpRSI_Overbought) // 空頭進場條件
      { // 執行做空
         double bid = m_symbol.Bid(); // 取得即時賣價
         double sl_price = NormalizeDouble(bid + (active_atr_sl * prev_atr), _Digits); // 價格標準化 ATR 動態止損價
         
         if(m_trade.Sell(InpLotSize, _Symbol, bid, sl_price, 0, "SchemeD_ShortCall_Sell")) // 發送空單 (TP=0)
         { // 成功
            Print("🚀 [做空開倉] 突破布林上軌觸發賣出 Call (Sell)！價格: ", bid, " | SL: ", sl_price, " | RSI: ", prev_rsi); // 日誌
         } // 成功結束
      } // 做空結束
   } // 開倉檢查結束
   
   m_last_bar_time = current_bar_time; // 更新執行時間戳記
} // OnTick 結束
