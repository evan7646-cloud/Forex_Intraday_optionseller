from strategy_arena.base import BaseOptionSellerStrategy  # 匯入策略基類
import pandas as pd  # 匯入 pandas 處理表格

class BBBandwidthExpansionGuardStrategy(BaseOptionSellerStrategy):  # 51Bitquant 布林帶寬擴張防禦策略
    def __init__(self, max_bandwidth_ratio: float = 1.45):  # 初始化建構函數
        super().__init__(  # 呼叫父類初始化
            name="01_51Bitquant_布林帶寬防單邊 (BB Bandwidth Guard)",  # 策略名稱
            description=f"在布林帶寬/均線比率 > {max_bandwidth_ratio} 時一票否決開倉，杜絕單邊趨勢爆發接飛刀"  # 策略說明
        )  # 結束
        self.max_ratio = max_bandwidth_ratio  # 帶寬擴張比率上限

    def filter_entry(self, row: pd.Series, is_long: bool, default_signal: bool, mod_info: dict) -> bool:  # 進場過濾鉤子
        if not default_signal:  # 若原始無開倉訊號
            return False  # 直接放棄
        bb_ratio = row.get("BB_WIDTH_RATIO", 1.0)  # 讀取當前布林帶寬相對於 20 均線的比率
        if bb_ratio > self.max_ratio:  # 若當前帶寬暴增超過門檻 (代表行情進入極速單邊爆發期)
            return False  # 一票否決開倉，避免被單邊爆發打穿停損
        return True  # 帶寬處於正常平穩震盪區間，允許開倉
