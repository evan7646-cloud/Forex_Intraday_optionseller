from strategy_arena.base import BaseOptionSellerStrategy  # 匯入策略基類
import pandas as pd  # 匯入 pandas 處理表格

class MacroTrendEMAAlignmentStrategy(BaseOptionSellerStrategy):  # 200 EMA 大週期趨勢宏觀對齊策略
    def __init__(self, atr_buffer: float = 1.2):  # 初始化建構函數
        super().__init__(  # 呼叫父類初始化
            name="03_EMA200_大週期宏觀對齊 (Macro EMA Alignment)",  # 策略名稱
            description="做多要求價格高於 200 EMA - 1.2 ATR，做空要求價格低於 200 EMA + 1.2 ATR，杜絕極端逆大勢交易"  # 說明
        )  # 結束
        self.atr_buffer = atr_buffer  # 緩衝 ATR 倍數

    def filter_entry(self, row: pd.Series, is_long: bool, default_signal: bool, mod_info: dict) -> bool:  # 進場過濾鉤子
        if not default_signal:  # 若原始無訊號
            return False  # 放棄
        c = row["close"]  # 當前收盤價
        e200 = row.get("EMA200", c)  # 讀取 200 EMA (若無則預設收盤價)
        atr = row["ATR"]  # 讀取當前 ATR
        if is_long:  # 做多判定
            return bool(c > e200 - self.atr_buffer * atr)  # 價格不可嚴重低於 200 EMA，避免空頭瀑布逆勢做多
        else:  # 做空判定
            return bool(c < e200 + self.atr_buffer * atr)  # 價格不可嚴重高於 200 EMA，避免多頭主升段逆勢做空
