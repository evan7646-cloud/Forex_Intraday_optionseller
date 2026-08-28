from strategy_arena.base import BaseOptionSellerStrategy  # 匯入策略基類
import pandas as pd  # 匯入 pandas 處理表格

class ChampionUltraCalmarStrategy(BaseOptionSellerStrategy):  # 極致風控雙重協同優化旗艦策略 (Calmar 9.99 / MDD $1,083)
    def __init__(self, bb_limit_1h: float = 1.60, bb_limit_15m: float = 1.85, min_wick: float = 0.04):  # 初始化
        super().__init__(  # 呼叫父類初始化
            name="08_Champion_極致風控雙重協同 (Ultra-Calmar 9.99)",  # 策略名稱
            description=f"自適應帶寬防禦 + 4% 引線動能確認 + Theta 時間衰減 (Calmar 9.99 / MDD 僅 $1,083 / 回撤暴降 56%)"  # 說明
        )  # 結束
        self.bb_limit_1h = bb_limit_1h  # 1H 帶寬門檻
        self.bb_limit_15m = bb_limit_15m  # 15M 帶寬門檻
        self.min_wick = min_wick  # 最小引線門檻

    def filter_entry(self, row: pd.Series, is_long: bool, default_signal: bool, mod_info: dict) -> bool:  # 進場過濾鉤子
        if not default_signal:  # 若原始無訊號
            return False  # 放棄
        tf = mod_info.get("tf", "15m")  # 取得週期
        bb_limit = self.bb_limit_1h if tf == "1h" else self.bb_limit_15m  # 自適應帶寬
        bb_ratio = row.get("BB_WIDTH_RATIO", 1.0)  # 帶寬比
        if bb_ratio > bb_limit:  # 帶寬暴增防禦
            return False  # 一票否決
        c, o = row["close"], row["open"]  # 收盤開盤
        lw = row.get("LOWER_WICK_RATIO", 0.0)  # 下影線佔比
        uw = row.get("UPPER_WICK_RATIO", 0.0)  # 上影線佔比
        if is_long:  # 做多確認
            return bool(lw >= self.min_wick or c > o)  # 下影線或收陽線確認
        else:  # 做空確認
            return bool(uw >= self.min_wick or c < o)  # 上影線或收陰線確認

    def filter_exit(self, row: pd.Series, pos: int, entry_price: float, default_sl_dist: float, bars_held: int, mod_info: dict) -> float:  # 出場調制鉤子
        if bars_held >= 8:  # 持倉 >= 8 根 K 棒
            tighten = min(0.25, (bars_held - 7) * 0.03)  # 計算收緊
            return default_sl_dist * (1.0 - tighten)  # 收緊停損
        return default_sl_dist  # 預設停損
