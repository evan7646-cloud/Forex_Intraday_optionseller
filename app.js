// 全域資料與狀態管理變數
let globalData = null; // 策略結果 JSON 原始數據
let selectedSymbols = new Set(); // 當前使用者勾選的貨幣對集合
let activeStrategyFilter = 'ALL'; // 當前策略過濾 ('ALL', 'SCALPER', 'STRADDLE')
let activeChartTab = 'combined-equity'; // 當前啟用的圖表分頁標籤
let candlestickSymbol = 'AUDCHF'; // 當前 K 線圖所選取的貨幣對標的
let currentPage = 1; // 當前歷史交易表格分頁
let pageSize = 15; // 每頁顯示交易筆數
let tableSearchQuery = ''; // 交易明細搜尋關鍵字
let tableTradeType = 'ALL'; // 交易明細方向過濾 ('ALL', 'BUY', 'SELL')
let tableTradeOutcome = 'ALL'; // 交易明細勝負過濾 ('ALL', 'WIN', 'LOSS')
let highlightedTradeId = null; // 當前點擊聚焦高亮的交易序號

// 貨幣對專屬圖表配色調色盤
const symbolColors = { // 配色字典
    "AUDCHF": "#00e676", // 翡翠綠
    "EURCHF": "#26a69a", // 松石綠
    "AUDCAD": "#29b6f6", // 科技天藍
    "USDCHF": "#ffa726", // 亮橘色
    "USDCAD": "#b388ff"  // 亮紫色
}; // 配色結束

// 8 大模組設定規格參照表
const moduleConfigsRef = { // 規格字典
    "Scalper_AUDCHF": { ea: "OptionSeller_AsianNightScalper_5m.mq5", session: "UTC 22:00 ~ 05:00 (07:00清倉)", params: "TP 5p (50pts) / SL 35p (350pts) / 點差 18pts" }, // AUDCHF 夜間
    "Scalper_EURCHF": { ea: "OptionSeller_AsianNightScalper_5m.mq5", session: "UTC 22:00 ~ 05:00 (07:00清倉)", params: "TP 5p (50pts) / SL 35p (350pts) / 點差 15pts" }, // EURCHF 夜間
    "Scalper_AUDCAD": { ea: "OptionSeller_AsianNightScalper_5m.mq5", session: "UTC 22:00 ~ 05:00 (07:00清倉)", params: "TP 8p (80pts) / SL 40p (400pts) / 點差 20pts" }, // AUDCAD 夜間
    "Scalper_USDCHF": { ea: "OptionSeller_AsianNightScalper_5m.mq5", session: "UTC 22:00 ~ 05:00 (07:00清倉)", params: "TP 8p (80pts) / SL 40p (400pts) / 點差 12pts" }, // USDCHF 夜間
    "Scalper_USDCAD": { ea: "OptionSeller_AsianNightScalper_5m.mq5", session: "UTC 22:00 ~ 05:00 (07:00清倉)", params: "TP 8p (80pts) / SL 40p (400pts) / 點差 12pts" }, // USDCAD 夜間
    "Straddle_AUDCHF": { ea: "OptionSeller_SyntheticShortStraddle_5m.mq5", session: "UTC 07:00 ~ 20:00 (21:00清倉)", params: "Z-in 2.1 / Z-out 0.2 / TP 50 / SL 350" }, // AUDCHF 日間
    "Straddle_AUDCAD": { ea: "OptionSeller_SyntheticShortStraddle_5m.mq5", session: "UTC 07:00 ~ 20:00 (21:00清倉)", params: "Z-in 2.1 / Z-out 0.2 / TP 80 / SL 400" }, // AUDCAD 日間
    "Straddle_USDCAD": { ea: "OptionSeller_SyntheticShortStraddle_5m.mq5", session: "UTC 07:00 ~ 20:00 (21:00清倉)", params: "Z-in 2.1 / Z-out 0.2 / TP 50 / SL 350" }  // USDCAD 日間
}; // 規格字典結束

// 網頁 DOM 載入完畢監聽入口
document.addEventListener('DOMContentLoaded', () => { // DOM 載入後觸發
    initApp(); // 啟動主應用程式
}); // 監聽結束

// 應用程式初始化
async function initApp() { // 初始化函數
    setupEventListeners(); // 綁定所有介面互動事件
    await loadStrategyData(); // 讀取策略 JSON 資料
} // initApp 結束

// 讀取 strategy_results.json 數據
async function loadStrategyData() { // 資料非同步加載函數
    try { // 嘗試執行讀取
        const timeStamp = new Date().getTime(); // 生成防快取時間戳
        const response = await fetch(`strategy_results.json?v=${timeStamp}`); // 發送請求讀取 JSON
        if (!response.ok) throw new Error(`HTTP 錯誤! 狀態碼: ${response.status}`); // 檢查回應狀態
        globalData = await response.json(); // 解析 JSON 物件

        // 初始化商品勾選集合 (預設全選所有 5 大商品)
        const allSyms = Object.keys(globalData.symbols_meta); // 取得全部貨幣對
        selectedSymbols = new Set(allSyms); // 放入集合
        if (allSyms.length > 0) candlestickSymbol = allSyms[0]; // 設定預設 K 線標的

        // 渲染各區塊內容
        renderHeaderStatus(); // 渲染頂部時間與系統狀態
        renderMarketTickers(); // 渲染即時行情小卡
        renderAssetCheckboxes(); // 渲染多商品勾選控制卡片
        recalculateAndRenderKPIs(); // 根據當前勾選重算並渲染 KPI 卡片
        renderMainChart(); // 渲染 Plotly 主圖表
        renderStrategyMatrix(); // 渲染 8 大策略模組參數與實盤績效矩陣總表
        renderTradesTable(); // 渲染歷史交易明細表格

    } catch (err) { // 捕捉異常
        console.error("載入策略資料失敗:", err); // 於 Console 記錄錯誤
        document.getElementById('status-update-time').textContent = '資料載入失敗，請確認 JSON 檔案是否存在！'; // 顯示錯誤提示
    } // 捕捉結束
} // loadStrategyData 結束

