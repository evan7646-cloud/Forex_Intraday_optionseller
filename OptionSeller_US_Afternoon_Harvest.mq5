//+------------------------------------------------------------------+ // 檔案標頭宣告
//|                         OptionSeller_US_Afternoon_Harvest.mq5 | // 檔案名稱
//|                                  Copyright 2026, Quant Fund Team | // 版權宣告
//|             🌙 策略二：【晚間美盤午後極窄點差收租策略】MT5 專屬自動化 EA | // 策略描述說明
//+------------------------------------------------------------------+ // 標頭結束
#property copyright "Copyright 2026, Quant Fund Team" // 版權設定
#property link      "https://github.com/evan7646-cloud" // 專案網址
#property version   "5.10" // 策略版本號 (v5.10 汰弱留強精銳升級版：納入 EURCAD 1h，剔除 EURUSD/EURNZD)
#property description "🌙 策略二【晚間美盤午後極窄點差收租 EA v5.10】：專攻 GBPJPY (1h), GBPUSD (15m), EURJPY (1h), EURCAD (1h)，運作時段 MT5 13:00~19:00 (台北 18:00~00:00)" // 描述

#include <Trade\Trade.mqh> // 導入 MT5 交易執行標準庫
#include <Trade\PositionInfo.mqh> // 導入持倉資訊查詢標準庫
#include <Trade\SymbolInfo.mqh> // 導入商品規格與行情標準庫

//--- 外部可調參數設定 (Inputs)
input group "=== 1. 資金管理與手數配置 ===" // 參數分組 1
input double   InpLotSize             = 1.0;    // 交易下單手數 (固定 1.0 手，FTMO 10K 請設 0.1)
input ulong    InpMagicNumber         = 800201; // 策略專屬 Magic Number 識別碼
input int      InpMaxSpreadPoints     = 25;     // 最大容許點差 (25 Points = 2.5 pips，超過禁止開倉)

input group "=== 2. 美盤交易時段與換日防禦 (MT5 伺服器時間 UTC+3) ===" // 參數分組 2
input int      InpUSStartHour         = 13;     // 美盤開倉起始小時 (MT5 13:00 = 台北 18:00)
input int      InpUSEndHour           = 18;     // 美盤開倉結束小時 (MT5 18:59 = 台北 23:59)
input bool     InpForceDailyClose     = true;   // 啟用每日強制清倉離場 (零隔夜 Zero-Overnight)
input int      InpForceCloseHour      = 22;     // 強制全平小時 (MT5 22:00 = 台北 03:00，換日前全平)
input int      InpFridayCloseHour     = 20;     // 週五提前清倉小時 (MT5 20:00 = 台北 01:00，避免跨週末跳空)

input group "=== 3. 布林通道 (Bollinger Bands) 參數 ===" // 參數分組 3
input bool     InpAutoParams          = true;   // 啟用自動品種參數適配 (EURCAD 3.0σ, EURJPY 2.5σ, GBPJPY/GBPUSD 2.2σ)
input int      InpBBPeriod            = 20;     // 布林通道均線週期 (20 SMA)
input double   InpBBMandatorySigma    = 2.2;    // 自訂布林標準差 (若關閉自動適配時生效)
input bool     InpExitAtBBMiddle      = true;   // 價格回歸布林中軌時是否立即止盈平倉

input group "=== 4. RSI 與動能過濾參數 ===" // 參數分組 4
input int      InpRSI_Period          = 14;     // RSI 計算週期 (14)
input double   InpRSI_Overbought      = 68.0;   // RSI 超買閾值 (>= 68 確認空單訊號)
input double   InpRSI_Oversold        = 32.0;   // RSI 超賣閾值 (<= 32 確認多單訊號)

input group "=== 5. ATR 動態停損參數 ===" // 參數分組 5
input int      InpATR_Period          = 14;     // ATR 週期 (14)
input double   InpATR_Multiplier      = 2.0;    // 自訂 ATR 止損倍數 (若關閉自動適配時生效)

