import pandas as pd  # 匯入 pandas 資料分析庫以處理時間序列與特徵表格
from abc import ABC, abstractmethod  # 匯入抽象基礎類別庫以規範統一策略介面

class BaseOptionSellerStrategy(ABC):  # 所有 OptionSeller 收租策略外掛必須繼承的統一抽象基類
    def __init__(self, name: str, description: str):  # 策略建構初始化函數
        self.name = name  # 策略顯示名稱 (例如: '01_51Bitquant_布林帶寬防單邊')
        self.description = description  # 策略邏輯核心一句話說明

    def prepare_indicators(self, df: pd.DataFrame, mod_info: dict) -> pd.DataFrame:  # 特徵與指標擴展計算鉤子函數
        return df  # 預設回傳已具備基礎指標 (MA20/UB/LB/ATR/RSI/ADX/BB_WIDTH/WICK) 的資料表

    def filter_entry(self, row: pd.Series, is_long: bool, default_signal: bool, mod_info: dict) -> bool:  # 進場開倉過濾鉤子
        return default_signal  # 預設遵從極限布林通道 + RSI 超買超賣訊號

    def filter_exit(self, row: pd.Series, pos: int, entry_price: float, default_sl_dist: float, bars_held: int, mod_info: dict) -> float:  # 動態出場與停損調制鉤子
        return default_sl_dist  # 預設維持標準 ATR 停損距離

    def calculate_lot_size(self, row: pd.Series, base_lot: float, mod_info: dict) -> float:  # 動態下單手數調制鉤子
        return base_lot  # 預設維持固定下單手數 (1.0 手)