// 綁定全域 UI 事件監聽
function setupEventListeners() { // 事件設定函數
    // 重新載入按鈕
    document.getElementById('btn-manual-refresh').addEventListener('click', async () => { // 點擊重整
        const btn = document.getElementById('btn-manual-refresh'); // 取得按鈕 DOM
        btn.innerHTML = '<span>⏳</span> 更新中...'; // 顯示更新中
        await loadStrategyData(); // 重新讀取
        btn.innerHTML = '<span>🔄</span> 重新載入'; // 恢復按鈕文字
    }); // 點擊結束

    // 策略快選群組按鈕事件
    document.getElementById('btn-toggle-all').addEventListener('click', () => applyStrategyPreset('ALL')); // 全部組合
    document.getElementById('btn-toggle-scalper').addEventListener('click', () => applyStrategyPreset('SCALPER')); // 亞洲收租
    document.getElementById('btn-toggle-straddle').addEventListener('click', () => applyStrategyPreset('STRADDLE')); // 跨式賣方
    document.getElementById('btn-select-all').addEventListener('click', () => selectAllSymbols(true)); // 全選商品
    document.getElementById('btn-clear-all').addEventListener('click', () => selectAllSymbols(false)); // 清除商品

    // 圖表分頁切換
    document.querySelectorAll('.tab-btn').forEach(btn => { // 遍歷分頁按鈕
        btn.addEventListener('click', (e) => { // 點擊切換
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active')); // 移除其他按鈕啟用態
            e.target.classList.add('active'); // 當前按鈕設為啟用
            activeChartTab = e.target.getAttribute('data-chart'); // 更新啟用分頁變數
            
            // 若為 K 線圖則顯示標的下拉選單
            const extraOpt = document.getElementById('candlestick-options'); // 取得下拉容器
            if (activeChartTab === 'candlestick-signals') { // 若是 K 線頁
                extraOpt.style.display = 'flex'; // 顯示下拉
            } else { // 否則
                extraOpt.style.display = 'none'; // 隱藏下拉
            } // 判斷結束

            renderMainChart(); // 重新繪製對應圖表
        }); // 監聽結束
    }); // 遍歷結束

    // K 線圖標的下拉選單變更
    document.getElementById('candlestick-symbol-select').addEventListener('change', (e) => { // 選擇變更
        candlestickSymbol = e.target.value; // 更新所選商品
        if (activeChartTab === 'candlestick-signals') { // 若當前正處於 K 線圖
            renderMainChart(); // 重新繪製 K 線圖
        } // 判斷結束
    }); // 監聽結束

    // 交易表格搜尋框輸入
    document.getElementById('table-search').addEventListener('input', (e) => { // 輸入事件
        tableSearchQuery = e.target.value.trim().toLowerCase(); // 取得搜尋關鍵字
        currentPage = 1; // 重設回第一頁
        renderTradesTable(); // 重新渲染表格
    }); // 搜尋監聽結束

    // 交易表格方向下拉篩選
    document.getElementById('filter-trade-type').addEventListener('change', (e) => { // 變更事件
        tableTradeType = e.target.value; // 更新方向篩選變數
        currentPage = 1; // 重設第一頁
        renderTradesTable(); // 重新渲染表格
    }); // 監聽結束

    // 交易表格勝負下拉篩選
    document.getElementById('filter-trade-outcome').addEventListener('change', (e) => { // 變更事件
        tableTradeOutcome = e.target.value; // 更新勝負篩選變數
        currentPage = 1; // 重設第一頁
        renderTradesTable(); // 重新渲染表格
    }); // 監聽結束

    // 每頁顯示筆數變更
    document.getElementById('page-size-select').addEventListener('change', (e) => { // 筆數變更
        pageSize = parseInt(e.target.value, 10); // 轉換數值
        currentPage = 1; // 重設第一頁
        renderTradesTable(); // 重新渲染表格
    }); // 監聽結束

    // 匯出 CSV 按鈕
    document.getElementById('btn-export-csv').addEventListener('click', () => { // 點擊匯出
        exportFilteredTradesCSV(); // 執行 CSV 下載
    }); // 監聽結束
} // setupEventListeners 結束

// 渲染頂部狀態列
function renderHeaderStatus() { // 頂部狀態渲染函數
    const timeEl = document.getElementById('status-update-time'); // 取得時間元素
    if (globalData && globalData.system_info) { // 若系統資訊存在
        timeEl.textContent = `台北時間: ${globalData.system_info.last_updated_tpe} | UTC: ${globalData.system_info.last_updated_utc}`; // 填入時間文字
    } // 判斷結束
} // renderHeaderStatus 結束

// 渲染即時市場行情卡片 (Market Ticker Strip)
function renderMarketTickers() { // 行情卡片渲染函數
    const container = document.getElementById('market-tickers-container'); // 取得容器 DOM
    if (!globalData || !globalData.symbols_meta) return; // 檢查資料

    const meta = globalData.symbols_meta; // 取得商品中繼資料
    container.innerHTML = Object.keys(meta).map(sym => { // 遍歷生成 HTML
        const item = meta[sym]; // 商品資料
        const changeClass = item.price_change_24h_pct >= 0 ? 'val-bull' : 'val-bear'; // 多空顏色
        const changePrefix = item.price_change_24h_pct >= 0 ? '+' : ''; // 正號標記
        
        // 判定當前是否有開倉窗口
        let sessionTag = ''; // 狀態標籤
        if (item.is_scalper_session && item.supports_scalper) { // 處於夜間收租時段
            sessionTag = '<span class="badge-scalper">🌙 夜間收租窗口中</span>'; // 夜間標籤
        } else if (item.is_straddle_session && item.supports_straddle) { // 處於日間跨式時段
            sessionTag = '<span class="badge-straddle">⚡ 日間跨式窗口中</span>'; // 日間標籤
        } else { // 非開倉時段
            sessionTag = '<span style="font-size:10px; color:var(--text-muted);">等待交易窗口</span>'; // 等待標籤
        } // 判斷結束

        return `
            <div class="market-ticker-card" onclick="selectSingleSymbol('${sym}')" title="點擊切換專屬監控 ${sym}">
                <div class="ticker-top-row">
                    <span class="ticker-symbol" style="color:${symbolColors[sym] || 'var(--text-primary)'};">${sym}</span>
                    <span class="${changeClass}" style="font-size:12px; font-weight:700; font-family:var(--font-mono);">${changePrefix}${item.price_change_24h_pct}%</span>
                </div>
                <div class="ticker-price ${changeClass}">$${item.current_price}</div>
                <div class="ticker-indicators">
                    <span>點差: <strong>${item.spread_pips}p</strong></span>
                    <span>RSI: <strong>${item.current_rsi}</strong></span>
                    <span>Z: <strong>${item.current_zscore > 0 ? '+' : ''}${item.current_zscore}σ</strong></span>
                </div>
                <div style="margin-top:4px;">${sessionTag}</div>
            </div>
        `; // 回傳卡片 HTML
    }).join(''); // 串接結束
} // renderMarketTickers 結束

// 渲染多商品勾選控制面板 Checkboxes
function renderAssetCheckboxes() { // 勾選卡片生成函數
    const container = document.getElementById('asset-checkbox-container'); // 取得容器
    if (!container || !globalData || !globalData.symbols_meta) return; // 檢查資料

    const meta = globalData.symbols_meta; // 取得商品資訊
    container.innerHTML = Object.keys(meta).map(sym => { // 遍歷生成 Checkbox
        const item = meta[sym]; // 商品資料
        const isChecked = selectedSymbols.has(sym); // 是否已勾選
        const activeClass = isChecked ? 'checked' : ''; // 樣式類別

        // 策略標籤 HTML
        let tagsHtml = ''; // 標籤字串
        if (item.supports_scalper) tagsHtml += '<span class="badge-scalper" style="font-size:10px; padding:2px 6px;">🌙 夜間剝頭皮</span>'; // 剝頭皮
        if (item.supports_straddle) tagsHtml += '<span class="badge-straddle" style="font-size:10px; padding:2px 6px;">⚡ 日間跨式</span>'; // 跨式

        return `
            <div class="asset-checkbox-item ${activeClass}" data-symbol="${sym}" onclick="toggleSymbolSelection('${sym}')">
                <div class="asset-check-left">
                    <div class="custom-checkbox"></div>
                    <span class="asset-symbol-name" style="color:${symbolColors[sym] || '#fff'};">${sym}</span>
                    <span style="font-size:11px; color:var(--text-secondary); font-family:var(--font-mono);">(${item.spread_pips}p)</span>
                </div>
                <div class="asset-strategy-tags" style="display:flex; gap:4px; flex-wrap:wrap;">
                    ${tagsHtml}
                </div>
            </div>
        `; // 回傳 Checkbox HTML
    }).join(''); // 串接結束
} // renderAssetCheckboxes 結束