input group "=== 6. [v5.10 新增] 波動度防禦與動能耗盡過濾 ===" // 參數分組 6
input bool     InpUseBandwidthGuard   = true;   // 啟用布林帶寬擴張防禦 (防單邊爆發接飛刀)
input double   InpMaxBandwidthRatio1H = 1.60;   // 1H 圖表最大容許帶寬比率 (1.60x)
input double   InpMaxBandwidthRatio15M= 1.85;   // 15M 圖表最大容許帶寬比率 (1.85x)
input bool     InpUseWickRejection    = true;   // 啟用 K 線引線動能衰竭確認 (防實體大棒接飛刀)
input double   InpMinWickRatio        = 0.04;   // 最小反向引線佔比門檻 (4% 或反轉實體)
input bool     InpUseThetaDecaySL     = true;   // 啟用持倉時間階梯收緊停損 (降低尾部風險)
input int      InpDecayStartBars      = 8;      // 啟動時間收緊之持倉 K 棒數 (8 根)

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
//| 去除經紀商 Symbol 後綴 (如 .a, .r, m 等) 取得純淨品種名                | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
string CleanSymbolName(string sym) // Symbol 後綴清理函數
{ // 區塊開始
   string base = sym; // 複製原始名稱
   int dot_pos = StringFind(base, "."); // 搜尋小數點後綴位置 (例如 GBPJPY.a)
   if(dot_pos > 0) base = StringSubstr(base, 0, dot_pos); // 截斷小數點後綴
   int len = StringLen(base); // 取得長度
   if(len > 6) // 長度大於標準 6 字元貨幣對
   { // 檢查末字
      ushort last_char = StringGetCharacter(base, len - 1); // 取得最後一個字元
      if(last_char >= 'a' && last_char <= 'z') // 若為小寫字母後綴 (如 m, r, c)
      { // 截斷
         base = StringSubstr(base, 0, len - 1); // 移除最後一個字元
      } // 截斷結束
   } // 長度判斷結束
   return base; // 回傳清理後的品種名稱
} // CleanSymbolName 結束

//+------------------------------------------------------------------+ // 函數分隔
//| [v5.10] 依據當前商品自動獲取最佳布林標準差倍數                          | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
double GetOptimalSigma(string sym) // 自動獲取標準差倍數
{ // 區塊開始
   if(!InpAutoParams) return InpBBMandatorySigma; // 若未啟用自動適配則回傳手動值
   string clean = CleanSymbolName(sym); // 清理 Symbol 後綴
   if(clean == "EURCAD") return 3.0; // EURCAD 美盤最佳為 3.0σ
   if(clean == "EURJPY") return 2.5; // EURJPY 美盤最佳為 2.5σ
   if(clean == "GBPJPY" || clean == "GBPUSD") return 2.2; // GBPJPY/GBPUSD 最佳為 2.2σ
   return 2.2; // 預設 2.2σ
} // GetOptimalSigma 結束

//+------------------------------------------------------------------+ // 函數分隔
//| [v5.10] 依據當前商品自動獲取最佳 ATR 停損倍數                           | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
double GetOptimalATRStop(string sym) // 自動獲取 ATR 停損倍數
{ // 區塊開始
   if(!InpAutoParams) return InpATR_Multiplier; // 若未啟用自動適配則回傳手動值
   string clean = CleanSymbolName(sym); // 清理 Symbol 後綴
   if(clean == "EURCAD" || clean == "GBPUSD") return 2.0; // EURCAD/GBPUSD 最佳為 2.0 ATR
   if(clean == "GBPJPY" || clean == "EURJPY") return 1.5; // GBPJPY/EURJPY 最佳為 1.5 ATR
   return 2.0; // 預設 2.0 ATR
} // GetOptimalATRStop 結束

