# 方案 A【全天分工收租旗艦量化策略】MT5 交易邏輯與系統規格說明書

> **版本 5.10 (汰弱留強精銳升級版)** | 最後更新：2026-08-28 | 8 大王牌模組全量 Pepperstone 實盤點差校準

本文件詳細記載 **方案 A（全天分工收租雙時段 8 大王牌精銳模組）** 之兩大獨立 MT5 EA 程式碼與量化架構：
1. ☀️ **`OptionSeller_DaytimeChannel_Harvest.mq5`** v5.10（白天全天通道避險收租策略）
2. 🌙 **`OptionSeller_US_Afternoon_Harvest.mq5`** v5.10（晚間美盤午後極窄點差收租策略）

---

## 🏆 策略組合績效總覽（v5.10 精銳 8 模組）

經由全市場 28 大貨幣對大亂鬥回測與「汰弱留強」機制，剔除低效益品種（`EURUSD 15m`、`EURNZD 1h`、`CHFJPY 15m`），正式納入 3 大高盈虧比新王牌（`EURCAD 1h`、`AUDUSD 1h`、`GBPJPY 15m`）：

| 核心指標 | 升級前 (v5.00 舊 8 模組) | 升級後 (v5.10 精銳 8 模組) | 改善幅度 |
| :--- | :---: | :---: | :---: |
| **總淨利 (USD)** | +$10,825.34 | **+$11,525.79** | 📈 **+$700.45 (+6.5%)** |
| **總交易筆數** | 195 筆 | **175 筆** (去蕪存菁) | 🎯 剔除低效率噪聲單 |
| **綜合勝率 (%)** | 62.6% | **63.4%** | 📈 **+0.8%** |
| **盈虧比 (PF)** | 2.09 | **2.38** | 🚀 **+13.9% (大幅提升)** |
| **最大回撤 (MDD)** | $1,083.16 (1.08%) | **$1,168.17 (1.17%)** | 🛡️ 恆定於 1.17% 極低水平 |
| **卡瑪比率 (Calmar)** | 9.99 | **9.87** | 💎 維持機構級頂級水平 |

---

## 📊 v5.10 精銳 8 大王牌模組詳細配置表

### 🌙 美盤午後組 (US_Afternoon Harvest EA — 4 大模組)
*運作時段：MT5 13:00 ~ 18:59（台北 18:00 ~ 23:59）｜每日清倉：MT5 22:00*

| 模組 ID | 品種 | 週期 | 實盤點差 | 布林 σ | ATR SL | 交易筆數 | 勝率 (%) | 盈虧比 (PF) | 總淨利 (USD) | 最大回撤 | 模組定位與特性 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`Opt_GBPJPY_1H_US`** | **GBPJPY** | **1h** | 2.1p | 2.2σ | 1.5 ATR | 46 筆 | 63.0% | **2.26** | **+$3,959.40** | $643 | 👑 全系統總獲利第一王牌 |
| **`Opt_EURJPY_1H_US`** | **EURJPY** | **1h** | 1.2p | 2.5σ | 1.5 ATR | 19 筆 | 68.4% | **4.15** | **+$1,413.76** | $198 | 高盈虧比歐日美盤收租 |
| **`Opt_GBPUSD_15M_US`** | **GBPUSD** | **15m** | 0.8p | 2.2σ | 2.0 ATR | 27 筆 | 63.0% | **1.78** | **+$1,389.80** | $491 | 極窄點差直盤極速收租 |
| **`Opt_EURCAD_1H_US`** | **EURCAD** | **1h** | 1.9p | 3.0σ | 2.0 ATR | 12 筆 | 58.3% | **3.91** | **+$699.83** | $181 | 🆕 歐加美盤高盈虧收租 |
| **美盤午後小計** | | | | | | **104 筆** | **63.5%** | **2.33** | **+$7,462.79** | **$790** | |

---

### ☀️ 白天全天通道組 (DaytimeChannel Harvest EA — 4 大模組)
*運作時段：MT5 01:15 ~ 18:00（台北 06:15 ~ 23:00）｜每日清倉：MT5 22:00*

| 模組 ID | 品種 | 週期 | 實盤點差 | 布林 σ | ATR SL | 交易筆數 | 勝率 (%) | 盈虧比 (PF) | 總淨利 (USD) | 最大回撤 | 模組定位與特性 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`Opt_EURJPY_15M_DAY`** | **EURJPY** | **15m** | 1.2p | 3.0σ | 2.0 ATR | 10 筆 | **80.0%** | **11.81** | **+$1,302.66** | $120 | 80% 超高勝率白天王牌 |
| **`Opt_AUDCHF_1H_DAY`** | **AUDCHF** | **1h** | 1.0p | 2.8σ | 2.5 ATR | 24 筆 | 58.3% | **2.30** | **+$1,185.65** | $485 | 經典大洋洲避險通道收租 |
| **`Opt_GBPJPY_15M_DAY`** | **GBPJPY** | **15m** | 2.1p | 2.8σ | 2.5 ATR | 16 筆 | 62.5% | **1.96** | **+$817.83** | $351 | 🆕 鎊日白天波動收租 |
| **`Opt_AUDUSD_1H_DAY`** | **AUDUSD** | **1h** | 0.6p | 3.0σ | 2.0 ATR | 21 筆 | 61.9% | **1.89** | **+$756.86** | $326 | 🆕 澳美 0.6p 超低點差收租 |
| **白天通道小計** | | | | | | **71 筆** | **63.4%** | **2.48** | **+$4,063.00** | **$620** | |

---

## 💻 EA 品種自動適配參數對照表

### 1. `OptionSeller_US_Afternoon_Harvest.mq5` v5.10
```mql5
double GetOptimalSigma(string sym)
{
   string clean = CleanSymbolName(sym);
   if(clean == "EURCAD") return 3.0; // EURCAD 3.0σ (高盈虧比通道)
   if(clean == "EURJPY") return 2.5; // EURJPY 2.5σ
   if(clean == "GBPJPY" || clean == "GBPUSD") return 2.2; // GBPJPY/GBPUSD 2.2σ
   return 2.2;
}

double GetOptimalATRStop(string sym)
{
   string clean = CleanSymbolName(sym);
   if(clean == "EURCAD" || clean == "GBPUSD") return 2.0; // EURCAD/GBPUSD 2.0 ATR
   if(clean == "GBPJPY" || clean == "EURJPY") return 1.5; // GBPJPY/EURJPY 1.5 ATR
   return 2.0;
}
```

### 2. `OptionSeller_DaytimeChannel_Harvest.mq5` v5.10
```mql5
double GetOptimalSigma(string sym)
{
   string clean = CleanSymbolName(sym);
   if(clean == "EURJPY" || clean == "AUDUSD") return 3.0; // EURJPY/AUDUSD 3.0σ
   if(clean == "AUDCHF" || clean == "GBPJPY") return 2.8; // AUDCHF/GBPJPY 2.8σ
   return 2.8;
}

double GetOptimalATRStop(string sym)
{
   string clean = CleanSymbolName(sym);
   if(clean == "AUDCHF" || clean == "GBPJPY") return 2.5; // AUDCHF/GBPJPY 2.5 ATR
   if(clean == "EURJPY" || clean == "AUDUSD") return 2.0; // EURJPY/AUDUSD 2.0 ATR
   return 2.0;
}
```