// 切換個別商品勾選狀態
function toggleSymbolSelection(sym) { // 單一商品切換函數
    if (selectedSymbols.has(sym)) { // 若已存在
        if (selectedSymbols.size > 1) { // 確保至少保留一個勾選
            selectedSymbols.delete(sym); // 移除
        } // 判斷結束
    } else { // 若未勾選
        selectedSymbols.add(sym); // 加入
    } // 判斷結束

    updateFilterButtonsState(); // 更新按鈕樣式狀態
    renderAssetCheckboxes(); // 重新渲染勾選狀態外觀
    recalculateAndRenderKPIs(); // 動態重算 KPI 指標
    renderMainChart(); // 重新繪製圖表
    renderTradesTable(); // 重新渲染交易表格
} // toggleSymbolSelection 結束

// 點擊即時報價卡片快速單選該標的
function selectSingleSymbol(sym) { // 快速單選函數
    selectedSymbols.clear(); // 清空全部
    selectedSymbols.add(sym); // 僅加入該標的
    candlestickSymbol = sym; // 同步切換 K 線標的
    const selectEl = document.getElementById('candlestick-symbol-select'); // 取得下拉
    if (selectEl) selectEl.value = sym; // 更新下拉選單
    
    updateFilterButtonsState(); // 更新按鈕
    renderAssetCheckboxes(); // 更新勾選外觀
    recalculateAndRenderKPIs(); // 重算 KPI
    renderMainChart(); // 重繪圖表
    renderTradesTable(); // 重繪表格
} // selectSingleSymbol 結束

// 策略快速預設組合切換
function applyStrategyPreset(preset) { // 策略預設函數
    activeStrategyFilter = preset; // 設定當前策略模式
    selectedSymbols.clear(); // 清空集合

    if (preset === 'ALL') { // 全部組合
        Object.keys(globalData.symbols_meta).forEach(s => selectedSymbols.add(s)); // 全部加入
    } else if (preset === 'SCALPER') { // 僅夜間剝頭皮
        Object.keys(globalData.symbols_meta).forEach(s => { // 遍歷
            if (globalData.symbols_meta[s].supports_scalper) selectedSymbols.add(s); // 加入支援者
        }); // 結束
    } else if (preset === 'STRADDLE') { // 僅日間跨式賣方
        Object.keys(globalData.symbols_meta).forEach(s => { // 遍歷
            if (globalData.symbols_meta[s].supports_straddle) selectedSymbols.add(s); // 加入支援者
        }); // 結束
    } // 判斷結束

    updateFilterButtonsState(); // 更新按鈕樣式
    renderAssetCheckboxes(); // 更新 Checkbox
    recalculateAndRenderKPIs(); // 重算 KPI
    renderMainChart(); // 重繪圖表
    renderTradesTable(); // 重繪表格
} // applyStrategyPreset 結束

// 全選或清除所有商品
function selectAllSymbols(selectAll) { // 全選切換函數
    selectedSymbols.clear(); // 清空
    if (selectAll) { // 若為全選
        Object.keys(globalData.symbols_meta).forEach(s => selectedSymbols.add(s)); // 全部加入
        activeStrategyFilter = 'ALL'; // 設為全部
    } else { // 若為清除
        const firstSym = Object.keys(globalData.symbols_meta)[0]; // 取得第一個標的
        if (firstSym) selectedSymbols.add(firstSym); // 保留至少一個標的
    } // 判斷結束

    updateFilterButtonsState(); // 更新按鈕狀態
    renderAssetCheckboxes(); // 更新外觀
    recalculateAndRenderKPIs(); // 重算 KPI
    renderMainChart(); // 重繪圖表
    renderTradesTable(); // 重繪表格
} // selectAllSymbols 結束

// 更新頂部篩選按鈕 active 樣式
function updateFilterButtonsState() { // 按鈕狀態更新函數
    const bAll = document.getElementById('btn-toggle-all'); // 全部按鈕
    const bScalp = document.getElementById('btn-toggle-scalper'); // 夜間按鈕
    const bStrad = document.getElementById('btn-toggle-straddle'); // 日間按鈕
    if (!bAll || !bScalp || !bStrad) return; // 檢查

    bAll.classList.remove('active'); // 移除
    bScalp.classList.remove('active'); // 移除
    bStrad.classList.remove('active'); // 移除

    if (activeStrategyFilter === 'ALL' && selectedSymbols.size === Object.keys(globalData.symbols_meta).length) { // 符合全部
        bAll.classList.add('active'); // 啟用全部
    } else if (activeStrategyFilter === 'SCALPER') { // 符合剝頭皮
        bScalp.classList.add('active'); // 啟用剝頭皮
    } else if (activeStrategyFilter === 'STRADDLE') { // 符合跨式
        bStrad.classList.add('active'); // 啟用跨式
    } // 判斷結束
} // updateFilterButtonsState 結束