//+------------------------------------------------------------------+ // 函數分隔
//| [v5.10] 檢查布林帶寬擴張比率是否處於安全震盪區間 (杜絕單邊爆發接飛刀)         | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
bool IsBandwidthSafe() // 帶寬安全檢查函數
{ // 區塊開始
   if(!InpUseBandwidthGuard) return true; // 若未啟用帶寬防禦則直接放行
   double bb_up[20], bb_low[20], bb_mid[20]; // 定義布林軌道陣列 (20 週期)
   ArraySetAsSeries(bb_up, true); // 設定為倒序
   ArraySetAsSeries(bb_low, true); // 設定為倒序
   ArraySetAsSeries(bb_mid, true); // 設定為倒序
   if(CopyBuffer(m_handle_bb, 1, 1, 20, bb_up) < 20) return true; // 複製上軌數據 (失敗放行)
   if(CopyBuffer(m_handle_bb, 2, 1, 20, bb_low) < 20) return true; // 複製下軌數據
   if(CopyBuffer(m_handle_bb, 0, 1, 20, bb_mid) < 20) return true; // 複製中軌數據
   
   double sum_w = 0.0; // 帶寬累加變數
   double curr_width = (bb_up[0] - bb_low[0]) / (bb_mid[0] + 1e-9); // 當前 K 棒帶寬
   for(int i = 0; i < 20; i++) // 計算 20 週期帶寬平均值
   { // 迴圈開始
      double w = (bb_up[i] - bb_low[i]) / (bb_mid[i] + 1e-9); // 計算單根帶寬
      sum_w += w; // 累加帶寬
   } // 迴圈結束
   double ma_width = sum_w / 20.0; // 計算帶寬 20 均值
   double curr_width_ratio = curr_width / (ma_width + 1e-9); // 計算當前帶寬比率
   
   double max_allowed = (_Period == PERIOD_H1) ? InpMaxBandwidthRatio1H : InpMaxBandwidthRatio15M; // 依週期選取門檻
   return (curr_width_ratio <= max_allowed); // 若帶寬比率小於上限則回傳安全 true
} // IsBandwidthSafe 結束

//+------------------------------------------------------------------+ // 函數分隔
//| [v5.10] 檢查 K 棒引線拒絕形態 (確認極限拉伸後的反轉動能)                  | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
bool IsWickRejectionValid(bool is_long) // 引線確認函數
{ // 區塊開始
   if(!InpUseWickRejection) return true; // 若未啟用引線確認則直接放行
   MqlRates rates[1]; // 定義 K 棒結構陣列
   ArraySetAsSeries(rates, true); // 設定為倒序
   if(CopyRates(_Symbol, _Period, 1, 1, rates) < 1) return true; // 複製前一根已收盤 K 棒
   double range = (rates[0].high - rates[0].low) + 1e-9; // 計算全距
   if(is_long) // 做多 (賣 Put) 檢查
   { // 多單
      double lower_wick = MathMin(rates[0].open, rates[0].close) - rates[0].low; // 計算下影線長度
      return ((lower_wick / range >= InpMinWickRatio) || (rates[0].close > rates[0].open)); // 下影線 >= 4% 或收陽線
   } // 多單結束
   else // 做空 (賣 Call) 檢查
   { // 空單
      double upper_wick = rates[0].high - MathMax(rates[0].open, rates[0].close); // 計算上影線長度
      return ((upper_wick / range >= InpMinWickRatio) || (rates[0].close < rates[0].open)); // 上影線 >= 4% 或收陰線
   } // 空單結束
} // IsWickRejectionValid 結束

