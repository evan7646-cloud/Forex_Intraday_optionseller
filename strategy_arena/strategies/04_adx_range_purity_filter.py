from strategy_arena.base import BaseOptionSellerStrategy  # 匯入策略基類
import pandas as pd  # 匯入 pandas 處理表格

class ADXRangePurityFilterStrategy(BaseOptionSellerStrategy):  # ADX 震盪市場純度鎖定濾網策略
    def __init__(self, max_adx: float = 28.0):  # 初始化建構函數
        super().__init__(  # 呼叫父類初始化
            name="04_ADX_震盪市場純度濾網 (ADX Range Guard)",  # 策略名稱
            description=f"強制要求 ADX(14) < {max_adx}，鎖定純震盪通道環境，當 ADX 呈現單邊強趨勢時一票否決開倉"  # 說明
        )  # 結束
        self.max_adx = max_adx  # ADX 門檻

    def filter_entry(self, row: pd.Series, is_long: bool, default_signal: bool, mod_info: dict) -> bool:  # 進場過濾鉤子
        if not default_signal:  # 若原始無訊號
            return False  # 放棄
        adx_val = row.get("ADX", 20.0)  # 讀取當前 14 週期 ADX 數值
        if adx_val >= self.max_adx:  # 若 ADX >= 門檻 (代表市場處於強單邊趨勢)
            return False  # 嚴禁進行合成期權賣方收租
        return True  # 震盪強度合格，允許開倉
