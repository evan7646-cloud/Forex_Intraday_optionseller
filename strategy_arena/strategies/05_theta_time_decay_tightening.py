from strategy_arena.base import BaseOptionSellerStrategy  # 匯入策略基類
import pandas as pd  # 匯入 pandas 處理表格

class ThetaTimeDecayTighteningStrategy(BaseOptionSellerStrategy):  # 期權時間價值階梯衰減出場策略
    def __init__(self, start_bars: int = 8, decay_rate: float = 0.04, max_decay: float = 0.30):  # 初始化
        super().__init__(  # 呼叫父類初始化
            name="05_Theta_時間價值衰減收緊 (Time-Decay Exit)",  # 策略名稱
            description=f"持倉超過 {start_bars} 根 K 棒未回歸中軌時，每根 K 棒階梯收緊停損 {int(decay_rate*100)}% (上限 {int(max_decay*100)}%)，降低時間尾部風險"  # 說明
        )  # 結束
        self.start_bars = start_bars  # 啟動收緊之持倉 K 棒數
        self.decay_rate = decay_rate  # 每根收緊比率
        self.max_decay = max_decay  # 最大累積收緊上限

    def filter_exit(self, row: pd.Series, pos: int, entry_price: float, default_sl_dist: float, bars_held: int, mod_info: dict) -> float:  # 出場調制鉤子
        if bars_held >= self.start_bars:  # 若持倉時間超過設定門檻
            decay_factor = min(self.max_decay, (bars_held - self.start_bars + 1) * self.decay_rate)  # 計算動態收緊係數
            return default_sl_dist * (1.0 - decay_factor)  # 回傳收緊後的 ATR 停損距離
        return default_sl_dist  # 預設維持原始 ATR 停損距離