//+------------------------------------------------------------------+ // 函數分隔
//| [v5.10] 管理期權時間價值階梯衰減停損 (持倉 > 8 根 K 棒動態收緊停損)         | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
void ManageThetaDecayStopLoss(double atr_val, double active_atr_sl) // 時間衰減停損管理函數
{ // 區塊開始
   if(!InpUseThetaDecaySL) return; // 若未啟用時間衰減則退出
   datetime current_time = TimeCurrent(); // 當前伺服器時間
   for(int i = PositionsTotal() - 1; i >= 0; i--) // 遍歷持倉
   { // 遍歷
      if(m_position.SelectByIndex(i)) // 選取持倉
      { // 選取成功
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber) // 比對標的與 Magic
         { // 符合
            datetime pos_time = (datetime)PositionGetInteger(POSITION_TIME); // 取得開倉時間
            int bar_seconds = PeriodSeconds(_Period); // 當前週期每根 K 棒秒數
            int bars_held = (int)((current_time - pos_time) / (bar_seconds > 0 ? bar_seconds : 900)); // 計算持有 K 棒數
            if(bars_held >= InpDecayStartBars) // 持倉超過設定 K 棒數
            { // 觸發時間收緊
               double decay_pct = MathMin(0.25, (bars_held - InpDecayStartBars + 1) * 0.03); // 每根收緊 3% (上限 25%)
               double curr_sl_dist = (active_atr_sl * atr_val) * (1.0 - decay_pct); // 計算收緊後停損距離
               double open_p = m_position.PriceOpen(); // 進場價格
               double current_sl = m_position.StopLoss(); // 當前停損
               if(m_position.PositionType() == POSITION_TYPE_BUY) // 多單
               { // 多單
                  double new_sl = NormalizeDouble(open_p - curr_sl_dist, _Digits); // 新停損
                  if(new_sl > current_sl) // 停損上移
                  { // 執行修改
                     m_trade.PositionModify(m_position.Ticket(), new_sl, 0); // 更新伺服器停損
                     Print("⏱️ [多單時間收緊停損] 持倉 ", bars_held, " 根 K 棒，停損上移至: ", new_sl); // 日誌
                  } // 修改結束
               } // 多單結束
               else if(m_position.PositionType() == POSITION_TYPE_SELL) // 空單
               { // 空單
                  double new_sl = NormalizeDouble(open_p + curr_sl_dist, _Digits); // 新停損
                  if(current_sl == 0.0 || new_sl < current_sl) // 停損下移
                  { // 執行修改
                     m_trade.PositionModify(m_position.Ticket(), new_sl, 0); // 更新伺服器停損
                     Print("⏱️ [空單時間收緊停損] 持倉 ", bars_held, " 根 K 棒，停損下移至: ", new_sl); // 日誌
                  } // 修改結束
               } // 空單結束
            } // 時間收緊結束
         } // 符合結束
      } // 選取結束
   } // 遍歷結束
} // ManageThetaDecayStopLoss 結束

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
   
   m_handle_bb = iBands(_Symbol, _Period, InpBBPeriod, 0, active_sigma, PRICE_CLOSE); // 建立布林通道指標
   m_handle_rsi = iRSI(_Symbol, _Period, InpRSI_Period, PRICE_CLOSE); // 建立 RSI 指標
   m_handle_atr = iATR(_Symbol, _Period, InpATR_Period); // 建立 ATR 指標
   
   if(m_handle_bb == INVALID_HANDLE || m_handle_rsi == INVALID_HANDLE || m_handle_atr == INVALID_HANDLE) // 檢查
   { // 建立失敗
      Print("❌ 建立技術指標 Handles 失敗！"); // 輸出日誌
      return INIT_FAILED; // 回傳失敗
   } // 判斷結束
   
   m_last_bar_time = 0; // 重設 K 棒時間
   
   Print("=========================================================================="); // 分隔線
   Print(" 🌙【策略二：晚間美盤午後極窄點差收租 EA v5.10】成功啟動！標的: ", _Symbol, " (清理後: ", CleanSymbolName(_Symbol), ") | 週期: ", EnumToString(_Period)); // 啟動提示
   Print(" • 運作時段: MT5 13:00 ~ 19:00 (台北 18:00 ~ 00:00)"); // 時段提示
   Print(" • 布林通道: 20 SMA / ", DoubleToString(active_sigma, 1), "σ | 止損: ", DoubleToString(active_atr_sl, 1), " ATR"); // 參數提示
   Print(" • [v5.10 防禦]: 帶寬擴張防禦: ", InpUseBandwidthGuard ? "ON" : "OFF", " | 引線動能衰竭確認: ", InpUseWickRejection ? "ON" : "OFF", " | 時間衰減停損: ", InpUseThetaDecaySL ? "ON" : "OFF"); // 防禦提示
   Print(" • 每日強制全平: MT5 22:00 (台北 03:00) | 週五提前清倉: MT5 ", InpFridayCloseHour, ":00 | 換日休市保護: MT5 23:45~01:15"); // 風控提示
   Print("=========================================================================="); // 分隔線
   
   return INIT_SUCCEEDED; // 初始化成功
} // OnInit 結束