// 核心功能：根據當前勾選的商品與策略，動態精算所有 KPI 指標
function recalculateAndRenderKPIs() { // KPI 精算與渲染函數
    if (!globalData || !globalData.all_trades) return; // 檢查資料

    // 篩選出符合當前勾選貨幣對與策略的交易明細
    const filtered = globalData.all_trades.filter(t => { // 過濾交易
        const matchSymbol = selectedSymbols.has(t.symbol); // 是否在勾選商品中
        let matchStrategy = true; // 預設策略符合
        if (activeStrategyFilter === 'SCALPER') matchStrategy = t.strategy.includes('Scalper'); // 僅剝頭皮
        if (activeStrategyFilter === 'STRADDLE') matchStrategy = t.strategy.includes('Straddle'); // 僅跨式
        return matchSymbol && matchStrategy; // 兩者皆符合
    }); // 過濾結束

    // 精算關鍵指標數值
    const totalTrades = filtered.length; // 總交易次數
    const wins = filtered.filter(t => t.win).length; // 獲利次數
    const losses = totalTrades - wins; // 虧損次數
    const winRate = totalTrades > 0 ? (wins / totalTrades * 100).toFixed(1) : '0.0'; // 勝率
    const totalPnl = filtered.reduce((acc, t) => acc + t.pnl_usd, 0); // 總淨利 (USD)
    const totalPips = filtered.reduce((acc, t) => acc + (t.pnl_pips || 0), 0); // 總盈虧點數
    const grossProfit = filtered.filter(t => t.pnl_usd > 0).reduce((acc, t) => acc + t.pnl_usd, 0); // 毛獲利
    const grossLoss = filtered.filter(t => t.pnl_usd < 0).reduce((acc, t) => acc + Math.abs(t.pnl_usd), 0); // 毛虧損
    const profitFactor = grossLoss > 0 ? (grossProfit / grossLoss).toFixed(2) : (wins > 0 ? '99.00' : '0.00'); // 獲利因子
    const roi = (totalPnl / 100000.0 * 100).toFixed(2); // 投報率

    // 計算所選組合的歷史最大回撤 (MDD)
    let mddPct = 0.0; // MDD 百分比
    let mddDollars = 0.0; // MDD 美金
    if (totalTrades > 0) { // 交易筆數大於 0
        const sortedTrades = [...filtered].sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time)); // 依出場時間正序
        let runningBal = 100000.0; // 模擬起始本金
        let peakBal = 100000.0; // 歷史最高權益
        let maxDdVal = 0.0; // 最大回撤金額
        let maxDdPval = 0.0; // 最大回撤百分比

        sortedTrades.forEach(t => { // 遍歷交易
            runningBal += t.pnl_usd; // 累加淨值
            if (runningBal > peakBal) peakBal = runningBal; // 更新新高
            const curDrawdown = peakBal - runningBal; // 當前美金回撤
            const curDrawdownPct = peakBal > 0 ? (curDrawdown / peakBal * 100) : 0; // 當前回撤百分比
            if (curDrawdown > maxDdVal) maxDdVal = curDrawdown; // 更新最大美金回撤
            if (curDrawdownPct > maxDdPval) maxDdPval = curDrawdownPct; // 更新最大百分比回撤
        }); // 遍歷結束

        mddPct = maxDdPval.toFixed(2); // 設定 MDD 百分比
        mddDollars = maxDdVal.toFixed(2); // 設定 MDD 美金
    } // MDD 計算結束

    // 渲染卡片 1：總淨利
    const pnlEl = document.getElementById('kpi-total-pnl'); // 取得 DOM
    pnlEl.textContent = `${totalPnl >= 0 ? '+' : ''}$${totalPnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`; // 格式化美金
    pnlEl.className = 'card-main-val ' + (totalPnl >= 0 ? 'val-bull' : 'val-bear'); // 多空配色
    document.getElementById('kpi-total-pips').textContent = `${totalPips >= 0 ? '+' : ''}${totalPips.toFixed(1)} pips`; // 顯示 pips
    document.getElementById('kpi-total-pips').className = totalPips >= 0 ? 'val-bull' : 'val-bear'; // pips 配色
    document.getElementById('kpi-roi').textContent = `${roi >= 0 ? '+' : ''}${roi}%`; // 顯示 ROI
    document.getElementById('kpi-roi').className = roi >= 0 ? 'val-bull' : 'val-bear'; // ROI 配色

    // 渲染卡片 2：勝率
    document.getElementById('kpi-win-rate').textContent = `${winRate}%`; // 顯示勝率
    document.getElementById('kpi-win-loss-count').textContent = `${wins}W / ${losses}L`; // 勝負次數
    document.getElementById('kpi-total-trades').textContent = `${totalTrades} 筆`; // 總交易筆數

    // 渲染卡片 3：獲利因子
    document.getElementById('kpi-profit-factor').textContent = profitFactor; // 顯示 PF
    document.getElementById('kpi-gross-profit').textContent = `+$${Math.round(grossProfit).toLocaleString()}`; // 顯示毛利
    document.getElementById('kpi-gross-loss').textContent = `-$${Math.round(grossLoss).toLocaleString()}`; // 顯示毛損

    // 渲染卡片 4：最大回撤
    document.getElementById('kpi-max-drawdown').textContent = `-${mddPct}%`; // 顯示 MDD%
    document.getElementById('kpi-mdd-dollars').textContent = `-$${parseFloat(mddDollars).toLocaleString()}`; // 顯示 MDD 美金

    // 渲染卡片 5：當前活躍部位
    const activeList = (globalData.active_positions || []).filter(p => selectedSymbols.has(p.symbol)); // 篩選當前勾選標的的活躍持倉
    const activeCountEl = document.getElementById('kpi-active-count'); // 活躍筆數 DOM
    const unrealizedPnlEl = document.getElementById('kpi-unrealized-pnl'); // 未實現損益 DOM
    const activeStatusEl = document.getElementById('kpi-active-status'); // 狀態標籤 DOM

    if (activeList.length === 0) { // 當前無持倉
        activeCountEl.textContent = '0 部位 (空手)'; // 顯示空手
        activeCountEl.className = 'card-main-val val-cyan'; // 預設色
        unrealizedPnlEl.textContent = '$0.00'; // $0
        unrealizedPnlEl.className = 'val-neutral'; // 白色
        activeStatusEl.textContent = '無隔夜風險'; // 狀態
        activeStatusEl.className = 'val-bull'; // 綠色
    } else { // 當前持有活躍部位
        const totalUnrealized = activeList.reduce((acc, p) => acc + (p.unrealized_pnl_usd || 0), 0); // 累計未實現損益
        activeCountEl.textContent = `${activeList.length} 部位在場`; // 顯示筆數
        activeCountEl.className = 'card-main-val val-blue'; // 亮藍色強調
        unrealizedPnlEl.textContent = `${totalUnrealized >= 0 ? '+' : ''}$${totalUnrealized.toFixed(2)}`; // 數值
        unrealizedPnlEl.className = totalUnrealized >= 0 ? 'val-bull' : 'val-bear'; // 顏色
        activeStatusEl.textContent = activeList.map(p => p.symbol).join(', '); // 標的
        activeStatusEl.className = 'val-purple'; // 紫色
    } // 活躍部位判斷結束
} // recalculateAndRenderKPIs 結束

// 渲染 8 大策略模組參數規格與實盤回測績效矩陣
function renderStrategyMatrix() { // 矩陣渲染函數
    const tbody = document.getElementById('strategy-matrix-table-body'); // 取得表體 DOM
    if (!tbody || !globalData || !globalData.modules_summary) return; // 檢查

    tbody.innerHTML = globalData.modules_summary.map(m => { // 遍歷模組
        const isScalp = m.strategy.includes('Scalper'); // 是否為夜間
        const badgeClass = isScalp ? 'badge-scalper' : 'badge-straddle'; // 樣式標籤
        const stratShortName = isScalp ? '🌙 5m 亞洲夜間收租' : '⚡ 5m 日間合成跨式'; // 短名稱
        const cfgRef = moduleConfigsRef[m.module_id] || { ea: "-", session: "-", params: "-" }; // 讀取設定
        const symColor = symbolColors[m.symbol] || '#fff'; // 標的顏色
        const pnlClass = m.total_pnl_usd >= 0 ? 'val-bull' : 'val-bear'; // 損益顏色

        return `
            <tr>
                <td style="font-family:var(--font-mono); font-weight:700; color:var(--text-secondary); font-size:12px;">${m.module_id}</td>
                <td><span class="${badgeClass}" style="font-size:11px; padding:3px 8px;">${stratShortName}</span></td>
                <td><strong style="color:${symColor}; font-family:var(--font-mono); font-size:14px;">${m.symbol}</strong></td>
                <td style="font-family:var(--font-mono); font-size:11px; color:#58a6ff;">${cfgRef.ea}</td>
                <td style="font-size:11px; color:var(--text-secondary);">${cfgRef.session}</td>
                <td style="font-size:11px; font-family:var(--font-mono); color:#e6edf3;">${cfgRef.params}</td>
                <td style="font-family:var(--font-mono);">${m.trades_count} 筆 (${m.wins}W/${m.losses}L)</td>
                <td><strong class="val-blue" style="font-family:var(--font-mono); font-size:13px;">${m.win_rate}%</strong></td>
                <td><strong class="val-purple" style="font-family:var(--font-mono);">${m.profit_factor}</strong></td>
                <td style="color:var(--color-bear); font-family:var(--font-mono);">-${m.max_drawdown_pct}%</td>
                <td><strong class="${pnlClass}" style="font-family:var(--font-mono); font-size:14px;">+$${m.total_pnl_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong></td>
            </tr>
        `; // 回傳一列 HTML
    }).join(''); // 串接結束
} // renderStrategyMatrix 結束

