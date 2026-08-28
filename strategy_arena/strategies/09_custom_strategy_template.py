from strategy_arena.base import BaseOptionSellerStrategy  # 匯入策略基類
import pandas as pd  # 匯入 pandas 處理表格

class CustomStrategyIdeaTemplate(BaseOptionSellerStrategy):  # 使用者自定義新交易邏輯外掛範本類別
    def __init__(self):  # 初始化建構函數
        super().__init__(  # 呼叫父類初始化
            name="09_自定義新策略外掛範本 (Custom Plugin Template)",  # 策略名稱
            description="使用者可在此檔案自由覆寫 prepare_indicators, filter_entry, filter_exit 等鉤子函式"  # 策略說明
        )  # 結束

    def prepare_indicators(self, df: pd.DataFrame, mod_info: dict) -> pd.DataFrame:  # 特徵擴展鉤子
        # 範例：可在此計算 MACD, SuperTrend, StochRSI, VWAP 等自定義指標
        # df['MACD'] = ...
        return df  # 回傳計算後資料表

    def filter_entry(self, row: pd.Series, is_long: bool, default_signal: bool, mod_info: dict) -> bool:  # 開倉過濾鉤子
        if not default_signal:  # 原始無訊號
            return False  # 放棄
        # 範例：若希望只在特定時段或指標條件才開倉，可在此自訂邏輯
        return True  # 預設允許開倉

    def filter_exit(self, row: pd.Series, pos: int, entry_price: float, default_sl_dist: float, bars_held: int, mod_info: dict) -> float:  # 出場調制鉤子
        # 範例：可在此實作動態追蹤停損 (Trailing Stop) 或保本停損 (Breakeven)
        return default_sl_dist  # 預設維持原始 ATR 停損距離