//+------------------------------------------------------------------+ // 函數分隔
//| Expert deinitialization function (EA 釋放卸載函數)                | // 卸載註解
//+------------------------------------------------------------------+ // 分隔線
void OnDeinit(const int reason) // 卸載入口函數
{ // 區塊開始
   IndicatorRelease(m_handle_bb); // 釋放布林通道
   IndicatorRelease(m_handle_rsi); // 釋放 RSI
   IndicatorRelease(m_handle_atr); // 釋放 ATR
   Print("🔌 策略二【晚間美盤收租 EA v5.10】已卸載。"); // 輸出日誌
} // OnDeinit 結束

//+------------------------------------------------------------------+ // 函數分隔
//| 檢查當前是否處於美盤允許開倉時間窗口 (MT5 13:00 ~ 18:59:59)              | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
bool IsWithinAllowedEntryWindow() // 允許開倉判定函數
{ // 區塊開始
   MqlDateTime dt; // 宣告時間結構
   TimeToStruct(TimeCurrent(), dt); // 解析當前時間
   
   if(dt.hour >= InpUSStartHour && dt.hour <= InpUSEndHour) return true; // 符合美盤窗口 (MT5 13:00 ~ 18:59)
   return false; // 否則禁止
} // IsWithinAllowedEntryWindow 結束

//+------------------------------------------------------------------+ // 函數分隔
//| 檢查是否到達每日強制清倉時間 (MT5 22:00 = 台北 03:00)                   | // 函數說明
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
//| 檢查是否為週五提前清倉時段 (避免跨週末跳空)                            | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
bool IsFridayCloseTime() // 週五提前清倉判定函數
{ // 區塊開始
   MqlDateTime dt; // 宣告時間結構
   TimeToStruct(TimeCurrent(), dt); // 解析當前時間
   if(dt.day_of_week == 5 && dt.hour >= InpFridayCloseHour) return true; // 週五 MT5 20:00 後強制清倉
   return false; // 非週五清倉時段
} // IsFridayCloseTime 結束

//+------------------------------------------------------------------+ // 函數分隔
//| 強制平倉 + 失敗重試與錯誤日誌                                         | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
void CloseAllPositions(string reason_text) // 全平函數
{ // 區塊開始
   for(int i = PositionsTotal() - 1; i >= 0; i--) // 倒序遍歷持倉
   { // 遍歷
      if(m_position.SelectByIndex(i)) // 選取持倉
      { // 選取成功
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber) // 比對標的與 Magic
         { // 符合條件
            ulong ticket = m_position.Ticket(); // 暫存 Ticket 避免迴圈中狀態變更
            if(!m_trade.PositionClose(ticket)) // 檢查平倉是否成功
            { // 平倉失敗
               Print("⚠️ [強制清倉失敗] Ticket: ", ticket, " | 錯誤碼: ", m_trade.ResultRetcode(), // 輸出錯誤碼
                     " | 說明: ", m_trade.ResultRetcodeDescription(), " | 原因: ", reason_text, // 輸出錯誤描述
                     " | ⚡ 將在下一 Tick 重試"); // 提示重試機制
            } // 失敗結束
            else // 平倉成功
            { // 成功
               Print("🛑 [強制清倉成功] 已平部位 Ticket: ", ticket, " | 原因: ", reason_text); // 輸出成功日誌
            } // 成功結束
         } // 判斷結束
      } // 選取結束
   } // 遍歷結束
} // CloseAllPositions 結束

//+------------------------------------------------------------------+ // 函數分隔
//| 計算當前策略持倉數量                                                 | // 函數說明
//+------------------------------------------------------------------+ // 分隔線
int CountMyPositions() // 持倉計數函數
{ // 區塊開始
   int count = 0; // 計數器歸零
   for(int i = PositionsTotal() - 1; i >= 0; i--) // 倒序遍歷所有持倉
   { // 遍歷
      if(m_position.SelectByIndex(i)) // 選取持倉
      { // 選取成功
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber) // 比對本策略標的與 Magic
         { // 符合
            count++; // 累加計數
         } // 符合結束
      } // 選取結束
   } // 遍歷結束
   return count; // 回傳持倉數量
} // CountMyPositions 結束