// 渲染主 Plotly 互動圖表 (依據當前分頁動態切換)
function renderMainChart() { // 主圖表調度函數
    if (!globalData) return; // 檢查資料

    if (activeChartTab === 'combined-equity') { // 分頁 1: 組合資金權益曲線
        renderCombinedEquityChart(); // 繪製組合權益線
    } else if (activeChartTab === 'comparative-equity') { // 分頁 2: 多標的曲線比較
        renderComparativeEquityChart(); // 繪製多標的比較
    } else if (activeChartTab === 'candlestick-signals') { // 分頁 3: 5m K 線與訊號標記
        renderCandlestickChart(candlestickSymbol); // 繪製 K 線圖
    } else if (activeChartTab === 'drawdown-curve') { // 分頁 4: 歷史回撤深度圖
        renderDrawdownChart(); // 繪製回撤圖
    } // 分頁判斷結束
} // renderMainChart 結束

// 繪製分頁 1：組合累積淨損益曲線 (從 $0 起計，隨勾選商品動態重算聚合)
function renderCombinedEquityChart() { // 組合損益圖繪製函數
    const filteredTrades = globalData.all_trades.filter(t => { // 過濾交易
        const matchSymbol = selectedSymbols.has(t.symbol); // 標的符合
        let matchStrategy = true; // 策略符合
        if (activeStrategyFilter === 'SCALPER') matchStrategy = t.strategy.includes('Scalper'); // 剝頭皮
        if (activeStrategyFilter === 'STRADDLE') matchStrategy = t.strategy.includes('Straddle'); // 跨式
        return matchSymbol && matchStrategy; // 兩者符合
    }).sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time)); // 依出場時間正序

    // 建立時間序列節點 (從 $0 淨損益起算)
    const timeSeries = []; // 時間陣列
    const pnlSeries = []; // 累積淨損益陣列
    let currentPnl = 0.0; // 初始累計淨利 $0.0

    if (filteredTrades.length > 0) { // 若有交易
        timeSeries.push(filteredTrades[0].entry_time); // 起始時間點
        pnlSeries.push(0.0); // 起始損益 $0.0
        filteredTrades.forEach(t => { // 遍歷交易
            currentPnl += t.pnl_usd; // 累加淨損益
            timeSeries.push(t.exit_time); // 記錄時間
            pnlSeries.push(Math.round(currentPnl * 100) / 100); // 記錄累計損益
        }); // 遍歷結束
    } else { // 無交易
        timeSeries.push(new Date().toISOString().substring(0, 19).replace('T', ' ')); // 當前時間
        pnlSeries.push(0.0); // 損益 $0.0
    } // 判斷結束

    const isPositive = (pnlSeries[pnlSeries.length - 1] || 0) >= 0; // 判斷最終損益正負
    const lineColor = isPositive ? '#00e676' : '#ff1744'; // 綠色或紅色
    const fillColor = isPositive ? 'rgba(0, 230, 118, 0.12)' : 'rgba(255, 23, 68, 0.12)'; // 對應填充

    const trace = { // 定義曲線軌跡
        x: timeSeries, // X 軸時間
        y: pnlSeries, // Y 軸累積淨損益
        mode: 'lines', // 折線模式
        name: '累積淨損益 ($0起計)', // 圖例名稱
        line: { color: lineColor, width: 2.8 }, // 線條顏色
        fill: 'tozeroy', // 填充至 $0 基準線
        fillcolor: fillColor // 半透明填充
    }; // 軌跡結束

    const layout = { // 定義圖表面版樣式
        paper_bgcolor: '#131722', plot_bgcolor: '#131722', margin: { l: 70, r: 40, t: 40, b: 40 }, // 背景色與邊距
        title: { text: `所選 ${selectedSymbols.size} 款標的之組合累積淨損益曲線 (從 $0 起計 / 扣實盤點差與 $5 手續費)`, font: { color: '#f0f6fc', family: 'Outfit', size: 16 } }, // 標題
        xaxis: { type: 'date', gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' } }, // X 軸
        yaxis: { gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, tickprefix: '$', zeroline: true, zerolinecolor: 'rgba(255,255,255,0.3)', zerolinewidth: 1.5 }, // Y 軸與 $0 基準線
        hovermode: 'x unified', // 統一浮動標籤
        legend: { orientation: 'h', y: 1.1, font: { color: '#8b949e' } } // 圖例
    }; // 面版結束

    Plotly.newPlot('main-plotly-chart', [trace], layout, { responsive: true, displayModeBar: true }); // 渲染 Plotly 圖表
} // renderCombinedEquityChart 結束

// 繪製分頁 2：多商品個別累積損益曲線對比圖 (從 $0 起計)
function renderComparativeEquityChart() { // 多商品比較圖繪製函數
    const traces = []; // 軌跡陣列

    selectedSymbols.forEach(sym => { // 遍歷已勾選的商品
        // 抓取該標的的交易並重建該標的的累計損益曲線
        const symTrades = globalData.all_trades.filter(t => t.symbol === sym).sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time)); // 依時間排序
        if (symTrades.length === 0) return; // 無交易跳過

        const tTimes = [symTrades[0].entry_time]; // 時間
        const tPnls = [0.0]; // 累積損益 (從 $0 開始)
        let rPnl = 0.0; // 當前累計淨利

        symTrades.forEach(t => { // 遍歷
            rPnl += t.pnl_usd; // 累加損益
            tTimes.push(t.exit_time); // 時間
            tPnls.push(Math.round(rPnl * 100) / 100); // 累積損益
        }); // 結束

        traces.push({ // 加入軌跡
            x: tTimes, // 時間
            y: tPnls, // 損益
            mode: 'lines', // 折線
            name: `${sym} (${symTrades.length} 筆 / ${rPnl >= 0 ? '+' : ''}$${Math.round(rPnl).toLocaleString()})`, // 名稱與總獲利
            line: { color: symbolColors[sym] || '#fff', width: 2.2 } // 專屬顏色
        }); // 結束
    }); // 遍歷結束

    const layout = { // 面版樣式
        paper_bgcolor: '#131722', plot_bgcolor: '#131722', margin: { l: 70, r: 40, t: 40, b: 40 }, // 背景色
        title: { text: '各貨幣對獨立累積淨損益比較 (從 $0 起計 / 扣手續費)', font: { color: '#f0f6fc', family: 'Outfit', size: 16 } }, // 標題
        xaxis: { type: 'date', gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' } }, // X 軸
        yaxis: { gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, tickprefix: '$', zeroline: true, zerolinecolor: 'rgba(255,255,255,0.3)', zerolinewidth: 1.5 }, // Y 軸與 $0 基準線
        hovermode: 'x unified', // 統一浮動
        legend: { orientation: 'h', y: 1.12, font: { color: '#8b949e', size: 11 } } // 圖例
    }; // 面版結束

    Plotly.newPlot('main-plotly-chart', traces, layout, { responsive: true, displayModeBar: true }); // 渲染圖表
} // renderComparativeEquityChart 結束

