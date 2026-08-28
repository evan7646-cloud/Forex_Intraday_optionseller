from strategy_arena.base import BaseOptionSellerStrategy  # 匯入策略基類
import pandas as pd  # 匯入 pandas 資料分析庫

class BaselineProductionStrategy(BaseOptionSellerStrategy):  # 原始生產版對照基準策略 (Control Benchmark)
    def __init__(self):  # 初始化建構函數
        super().__init__(  # 呼叫父類建構函數
            name="00_原始生產版基準 (Control Baseline)",  # 策略名稱
            description="極限布林通道 (2.0σ~3.0σ) + RSI 14 (32/68) + 碰中軌盈利止盈 + ATR 硬停損 (v4.10 原版)"  # 策略簡介
        )  # 建構結束

    # 原始生產版本：完全遵從預設布林通道極限偏離與 RSI 超買超賣訊號，不覆寫任何過濾器
    def filter_entry(self, row: pd.Series, is_long: bool, default_signal: bool, mod_info: dict) -> bool:  # 進場過濾鉤子
        return default_signal  # 100% 遵從預設主訊號進場
