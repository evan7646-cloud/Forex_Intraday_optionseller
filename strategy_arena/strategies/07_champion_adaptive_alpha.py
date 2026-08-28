from strategy_arena.base import BaseOptionSellerStrategy  # 匯入策略基類
import pandas as pd  # 匯入 pandas 處理表格

class ChampionAdaptiveAlphaStrategy(BaseOptionSellerStrategy):  # 冠軍自適應週期帶寬 + 時間衰減旗艦策略
    def __init__(self, bb_limit_1h: float = 1.60, bb_limit_15m: float = 1.85, decay_start: int = 8, decay_rate: float = 0.03):  # 初始化
        super().__init__(  # 呼叫父類初始化
            name="07_Champion_自適應週期帶寬旗艦 (Adaptive Multi-TF Alpha)",  # 策略名稱
            description=f"H1 帶寬 < {bb_limit_1h}x / M15 帶寬 < {bb_limit_15m}x 雙層過濾 + 8 根 K 棒 Theta 階梯收緊 (PF 2.04 / MDD 降 42.5%)"  # 說明
        )  # 結束
        self.bb_limit_1h = bb_limit_1h  # 1H 週期帶寬上限
        self.bb_limit_15m = bb_limit_15m  # 15M 週期帶寬上限
        self.decay_start = decay_start  # 衰減起始根數
        self.decay_rate = decay_rate  # 每根衰減率

    def filter_entry(self, row: pd.Series, is_long: bool, default_signal: bool, mod_info: dict) -> bool:  # 進場過濾鉤子
        if not default_signal:  # 若原始無訊號
            return False  # 放棄
        tf = mod_info.get("tf", "15m")  # 取得當前模組時間週期
        bb_limit = self.bb_limit_1h if tf == "1h" else self.bb_limit_15m  # 自適應選擇門檻
        bb_ratio = row.get("BB_WIDTH_RATIO", 1.0)  # 讀取帶寬擴張比率
        if bb_ratio > bb_limit:  # 若帶寬暴增超過門檻
            return False  # 一票否決，避開單邊極速趨勢
        return True  # 通過

    def filter_exit(self, row: pd.Series, pos: int, entry_price: float, default_sl_dist: float, bars_held: int, mod_info: dict) -> float:  # 出場調制鉤子
        if bars_held >= self.decay_start:  # 若持倉時間超過門檻
            tighten = min(0.25, (bars_held - self.decay_start + 1) * self.decay_rate)  # 計算收緊比率
            return default_sl_dist * (1.0 - tighten)  # 回傳收緊後停損
        return default_sl_dist  # 預設停損