// 繪製分頁 3：5m 互動式 K 線圖與真實進出場買賣訊號點標記
function renderCandlestickChart(sym) { // K 線繪製函數
    if (!globalData || !globalData.chart_data || !globalData.chart_data[sym]) return; // 檢查資料

    const cdata = globalData.chart_data[sym]; // 取得該標的 K 線與指標數據
    const symTrades = globalData.all_trades.filter(t => t.symbol === sym); // 取得該標的交易

    // 1. K 線圖軌跡 (Candlestick)
    const traceCandles = { // K 線
        x: cdata.timestamps, // 時間
        open: cdata.open, // 開盤
        high: cdata.high, // 最高
        low: cdata.low, // 最低
        close: cdata.close, // 收盤
        type: 'candlestick', // 蠟燭圖
        name: `${sym} 5m K線`, // 名稱
        increasing: { line: { color: '#00e676', width: 1.2 }, fillcolor: '#00e676' }, // 陽線翡翠綠
        decreasing: { line: { color: '#ff1744', width: 1.2 }, fillcolor: '#ff1744' }, // 陰線珊瑚紅
        yaxis: 'y' // 主座標軸
    }; // K 線結束

    // 2. 布林通道指標軌跡
    const traceBBUpper = { x: cdata.timestamps, y: cdata.bb_upper, mode: 'lines', name: 'BB 上軌 (2.2σ)', line: { color: 'rgba(41, 182, 246, 0.4)', width: 1.2, dash: 'dot' }, yaxis: 'y' }; // 上軌
    const traceBBMid   = { x: cdata.timestamps, y: cdata.bb_mid, mode: 'lines', name: 'BB 中軌 (20SMA)', line: { color: 'rgba(255, 167, 38, 0.6)', width: 1.2 }, yaxis: 'y' }; // 中軌
    const traceBBLower = { x: cdata.timestamps, y: cdata.bb_lower, mode: 'lines', name: 'BB 下軌 (2.2σ)', line: { color: 'rgba(41, 182, 246, 0.4)', width: 1.2, dash: 'dot' }, yaxis: 'y' }; // 下軌

    // 3. 進場買賣點與出場點標記 (Markers)
    const buyEntries = symTrades.filter(t => t.type.includes('Buy')); // 多單進場
    const sellEntries = symTrades.filter(t => t.type.includes('Sell')); // 空單進場
    const exits = symTrades; // 全部出場

    const traceBuyMarkers = { // 買入標記 (綠色三角向上)
        x: buyEntries.map(t => t.entry_time), // 時間
        y: buyEntries.map(t => t.entry_price), // 價格
        mode: 'markers', // 標記點
        name: '買進進場 (Buy)', // 圖例
        marker: { symbol: 'triangle-up', size: 11, color: '#00e676', line: { color: '#ffffff', width: 1.5 } }, // 綠色三角
        yaxis: 'y' // 主軸
    }; // 買入標記結束

    const traceSellMarkers = { // 賣出標記 (紅色三角向下)
        x: sellEntries.map(t => t.entry_time), // 時間
        y: sellEntries.map(t => t.entry_price), // 價格
        mode: 'markers', // 標記點
        name: '賣出進場 (Sell)', // 圖例
        marker: { symbol: 'triangle-down', size: 11, color: '#ff1744', line: { color: '#ffffff', width: 1.5 } }, // 紅色三角
        yaxis: 'y' // 主軸
    }; // 賣出標記結束

    const traceExitMarkers = { // 出場標記 (黃色方塊)
        x: exits.map(t => t.exit_time), // 時間
        y: exits.map(t => t.exit_price), // 價格
        mode: 'markers', // 標記點
        name: '平倉出場 (Exit)', // 圖例
        marker: { symbol: 'square', size: 7, color: '#ffd600' }, // 黃色方塊
        text: exits.map(t => `出場原因: ${t.exit_reason}<br>損益: ${t.pnl_usd >= 0 ? '+' : ''}$${t.pnl_usd} (${t.pnl_pips}p)`), // 提示框
        hoverinfo: 'text+x+y', // 提示
        yaxis: 'y' // 主軸
    }; // 出場標記結束

    // 4. 下方子圖 1: RSI 指標
    const traceRSI = { // RSI 軌跡
        x: cdata.timestamps, // 時間
        y: cdata.rsi, // 數值
        mode: 'lines', // 折線
        name: 'RSI (14)', // 名稱
        line: { color: '#b388ff', width: 1.5 }, // 紫色
        yaxis: 'y2' // 子座標軸 2
    }; // RSI 結束

    // 5. 下方子圖 2: Z-Score 統計偏離度
    const traceZScore = { // Z-Score 軌跡
        x: cdata.timestamps, // 時間
        y: cdata.z_score, // 數值
        mode: 'lines', // 折線
        name: 'Z-Score (30)', // 名稱
        line: { color: '#29b6f6', width: 1.5 }, // 藍色
        yaxis: 'y3' // 子座標軸 3
    }; // Z-Score 結束

    // 圖表多座標軸複合排版 Layout
    const layout = { // 複合 Layout
        paper_bgcolor: '#131722', plot_bgcolor: '#131722', margin: { l: 70, r: 40, t: 40, b: 40 }, // 背景邊距
        title: { text: `[${sym}] 5m K線、布林通道與實戰進出場訊號點 (最近 800 根 K 棒)`, font: { color: '#f0f6fc', family: 'Outfit', size: 16 } }, // 標題
        xaxis: { type: 'date', gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, rangeslider: { visible: false } }, // X 軸
        yaxis: { domain: [0.38, 1.0], gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, title: '價格' }, // 主 K 線軸 (佔 62% 高度)
        yaxis2: { domain: [0.19, 0.35], gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, title: 'RSI', range: [10, 90] }, // RSI 軸 (佔 16% 高度)
        yaxis3: { domain: [0.0, 0.16], gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, title: 'Z-Score', range: [-4.0, 4.0] }, // Z-Score 軸 (佔 16% 高度)
        hovermode: 'x unified', // 統一浮動
        legend: { orientation: 'h', y: 1.08, font: { color: '#8b949e', size: 11 } } // 圖例
    }; // Layout 結束

    Plotly.newPlot('main-plotly-chart', [traceCandles, traceBBUpper, traceBBMid, traceBBLower, traceBuyMarkers, traceSellMarkers, traceExitMarkers, traceRSI, traceZScore], layout, { responsive: true, displayModeBar: true }); // 渲染
} // renderCandlestickChart 結束

