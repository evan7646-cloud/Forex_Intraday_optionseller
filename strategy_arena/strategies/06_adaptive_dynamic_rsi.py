from strategy_arena.base import BaseOptionSellerStrategy  # 匯入策略基類
import pandas as pd  # 匯入 pandas 處理表格

class AdaptiveDynamicRSIStrategy(BaseOptionSellerStrategy):  # 品種波動度自適應動態 RSI 策略
    def __init__(self):  # 初始化建構函數
        super().__init__(  # 呼叫父類初始化
            name="06_Adaptive_品種自適應動態RSI (Pair Dynamic RSI)",  # 策略名稱
            description="日圓/紐幣高波交叉盤採用更嚴格 30/70 超買超賣閾值，低點差直盤採用 33/67 閾值以提高資金周轉率"  # 說明
        )  # 結束

    def filter_entry(self, row: pd.Series, is_long: bool, default_signal: bool, mod_info: dict) -> bool:  # 進場過濾鉤子
        sym = mod_info.get("symbol", "")  # 取得品種名稱
        c, ub, lb, rsi = row["close"], row["UB"], row["LB"], row["RSI"]  # 取得當前價格與指標
        is_high_vol = ("JPY" in sym) or ("NZD" in sym)  # 判斷是否為高波動日圓/紐幣商品
        os_thresh = 30.0 if is_high_vol else 33.0  # 動態超賣閾值
        ob_thresh = 70.0 if is_high_vol else 67.0  # 動態超買閾值
        if is_long:  # 做多判定
            return bool(c <= lb and rsi <= os_thresh)  # 需滿足自適應超賣
        else:  # 做空判定
            return bool(c >= ub and rsi >= ob_thresh)  # 需滿足自適應超買
