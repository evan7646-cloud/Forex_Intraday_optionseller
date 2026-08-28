from strategy_arena.base import BaseOptionSellerStrategy  # 匯入策略基類
import pandas as pd  # 匯入 pandas 處理表格

class PriceActionPinbarRejectionStrategy(BaseOptionSellerStrategy):  # 價格行為引線拒絕與動能耗盡確認策略
    def __init__(self, min_wick_ratio: float = 0.15):  # 初始化建構函數
        super().__init__(  # 呼叫父類初始化
            name="02_PriceAction_引線形態衰竭 (Pinbar Rejection)",  # 策略名稱
            description=f"多單需下影線 >= {int(min_wick_ratio*100)}% 或收陽線，空單需上影線 >= {int(min_wick_ratio*100)}% 或收陰線確認反轉動能"  # 策略說明
        )  # 結束
        self.min_wick = min_wick_ratio  # 最小引線佔比門檻

    def filter_entry(self, row: pd.Series, is_long: bool, default_signal: bool, mod_info: dict) -> bool:  # 進場過濾鉤子
        if not default_signal:  # 若原始無開倉訊號
            return False  # 放棄
        c, o = row["close"], row["open"]  # 當前 K 棒收盤價與開盤價
        lw = row.get("LOWER_WICK_RATIO", 0.0)  # 當前 K 棒下影線佔比
        uw = row.get("UPPER_WICK_RATIO", 0.0)  # 當前 K 棒上影線佔比
        if is_long:  # 做多 (賣出 Put) 判定
            return bool(lw >= self.min_wick or c > o)  # 需具備足夠下影線(買方拒絕更低價)或收陽線確認
        else:  # 做空 (賣出 Call) 判定
            return bool(uw >= self.min_wick or c < o)  # 需具備足夠上影線(賣方拒絕更高價)或收陰線確認