// 繪製分頁 4：歷史回撤深度圖 (Drawdown Underwater Chart)
function renderDrawdownChart() { // 回撤圖繪製函數
    const filteredTrades = globalData.all_trades.filter(t => { // 過濾
        const matchSymbol = selectedSymbols.has(t.symbol); // 標的
        let matchStrategy = true; // 策略
        if (activeStrategyFilter === 'SCALPER') matchStrategy = t.strategy.includes('Scalper'); // 剝頭皮
        if (activeStrategyFilter === 'STRADDLE') matchStrategy = t.strategy.includes('Straddle'); // 跨式
        return matchSymbol && matchStrategy; // 符合
    }).sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time)); // 排序

    const timeSeries = []; // 時間
    const ddPctSeries = []; // 回撤百分比
    let runningBal = 100000.0; // 淨值
    let peakBal = 100000.0; // 歷史最高點

    if (filteredTrades.length > 0) { // 有交易
        timeSeries.push(filteredTrades[0].entry_time); // 起始
        ddPctSeries.push(0.0); // 起始回撤 0%
        filteredTrades.forEach(t => { // 遍歷
            runningBal += t.pnl_usd; // 累加
            if (runningBal > peakBal) peakBal = runningBal; // 新高
            const ddPct = peakBal > 0 ? -((peakBal - runningBal) / peakBal * 100) : 0; // 回撤百分比 (負值)
            timeSeries.push(t.exit_time); // 時間
            ddPctSeries.push(Math.round(ddPct * 100) / 100); // 記錄
        }); // 結束
    } // 判斷結束

    const trace = { // 軌跡
        x: timeSeries, // 時間
        y: ddPctSeries, // 回撤深度
        mode: 'lines', // 折線
        name: '回撤深度 (%)', // 名稱
        line: { color: '#ff1744', width: 2.0 }, // 紅線
        fill: 'tozeroy', // 填至 0% 線
        fillcolor: 'rgba(255, 23, 68, 0.2)' // 半透明紅底
    }; // 軌跡結束

    const layout = { // Layout
        paper_bgcolor: '#131722', plot_bgcolor: '#131722', margin: { l: 70, r: 40, t: 40, b: 40 }, // 背景邊距
        title: { text: '所選組合歷史資金回撤深度圖 (Underwater Drawdown %)', font: { color: '#f0f6fc', family: 'Outfit', size: 16 } }, // 標題
        xaxis: { type: 'date', gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' } }, // X 軸
        yaxis: { gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, ticksuffix: '%', zeroline: true, zerolinecolor: 'rgba(255,255,255,0.3)', zerolinewidth: 1.5 }, // Y 軸
        hovermode: 'x unified' // 浮動
    }; // Layout 結束

    Plotly.newPlot('main-plotly-chart', [trace], layout, { responsive: true, displayModeBar: true }); // 渲染
} // renderDrawdownChart 結束

// 渲染歷史交易明細表格 (支援搜尋、過濾、分頁與高亮)
function renderTradesTable() { // 表格渲染函數
    const tbody = document.getElementById('trades-table-body'); // 取得表體 DOM
    const counterEl = document.getElementById('table-trades-counter'); // 取得計數器 DOM
    if (!tbody || !globalData || !globalData.all_trades) return; // 檢查資料

    // 1. 多維度篩選交易記錄
    const filtered = globalData.all_trades.filter(t => { // 遍歷過濾
        // 標的篩選
        if (!selectedSymbols.has(t.symbol)) return false; // 若不在勾選中則排除
        // 策略篩選
        if (activeStrategyFilter === 'SCALPER' && !t.strategy.includes('Scalper')) return false; // 排除非剝頭皮
        if (activeStrategyFilter === 'STRADDLE' && !t.strategy.includes('Straddle')) return false; // 排除非跨式
        // 交易方向篩選
        if (tableTradeType === 'BUY' && !t.type.includes('Buy')) return false; // 僅買進
        if (tableTradeType === 'SELL' && !t.type.includes('Sell')) return false; // 僅賣出
        // 勝負損益篩選
        if (tableTradeOutcome === 'WIN' && !t.win) return false; // 僅獲利
        if (tableTradeOutcome === 'LOSS' && t.win) return false; // 僅虧損
        // 關鍵字搜尋 (標的 / 策略 / 出場原因)
        if (tableSearchQuery) { // 若有搜尋字
            const matchSym = t.symbol.toLowerCase().includes(tableSearchQuery); // 標的匹配
            const matchReason = t.exit_reason.toLowerCase().includes(tableSearchQuery); // 原因匹配
            const matchStrat = t.strategy.toLowerCase().includes(tableSearchQuery); // 策略匹配
            if (!matchSym && !matchReason && !matchStrat) return false; // 皆不符則排除
        } // 搜尋結束
        return true; // 符合保留
    }); // 過濾結束

    // 2. 更新筆數計數器
    counterEl.textContent = `顯示 ${filtered.length} / ${globalData.all_trades.length} 筆交易明細`; // 填入計數

    // 3. 分頁計算
    const totalPages = Math.ceil(filtered.length / pageSize) || 1; // 計算總頁數
    if (currentPage > totalPages) currentPage = totalPages; // 校正當前頁碼
    const startIndex = (currentPage - 1) * pageSize; // 起始索引
    const endIndex = Math.min(startIndex + pageSize, filtered.length); // 結束索引
    const pageTrades = filtered.slice(startIndex, endIndex); // 抽取當頁資料

    // 4. 渲染表格列 HTML
    if (pageTrades.length === 0) { // 無資料
        tbody.innerHTML = `<tr><td colspan="13" style="text-align:center; padding:30px; color:var(--text-muted);">無符合當前篩選條件之交易紀錄</td></tr>`; // 顯示空表提示
    } else { // 有資料
        tbody.innerHTML = pageTrades.map(t => { // 遍歷生成 HTML 列
            const isWin = t.win; // 是否獲利
            const pnlClass = isWin ? 'val-bull' : 'val-bear'; // 損益顏色
            const typeBadge = t.type.includes('Buy') ? '<span class="badge-bull">買進 (Buy)</span>' : '<span class="badge-bear">賣出 (Sell)</span>'; // 方向標籤
            const stratBadge = t.strategy.includes('Scalper') ? '<span class="badge-scalper">5m 剝頭皮</span>' : '<span class="badge-straddle">5m 跨式</span>'; // 策略標籤
            const symColor = symbolColors[t.symbol] || '#fff'; // 貨幣對顏色
            const isHighlight = highlightedTradeId === t.global_id ? 'style="background:rgba(41,182,246,0.15);"' : ''; // 高亮樣式

            return `
                <tr ${isHighlight} onclick="focusTradeOnChart('${t.symbol}', ${t.global_id})">
                    <td style="font-family:var(--font-mono); color:var(--text-secondary); font-size:12px;">#${t.global_id}</td>
                    <td>${stratBadge}</td>
                    <td><strong style="color:${symColor}; font-family:var(--font-mono);">${t.symbol}</strong></td>
                    <td>${typeBadge}</td>
                    <td style="font-family:var(--font-mono);">${t.lot_size}</td>
                    <td style="font-family:var(--font-mono); font-size:12px; color:var(--text-secondary);">${t.entry_time}</td>
                    <td style="font-family:var(--font-mono);">${t.entry_price}</td>
                    <td style="font-family:var(--font-mono); font-size:12px; color:var(--text-secondary);">${t.exit_time}</td>
                    <td style="font-family:var(--font-mono);">${t.exit_price}</td>
                    <td><strong class="${pnlClass}" style="font-family:var(--font-mono);">${t.pnl_usd >= 0 ? '+' : ''}$${t.pnl_usd.toFixed(2)}</strong></td>
                    <td class="${pnlClass}" style="font-family:var(--font-mono);">${t.pnl_pips >= 0 ? '+' : ''}${t.pnl_pips.toFixed(1)}p</td>
                    <td style="font-size:12px; color:var(--text-secondary);">${t.exit_reason}</td>
                    <td style="font-family:var(--font-mono); font-size:12px; color:var(--text-muted);">${t.duration_mins} 分鐘 (${t.duration_bars} 根)</td>
                </tr>
            `; // 回傳一列 HTML
        }).join(''); // 串接結束
    } // 判斷結束

    // 5. 渲染分頁按鈕控制項
    renderPaginationControls(totalPages); // 生成分頁按鈕
} // renderTradesTable 結束