//+------------------------------------------------------------------+ // 函數分隔
//| Expert tick function (即時行情跳動核心函數)                       | // 主迴圈註解
//+------------------------------------------------------------------+ // 分隔線
void OnTick() // 即時行情入口
{ // 區塊開始
   // 1. 週五提前清倉檢查 (避免跨週末跳空風險)
   if(IsFridayCloseTime()) // 週五清倉時間檢查
   { // 週五清倉
      CloseAllPositions("週五提前清倉 (MT5 " + IntegerToString(InpFridayCloseHour) + ":00)，避免跨週末跳空"); // 平倉
      return; // 退出
   } // 週五清倉結束
   
   // 2. 換日前強制清倉檢查
   if(IsForceCloseTime()) // 清倉時間檢查
   { // 清倉
      CloseAllPositions("每日換日前強制清倉 (MT5 22:00 / 台北 03:00)"); // 平倉
      return; // 退出
   } // 結束
   
   // 3. 檢查新 K 棒生成
   datetime current_bar_time = iTime(_Symbol, _Period, 0); // 取得 K 棒時間
   if(current_bar_time == m_last_bar_time) return; // 非新 K 棒退出
   
   // 4. 讀取技術指標數值
   double bb_upper[], bb_middle[], bb_lower[]; // 布林緩衝
   double rsi_val[], atr_val[]; // RSI/ATR 緩衝
   ArraySetAsSeries(bb_upper, true); ArraySetAsSeries(bb_middle, true); ArraySetAsSeries(bb_lower, true); // 設定倒序
   ArraySetAsSeries(rsi_val, true); ArraySetAsSeries(atr_val, true); // 設定倒序
   
   if(CopyBuffer(m_handle_bb, 1, 1, 2, bb_upper) < 2 || // 複製上軌
      CopyBuffer(m_handle_bb, 0, 1, 2, bb_middle) < 2 || // 複製中軌
      CopyBuffer(m_handle_bb, 2, 1, 2, bb_lower) < 2 || // 複製下軌
      CopyBuffer(m_handle_rsi, 0, 1, 2, rsi_val) < 2 || // 複製 RSI
      CopyBuffer(m_handle_atr, 0, 1, 2, atr_val) < 2) // 複製 ATR
   { return; } // 失敗退出
   
   MqlRates rates[]; // K 線陣列
   ArraySetAsSeries(rates, true); // 設倒序
   if(CopyRates(_Symbol, _Period, 1, 2, rates) < 2) return; // 複製已收盤 K 棒
   
   double closed_price = rates[0].close; // 前一根收盤價
   double prev_bb_mid = bb_middle[0]; // 前一根中軌
   double prev_bb_upper = bb_upper[0]; // 前一根上軌
   double prev_bb_lower = bb_lower[0]; // 前一根下軌
   double prev_rsi = rsi_val[0]; // 前一根 RSI
   double prev_atr = atr_val[0]; // 前一根 ATR
   double active_atr_sl = GetOptimalATRStop(_Symbol); // 取得 ATR 止損倍數
   
   // 5. [v5.10] 管理持倉時間階梯收緊停損 (降低跨時段長持倉風險)
   ManageThetaDecayStopLoss(prev_atr, active_atr_sl); // 執行時間收緊停損檢查
   
   // 6. 持倉管理與布林中軌動態止盈平倉 (回歸中軌 + 盈利條件才止盈)
   for(int i = PositionsTotal() - 1; i >= 0; i--) // 遍歷
   { // 遍歷
      if(m_position.SelectByIndex(i)) // 選取
      { // 成功
         if(m_position.Symbol() == _Symbol && m_position.Magic() == InpMagicNumber) // 比對
         { // 符合
            if(m_position.PositionType() == POSITION_TYPE_BUY) // 多單持倉
            { // 多單
               if(InpExitAtBBMiddle && closed_price >= prev_bb_mid && closed_price > m_position.PriceOpen()) // 收盤觸碰中軌 + 當前盈利才止盈
               { // 止盈出場
                  m_trade.PositionClose(m_position.Ticket()); // 執行平倉
                  Print("🎉 [多單中軌止盈] 觸及布林中軌平倉！Ticket: ", m_position.Ticket(), " | 獲利: $", m_position.Profit()); // 日誌
               } // 結束
            } // 結束
            else if(m_position.PositionType() == POSITION_TYPE_SELL) // 空單持倉
            { // 空單
               if(InpExitAtBBMiddle && closed_price <= prev_bb_mid && closed_price < m_position.PriceOpen()) // 收盤觸碰中軌 + 當前盈利才止盈
               { // 止盈出場
                  m_trade.PositionClose(m_position.Ticket()); // 執行平倉
                  Print("🎉 [空單中軌止盈] 觸及布林中軌平倉！Ticket: ", m_position.Ticket(), " | 獲利: $", m_position.Profit()); // 日誌
               } // 結束
            } // 結束
         } // 符合結束
      } // 選取結束
   } // 持倉管理結束
   
   // 7. 精確判定持倉數量
   bool has_position = (CountMyPositions() > 0); // 計算持倉數量
   
   // 8. 開倉訊號檢查 (價格標準化 NormalizeDouble，注入 v5.10 帶寬防禦與引線衰竭確認)
   if(!has_position && IsWithinAllowedEntryWindow()) // 開倉判定
   { // 開倉檢查
      if(!m_symbol.RefreshRates()) return; // 刷新行情
      if(m_symbol.Spread() > InpMaxSpreadPoints) { m_last_bar_time = current_bar_time; return; } // 點差保護
      
      // 多單訊號：收盤跌破布林下軌 + RSI <= 32 + 帶寬未暴增 + 引線/收陽動能衰竭確認
      if(closed_price <= prev_bb_lower && prev_rsi <= InpRSI_Oversold && IsBandwidthSafe() && IsWickRejectionValid(true)) // 多單條件
      { // 做多
         double ask = m_symbol.Ask(); // 即時買價
         double sl = NormalizeDouble(ask - (active_atr_sl * prev_atr), _Digits); // 價格標準化 ATR 止損
         if(m_trade.Buy(InpLotSize, _Symbol, ask, sl, 0, "US_Afternoon_ShortPut_Buy")) // 發送多單 (TP=0)
         { // 成功
            Print("🚀 [美盤做多] 跌破下軌做多 (Buy)！Ask: ", ask, " | SL: ", sl, " | RSI: ", prev_rsi); // 日誌
         } // 成功結束
         else // 開倉失敗錯誤日誌
         { // 失敗
            Print("❌ [美盤做多失敗] 錯誤碼: ", m_trade.ResultRetcode(), " | 說明: ", m_trade.ResultRetcodeDescription(), // 輸出錯誤碼
                  " | Ask: ", ask, " | SL: ", sl, " | RSI: ", prev_rsi); // 輸出價格參數
         } // 失敗結束
      } // 結束
      
      // 空單訊號：收盤衝破布林上軌 + RSI >= 68 + 帶寬未暴增 + 引線/收陰動能衰竭確認
      else if(closed_price >= prev_bb_upper && prev_rsi >= InpRSI_Overbought && IsBandwidthSafe() && IsWickRejectionValid(false)) // 空單條件
      { // 做空
         double bid = m_symbol.Bid(); // 即時賣價
         double sl = NormalizeDouble(bid + (active_atr_sl * prev_atr), _Digits); // 價格標準化 ATR 止損
         if(m_trade.Sell(InpLotSize, _Symbol, bid, sl, 0, "US_Afternoon_ShortCall_Sell")) // 發送空單 (TP=0)
         { // 成功
            Print("🚀 [美盤做空] 突破上軌做空 (Sell)！Bid: ", bid, " | SL: ", sl, " | RSI: ", prev_rsi); // 日誌
         } // 成功結束
         else // 開倉失敗錯誤日誌
         { // 失敗
            Print("❌ [美盤做空失敗] 錯誤碼: ", m_trade.ResultRetcode(), " | 說明: ", m_trade.ResultRetcodeDescription(), // 輸出錯誤碼
                  " | Bid: ", bid, " | SL: ", sl, " | RSI: ", prev_rsi); // 輸出價格參數
         } // 失敗結束
      } // 結束
   } // 開倉結束
   
   m_last_bar_time = current_bar_time; // 更新時間
} // OnTick 結束