// 渲染分頁導航按鈕
function renderPaginationControls(totalPages) { // 分頁按鈕生成函數
    const container = document.getElementById('pagination-buttons-container'); // 取得容器 DOM
    if (!container) return; // 檢查容器

    let html = `
        <button class="page-btn" onclick="changeTablePage(1)" ${currentPage === 1 ? 'disabled' : ''}>« 首頁</button>
        <button class="page-btn" onclick="changeTablePage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>‹ 上一頁</button>
        <span style="font-size:12px; color:var(--text-secondary); font-family:var(--font-mono); padding:0 8px;">第 ${currentPage} / ${totalPages} 頁</span>
        <button class="page-btn" onclick="changeTablePage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>下一頁 ›</button>
        <button class="page-btn" onclick="changeTablePage(${totalPages})" ${currentPage === totalPages ? 'disabled' : ''}>末頁 »</button>
    `; // 分頁 HTML

    container.innerHTML = html; // 填入容器
} // renderPaginationControls 結束

// 表格分頁切換
function changeTablePage(page) { // 分頁跳轉函數
    currentPage = page; // 更新當前頁碼
    renderTradesTable(); // 重新渲染表格
} // changeTablePage 結束

// 點擊交易明細列自動聚焦切換至該標的 K 線圖
function focusTradeOnChart(sym, tradeId) { // 聚焦交易函數
    highlightedTradeId = tradeId; // 記錄高亮 ID
    candlestickSymbol = sym; // 切換 K 線標的
    const selectEl = document.getElementById('candlestick-symbol-select'); // 取得下拉
    if (selectEl) selectEl.value = sym; // 更新下拉

    // 自動切換分頁至 K 線圖
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active')); // 移除啟用
    const candleTabBtn = document.querySelector('.tab-btn[data-chart="candlestick-signals"]'); // 取得 K 線按鈕
    if (candleTabBtn) candleTabBtn.classList.add('active'); // 啟用
    activeChartTab = 'candlestick-signals'; // 設定分頁變數
    document.getElementById('candlestick-options').style.display = 'flex'; // 顯示下拉

    renderMainChart(); // 重新繪製 K 線圖
    renderTradesTable(); // 重新高亮該列
    
    // 平滑滾動至圖表區塊
    document.querySelector('.chart-section').scrollIntoView({ behavior: 'smooth' }); // 平滑滾動
} // focusTradeOnChart 結束

// 匯出當前篩選之所有交易明細 CSV 檔案
function exportFilteredTradesCSV() { // CSV 下載函數
    if (!globalData || !globalData.all_trades) return; // 檢查資料

    // 取得當前篩選下的全部交易
    const filtered = globalData.all_trades.filter(t => { // 過濾
        if (!selectedSymbols.has(t.symbol)) return false; // 排除
        if (activeStrategyFilter === 'SCALPER' && !t.strategy.includes('Scalper')) return false; // 排除
        if (activeStrategyFilter === 'STRADDLE' && !t.strategy.includes('Straddle')) return false; // 排除
        if (tableTradeType === 'BUY' && !t.type.includes('Buy')) return false; // 排除
        if (tableTradeType === 'SELL' && !t.type.includes('Sell')) return false; // 排除
        if (tableTradeOutcome === 'WIN' && !t.win) return false; // 排除
        if (tableTradeOutcome === 'LOSS' && t.win) return false; // 排除
        if (tableSearchQuery) { // 關鍵字
            const matchSym = t.symbol.toLowerCase().includes(tableSearchQuery); // 標的
            const matchReason = t.exit_reason.toLowerCase().includes(tableSearchQuery); // 原因
            const matchStrat = t.strategy.toLowerCase().includes(tableSearchQuery); // 策略
            if (!matchSym && !matchReason && !matchStrat) return false; // 排除
        } // 結束
        return true; // 保留
    }); // 過濾結束

    if (filtered.length === 0) { // 無資料
        alert('當前無符合條件之交易紀錄可供匯出！'); // 提示
        return; // 終止
    } // 判斷結束

    // 構建 CSV 內容
    const headers = ["序號", "策略名稱", "貨幣對", "交易方向", "手數", "進場時間(UTC)", "進場價", "出場時間(UTC)", "出場價", "淨損益(USD)", "獲利點數(pips)", "報酬率(%)", "出場原因", "持倉分鐘數"]; // 表頭
    const csvRows = [headers.join(',')]; // 寫入表頭

    filtered.forEach(t => { // 遍歷交易
        const row = [ // 單列資料
            t.global_id, // 序號
            `"${t.strategy}"`, // 策略
            t.symbol, // 標的
            `"${t.type}"`, // 方向
            t.lot_size, // 手數
            t.entry_time, // 進場
            t.entry_price, // 進價
            t.exit_time, // 出場
            t.exit_price, // 出價
            t.pnl_usd, // 淨利
            t.pnl_pips, // 點數
            t.return_pct, // 報酬
            `"${t.exit_reason}"`, // 原因
            t.duration_mins // 分鐘
        ]; // 單列結束
        csvRows.push(row.join(',')); // 加入陣列
    }); // 遍歷結束

    // 建立 Blob 並觸發瀏覽器下載
    const csvContent = "\uFEFF" + csvRows.join('\n'); // 加入 UTF-8 BOM 防亂碼
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' }); // 建立 Blob
    const url = URL.createObjectURL(blob); // 生成下載網址
    const link = document.createElement('a'); // 建立 a 標籤
    link.setAttribute('href', url); // 設定網址
    link.setAttribute('download', `5m_Trading_Trades_${new Date().toISOString().substring(0, 10)}.csv`); // 設定下載檔名
    document.body.appendChild(link); // 加入 DOM
    link.click(); // 觸發點擊下載
    document.body.removeChild(link); // 移除 DOM
} // exportFilteredTradesCSV 結束
