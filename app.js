// 全域資料與狀態管理變數
let globalData = null; // 策略結果 JSON 原始數據
let selectedSymbols = new Set(); // 當前使用者勾選的貨幣對集合
let activeStrategyFilter = 'ALL'; // 當前策略過濾 ('ALL', 'SCALPER', 'STRADDLE')
let activeChartTab = 'combined-equity'; // 當前啟用的圖表分頁標籤
let candlestickSymbol = 'NZDCAD'; // 當前 K 線圖所選取的貨幣對標的
let currentPage = 1; // 當前歷史交易表格分頁
let pageSize = 15; // 每頁顯示交易筆數
let tableSearchQuery = ''; // 交易明細搜尋關鍵字
let tableTradeType = 'ALL'; // 交易明細方向過濾 ('ALL', 'BUY', 'SELL')
let tableTradeOutcome = 'ALL'; // 交易明細勝負過濾 ('ALL', 'WIN', 'LOSS')
let highlightedTradeId = null; // 當前點擊聚焦高亮的交易序號

// 貨幣對專屬圖表配色調色盤
const symbolColors = { // 配色字典
    "NZDCAD": "#b388ff", // 亮紫色
    "AUDNZD": "#00e676", // 翡翠綠
    "AUDCAD": "#29b6f6", // 科技天藍
    "EURGBP": "#ffa726", // 亮橘色
    "EURCHF": "#26a69a", // 松石綠
    "EURUSD": "#ec407a", // 霓虹粉紅
    "EURJPY": "#ff5252"  // 珊瑚紅
}; // 配色結束

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

        // 初始化商品勾選集合 (預設全選所有商品)
        const allSyms = Object.keys(globalData.symbols_meta); // 取得全部貨幣對
        selectedSymbols = new Set(allSyms); // 放入集合
        if (allSyms.length > 0) candlestickSymbol = allSyms[0]; // 設定預設 K 線標的

        // 渲染各區塊內容
        renderHeaderStatus(); // 渲染頂部時間與系統狀態
        renderMarketTickers(); // 渲染即時行情小卡
        renderAssetCheckboxes(); // 渲染多商品勾選控制卡片
        recalculateAndRenderKPIs(); // 根據當前勾選重算並渲染 KPI 卡片
        renderMainChart(); // 渲染 Plotly 主圖表
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
        candlestickSymbol = e.target.value; // 更新當前標的
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
            sessionTag = '<span class="badge-scalper">夜間收租開倉中</span>'; // 夜間標籤
        } else if (item.is_straddle_session && item.supports_straddle) { // 處於日間跨式時段
            sessionTag = '<span class="badge-straddle">日間跨式開倉中</span>'; // 日間標籤
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
                    <span>RSI: <strong>${item.current_rsi}</strong></span>
                    <span>Z: <strong>${item.current_zscore > 0 ? '+' : ''}${item.current_zscore}σ</strong></span>
                </div>
                <div style="margin-top:2px;">${sessionTag}</div>
            </div>
        `; // 回傳卡片 HTML
    }).join(''); // 串接結束
} // renderMarketTickers 結束

// 渲染多商品勾選控制面板 Checkboxes
function renderAssetCheckboxes() { // 勾選卡片生成函數
    const container = document.getElementById('asset-checkbox-container'); // 取得容器
    if (!globalData || !globalData.symbols_meta) return; // 檢查資料

    const meta = globalData.symbols_meta; // 取得商品資訊
    container.innerHTML = Object.keys(meta).map(sym => { // 遍歷生成 Checkbox
        const item = meta[sym]; // 商品資料
        const isChecked = selectedSymbols.has(sym); // 是否已勾選
        const activeClass = isChecked ? 'checked' : ''; // 樣式類別

        // 策略標籤 HTML
        let tagsHtml = ''; // 標籤字串
        if (item.supports_scalper) tagsHtml += '<span class="badge-scalper">5m 剝頭皮</span>'; // 剝頭皮
        if (item.supports_straddle) tagsHtml += '<span class="badge-straddle">5m 跨式</span>'; // 跨式

        return `
            <div class="asset-checkbox-item ${activeClass}" data-symbol="${sym}" onclick="toggleSymbolSelection('${sym}')">
                <div class="asset-check-left">
                    <div class="custom-checkbox"></div>
                    <span class="asset-symbol-name" style="color:${symbolColors[sym] || '#fff'};">${sym}</span>
                </div>
                <div class="asset-strategy-tags">
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
    document.getElementById('candlestick-symbol-select').value = sym; // 更新下拉選單
    
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
    document.getElementById('btn-toggle-all').classList.remove('active'); // 移除
    document.getElementById('btn-toggle-scalper').classList.remove('active'); // 移除
    document.getElementById('btn-toggle-straddle').classList.remove('active'); // 移除

    if (activeStrategyFilter === 'ALL' && selectedSymbols.size === Object.keys(globalData.symbols_meta).length) { // 符合全部
        document.getElementById('btn-toggle-all').classList.add('active'); // 啟用全部
    } else if (activeStrategyFilter === 'SCALPER') { // 符合剝頭皮
        document.getElementById('btn-toggle-scalper').classList.add('active'); // 啟用剝頭皮
    } else if (activeStrategyFilter === 'STRADDLE') { // 符合跨式
        document.getElementById('btn-toggle-straddle').classList.add('active'); // 啟用跨式
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
    const activeCountEl = document.getElementById('kpi-active-positions-count'); // 活躍筆數 DOM
    const activeDetailEl = document.getElementById('kpi-active-positions-detail'); // 細節容器 DOM

    if (activeList.length === 0) { // 當前無持倉
        activeCountEl.textContent = '0 筆 (空手等待)'; // 顯示空手
        activeCountEl.className = 'card-main-val val-neutral'; // 預設白字
        activeDetailEl.innerHTML = '<span>零隔夜狀態: <strong class="val-bull">無隔夜風險</strong></span>'; // 顯示無風險
    } else { // 當前持有活躍部位
        const totalUnrealized = activeList.reduce((acc, p) => acc + (p.unrealized_pnl_usd || 0), 0); // 累計未實現損益
        activeCountEl.textContent = `${activeList.length} 筆即時持倉`; // 顯示筆數
        activeCountEl.className = 'card-main-val val-blue'; // 亮藍色強調
        activeDetailEl.innerHTML = `
            <span>未實現損益: <strong class="${totalUnrealized >= 0 ? 'val-bull' : 'val-bear'}">${totalUnrealized >= 0 ? '+' : ''}$${totalUnrealized.toFixed(2)}</strong></span>
            <span>持倉標的: <strong class="val-purple">${activeList.map(p => p.symbol).join(', ')}</strong></span>
        `; // 填入持倉細節
    } // 活躍部位判斷結束
} // recalculateAndRenderKPIs 結束

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

// 繪製分頁 1：組合累積資金權益曲線 (隨勾選商品動態重算聚合)
function renderCombinedEquityChart() { // 組合權益圖繪製函數
    const filteredTrades = globalData.all_trades.filter(t => { // 過濾交易
        const matchSymbol = selectedSymbols.has(t.symbol); // 標的符合
        let matchStrategy = true; // 策略符合
        if (activeStrategyFilter === 'SCALPER') matchStrategy = t.strategy.includes('Scalper'); // 剝頭皮
        if (activeStrategyFilter === 'STRADDLE') matchStrategy = t.strategy.includes('Straddle'); // 跨式
        return matchSymbol && matchStrategy; // 兩者符合
    }).sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time)); // 依出場時間正序

    // 建立時間序列節點
    const timeSeries = []; // 時間陣列
    const balanceSeries = []; // 權益陣列
    let currentBal = 100000.0; // 初始本金 $100,000

    if (filteredTrades.length > 0) { // 若有交易
        timeSeries.push(filteredTrades[0].entry_time); // 起始時間點
        balanceSeries.push(currentBal); // 起始本金
        filteredTrades.forEach(t => { // 遍歷交易
            currentBal += t.pnl_usd; // 累加淨值
            timeSeries.push(t.exit_time); // 記錄時間
            balanceSeries.push(Math.round(currentBal * 100) / 100); // 記錄權益
        }); // 遍歷結束
    } else { // 無交易
        timeSeries.push(new Date().toISOString().substring(0, 19).replace('T', ' ')); // 當前時間
        balanceSeries.push(100000.0); // 本金
    } // 判斷結束

    const trace = { // 定義曲線軌跡
        x: timeSeries, // X 軸時間
        y: balanceSeries, // Y 軸權益
        mode: 'lines', // 折線模式
        name: '篩選組合資金權益 ($100k 本金)', // 圖例名稱
        line: { color: '#00e676', width: 2.8 }, // 亮綠色線條
        fill: 'tozeroy', // 填充至底部
        fillcolor: 'rgba(0, 230, 118, 0.08)' // 淡綠半透明填充
    }; // 軌跡結束

    const layout = { // 定義圖表面版樣式
        paper_bgcolor: '#131722', plot_bgcolor: '#131722', margin: { l: 60, r: 40, t: 40, b: 40 }, // 背景色與邊距
        title: { text: `所選 ${selectedSymbols.size} 款商品之累計權益曲線 (固定 1.0 Lot / 零隔夜)`, font: { color: '#f0f6fc', family: 'Outfit', size: 16 } }, // 標題
        xaxis: { type: 'date', gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' } }, // X 軸
        yaxis: { gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, tickprefix: '$' }, // Y 軸
        hovermode: 'x unified', // 統一浮動標籤
        legend: { orientation: 'h', y: 1.1, font: { color: '#8b949e' } } // 圖例
    }; // 面版結束

    Plotly.newPlot('main-plotly-chart', [trace], layout, { responsive: true, displayModeBar: true }); // 渲染 Plotly 圖表
} // renderCombinedEquityChart 結束

// 繪製分頁 2：多商品個別資金曲線對比圖
function renderComparativeEquityChart() { // 多商品比較圖繪製函數
    const traces = []; // 軌跡陣列

    selectedSymbols.forEach(sym => { // 遍歷已勾選的商品
        // 抓取該標的的交易並重建該標的的權益曲線
        const symTrades = globalData.all_trades.filter(t => t.symbol === sym).sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time)); // 依時間排序
        if (symTrades.length === 0) return; // 無交易跳過

        const tTimes = [symTrades[0].entry_time]; // 時間
        const tBals = [100000.0]; // 權益
        let rBal = 100000.0; // 淨值

        symTrades.forEach(t => { // 遍歷
            rBal += t.pnl_usd; // 累加
            tTimes.push(t.exit_time); // 時間
            tBals.push(Math.round(rBal * 100) / 100); // 權益
        }); // 結束

        traces.push({ // 加入軌跡
            x: tTimes, // 時間
            y: tBals, // 權益
            mode: 'lines', // 折線
            name: `${sym} (${symTrades.length} 筆交易)`, // 名稱
            line: { color: symbolColors[sym] || '#fff', width: 2.2 } // 專屬顏色
        }); // 結束
    }); // 遍歷結束

    const layout = { // 面版樣式
        paper_bgcolor: '#131722', plot_bgcolor: '#131722', margin: { l: 60, r: 40, t: 40, b: 40 }, // 背景色
        title: { text: '各貨幣對獨立資金成長曲線比較 (初始本金 $100,000)', font: { color: '#f0f6fc', family: 'Outfit', size: 16 } }, // 標題
        xaxis: { type: 'date', gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' } }, // X 軸
        yaxis: { gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, tickprefix: '$' }, // Y 軸
        hovermode: 'x unified', // 統一浮動
        legend: { orientation: 'h', y: 1.12, font: { color: '#8b949e', size: 11 } } // 圖例
    }; // 面版結束

    Plotly.newPlot('main-plotly-chart', traces, layout, { responsive: true, displayModeBar: true }); // 渲染圖表
} // renderComparativeEquityChart 結束

// 繪製分頁 3：5m 即時 K 線圖、布林通道 / Z-Score 與進出場買賣標記
function renderCandlestickChart(symbol) { // 5m K 線與訊號圖繪製函數
    if (!globalData || !globalData.chart_data || !globalData.chart_data[symbol]) return; // 檢查資料

    const cData = globalData.chart_data[symbol]; // 取得圖表數據
    const symTrades = globalData.all_trades.filter(t => t.symbol === symbol); // 取得該標的所有歷史交易

    // 1. 5m 主 K 線軌跡
    const candleTrace = { // K 線
        x: cData.timestamps, open: cData.open, high: cData.high, low: cData.low, close: cData.close, // 價格
        type: 'candlestick', name: `${symbol} 5m K線`, // 類型與名稱
        increasing: { line: { color: '#00e676', width: 1 }, fillcolor: '#00e676' }, // 陽線亮綠
        decreasing: { line: { color: '#ff1744', width: 1 }, fillcolor: '#ff1744' }, // 陰線亮紅
        xaxis: 'x', yaxis: 'y' // 主座標軸
    }; // K 線結束

    // 2. 布林中軌
    const bbMidTrace = { // 中軌
        x: cData.timestamps, y: cData.bb_mid, mode: 'lines', name: 'BB Mid (SMA 20)', // 中軌
        line: { color: '#ffa726', width: 1.2 }, xaxis: 'x', yaxis: 'y' // 橘色線
    }; // 中軌結束

    // 3. 布林上軌 (2.2σ)
    const bbUpperTrace = { // 上軌
        x: cData.timestamps, y: cData.bb_upper, mode: 'lines', name: 'BB Upper (2.2σ)', // 上軌
        line: { color: '#b388ff', width: 1.2, dash: 'dash' }, xaxis: 'x', yaxis: 'y' // 紫色虛線
    }; // 上軌結束

    // 4. 布林下軌 (2.2σ)
    const bbLowerTrace = { // 下軌
        x: cData.timestamps, y: cData.bb_lower, mode: 'lines', name: 'BB Lower (2.2σ)', // 下軌
        line: { color: '#29b6f6', width: 1.2, dash: 'dash' }, xaxis: 'x', yaxis: 'y' // 藍色虛線
    }; // 下軌結束

    // 5. 構建進出場標記點 (Annotations / Scatter)
    const buyEntriesX = [], buyEntriesY = [], buyText = []; // 買進點
    const sellEntriesX = [], sellEntriesY = [], sellText = []; // 賣出點
    const exitsX = [], exitsY = [], exitsText = []; // 出場點

    // 過濾近期的交易顯示在 K 線上
    const minTime = cData.timestamps[0]; // 圖表最左側時間
    symTrades.forEach(t => { // 遍歷交易
        if (t.entry_time >= minTime) { // 若進場時間在圖表範圍內
            if (t.type.includes('Buy')) { // 買進多單
                buyEntriesX.push(t.entry_time); // 時間
                buyEntriesY.push(t.entry_price); // 價格
                buyText.push(`[多單進場 #${t.trade_id}] ${t.strategy}<br>價格: ${t.entry_price}`); // 說明文字
            } else { // 賣出空單
                sellEntriesX.push(t.entry_time); // 時間
                sellEntriesY.push(t.entry_price); // 價格
                sellText.push(`[空單進場 #${t.trade_id}] ${t.strategy}<br>價格: ${t.entry_price}`); // 說明文字
            } // 判斷結束

            exitsX.push(t.exit_time); // 出場時間
            exitsY.push(t.exit_price); // 出場價格
            exitsText.push(`[平倉結算 #${t.trade_id}] ${t.exit_reason}<br>損益: ${t.pnl_usd >= 0 ? '+' : ''}$${t.pnl_usd} (${t.pnl_pips} pips)`); // 說明文字
        } // 判斷結束
    }); // 遍歷結束

    // 買進進場綠色向上三角
    const buyScatter = { // 買進標記
        x: buyEntriesX, y: buyEntriesY, mode: 'markers', name: '買進進場 (Buy Entry)', // 標記
        marker: { symbol: 'triangle-up', size: 12, color: '#00e676', line: { color: '#ffffff', width: 1 } }, // 向上綠三角
        text: buyText, hoverinfo: 'text', xaxis: 'x', yaxis: 'y' // 提示
    }; // 標記結束

    // 賣出進場紅色向下三角
    const sellScatter = { // 賣出標記
        x: sellEntriesX, y: sellEntriesY, mode: 'markers', name: '賣出進場 (Sell Entry)', // 標記
        marker: { symbol: 'triangle-down', size: 12, color: '#ff1744', line: { color: '#ffffff', width: 1 } }, // 向下紅三角
        text: sellText, hoverinfo: 'text', xaxis: 'x', yaxis: 'y' // 提示
    }; // 標記結束

    // 出場平倉圓形圓點
    const exitScatter = { // 出場標記
        x: exitsX, y: exitsY, mode: 'markers', name: '出場平倉 (Exit Close)', // 標記
        marker: { symbol: 'circle', size: 8, color: '#ffd54f', line: { color: '#ffffff', width: 1 } }, // 金色圓圈
        text: exitsText, hoverinfo: 'text', xaxis: 'x', yaxis: 'y' // 提示
    }; // 標記結束

    // 下方子圖：RSI (0-100) 與 Z-Score 指標
    const rsiTrace = { // RSI 軌跡
        x: cData.timestamps, y: cData.rsi, mode: 'lines', name: 'RSI(14)', // RSI
        line: { color: '#b388ff', width: 1.5 }, xaxis: 'x', yaxis: 'y2' // 放置於 Y2 子圖
    }; // RSI 結束

    const traces = [candleTrace, bbMidTrace, bbUpperTrace, bbLowerTrace, buyScatter, sellScatter, exitScatter, rsiTrace]; // 整合軌跡

    const layout = { // 雙子圖版面配置
        paper_bgcolor: '#131722', plot_bgcolor: '#131722', margin: { l: 60, r: 60, t: 40, b: 30 }, // 邊距
        title: { text: `[${symbol}] 5 分鐘高頻 K 線、布林通道與歷史訊號標記`, font: { color: '#f0f6fc', family: 'Outfit', size: 16 } }, // 標題
        xaxis: { type: 'date', rangeslider: { visible: false }, gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' } }, // X 軸
        yaxis: { domain: [0.32, 1.0], gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, side: 'right' }, // 主 K 線 Y 軸
        yaxis2: { domain: [0.0, 0.25], gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, side: 'right', range: [10, 90] }, // RSI 子圖 Y 軸
        hovermode: 'closest', // 鄰近懸停
        legend: { orientation: 'h', y: 1.12, font: { color: '#8b949e', size: 11 } } // 圖例
    }; // 版面結束

    Plotly.newPlot('main-plotly-chart', traces, layout, { responsive: true, displayModeBar: true }); // 渲染圖表
} // renderCandlestickChart 結束

// 繪製分頁 4：歷史回撤深度圖 (Underwater Drawdown)
function renderDrawdownChart() { // 回撤圖繪製函數
    const filteredTrades = globalData.all_trades.filter(t => { // 過濾交易
        const matchSymbol = selectedSymbols.has(t.symbol); // 標的符合
        let matchStrategy = true; // 策略符合
        if (activeStrategyFilter === 'SCALPER') matchStrategy = t.strategy.includes('Scalper'); // 剝頭皮
        if (activeStrategyFilter === 'STRADDLE') matchStrategy = t.strategy.includes('Straddle'); // 跨式
        return matchSymbol && matchStrategy; // 兩者符合
    }).sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time)); // 排序

    const tTimes = []; // 時間
    const ddSeries = []; // 回撤百分比
    let rBal = 100000.0; // 淨值
    let peak = 100000.0; // 峰值

    filteredTrades.forEach(t => { // 遍歷交易
        rBal += t.pnl_usd; // 累加淨值
        if (rBal > peak) peak = rBal; // 更新峰值
        const ddPct = peak > 0 ? -((peak - rBal) / peak * 100) : 0; // 回撤百分比 (負值)
        tTimes.push(t.exit_time); // 時間
        ddSeries.push(Math.round(ddPct * 100) / 100); // 記錄
    }); // 結束

    const trace = { // 軌跡
        x: tTimes, y: ddSeries, mode: 'lines', name: '回撤百分比 (Drawdown %)', // 名稱
        line: { color: '#ff1744', width: 2.0 }, fill: 'tozeroy', fillcolor: 'rgba(255, 23, 68, 0.15)' // 紅色水下填充
    }; // 軌跡結束

    const layout = { // 版面
        paper_bgcolor: '#131722', plot_bgcolor: '#131722', margin: { l: 60, r: 40, t: 40, b: 40 }, // 邊距
        title: { text: '所選組合水下歷史回撤深度圖 (Underwater Drawdown %)', font: { color: '#f0f6fc', family: 'Outfit', size: 16 } }, // 標題
        xaxis: { type: 'date', gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' } }, // X 軸
        yaxis: { gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, ticksuffix: '%' }, // Y 軸
        hovermode: 'x unified' // 統一懸停
    }; // 版面結束

    Plotly.newPlot('main-plotly-chart', [trace], layout, { responsive: true, displayModeBar: true }); // 渲染圖表
} // renderDrawdownChart 結束

// 渲染歷史交易紀錄表格清單 (含多條件搜尋、篩選與分頁)
function renderTradesTable() { // 表格渲染函數
    if (!globalData || !globalData.all_trades) return; // 檢查資料

    // 1. 多條件過濾交易
    const filtered = globalData.all_trades.filter(t => { // 篩選
        // 勾選商品過濾
        if (!selectedSymbols.has(t.symbol)) return false; // 未勾選排除
        // 策略模式過濾
        if (activeStrategyFilter === 'SCALPER' && !t.strategy.includes('Scalper')) return false; // 非剝頭皮排除
        if (activeStrategyFilter === 'STRADDLE' && !t.strategy.includes('Straddle')) return false; // 非跨式排除
        // 交易方向過濾
        if (tableTradeType === 'BUY' && !t.type.includes('Buy')) return false; // 非多單排除
        if (tableTradeType === 'SELL' && !t.type.includes('Sell')) return false; // 非空單排除
        // 勝負過濾
        if (tableTradeOutcome === 'WIN' && !t.win) return false; // 非獲利排除
        if (tableTradeOutcome === 'LOSS' && t.win) return false; // 非虧損排除
        // 關鍵字搜尋過濾 (標的、策略、出場原因)
        if (tableSearchQuery) { // 若有搜尋字
            const str = `${t.symbol} ${t.strategy} ${t.exit_reason} ${t.type}`.toLowerCase(); // 拼合字串
            if (!str.includes(tableSearchQuery)) return false; // 不包含排除
        } // 搜尋結束
        return true; // 符合保留
    }); // 篩選結束

    // 更新交易總筆數計數器
    document.getElementById('table-trades-counter').textContent = `顯示 ${filtered.length} / ${globalData.all_trades.length} 筆歷史紀錄`; // 填入筆數

    // 2. 分頁計算
    const totalRecords = filtered.length; // 總筆數
    const totalPages = Math.ceil(totalRecords / pageSize) || 1; // 總頁數
    if (currentPage > totalPages) currentPage = totalPages; // 避免頁碼超出
    if (currentPage < 1) currentPage = 1; // 避免頁碼小於 1

    const startIndex = (currentPage - 1) * pageSize; // 起始索引
    const endIndex = Math.min(startIndex + pageSize, totalRecords); // 結束索引
    const pageRecords = filtered.slice(startIndex, endIndex); // 當前頁切片資料

    // 3. 渲染 tbody HTML
    const tbody = document.getElementById('trades-table-body'); // 取得 tbody DOM
    if (pageRecords.length === 0) { // 若無符合資料
        tbody.innerHTML = `<tr><td colspan="13" style="text-align:center; padding:30px; color:var(--text-secondary);">查無符合條件之歷史交易紀錄</td></tr>`; // 顯示無資料
    } else { // 有資料
        tbody.innerHTML = pageRecords.map(t => { // 遍歷生成 TR
            const isBuy = t.type.includes('Buy'); // 是否為買單
            const isWin = t.win; // 是否獲利
            const typeBadge = isBuy ? `<span class="badge-buy">${t.type}</span>` : `<span class="badge-sell">${t.type}</span>`; // 方向標籤
            const pnlClass = isWin ? 'val-bull' : 'val-bear'; // 損益顏色
            const pnlPrefix = t.pnl_usd >= 0 ? '+' : ''; // 正號
            const isHighlighted = (highlightedTradeId === t.global_id) ? 'active-highlight' : ''; // 是否高亮

            return `
                <tr class="${isHighlighted}" onclick="focusTradeOnChart('${t.symbol}', ${t.global_id})">
                    <td style="color:var(--text-secondary);">${t.global_id || t.trade_id}</td>
                    <td style="font-size:12px; color:${t.strategy.includes('Scalper') ? 'var(--color-purple)' : 'var(--color-accent)'}; font-weight:600;">${t.strategy}</td>
                    <td style="font-weight:700; color:${symbolColors[t.symbol] || '#fff'};">${t.symbol}</td>
                    <td>${typeBadge}</td>
                    <td>${t.lot_size}</td>
                    <td style="font-size:12px; color:var(--text-secondary);">${t.entry_time}</td>
                    <td style="font-weight:600;">${t.entry_price}</td>
                    <td style="font-size:12px; color:var(--text-secondary);">${t.exit_time}</td>
                    <td style="font-weight:600;">${t.exit_price}</td>
                    <td class="${pnlClass}" style="font-weight:700;">${pnlPrefix}$${t.pnl_usd.toFixed(2)}</td>
                    <td class="${pnlClass}">${pnlPrefix}${t.pnl_pips}</td>
                    <td style="font-size:12px; color:var(--text-secondary);">${t.exit_reason}</td>
                    <td style="font-size:12px; color:var(--text-secondary);">${t.duration_mins} 分 (${t.duration_bars} 根)</td>
                </tr>
            `; // 回傳單列 HTML
        }).join(''); // 串接結束
    } // 判斷結束

    // 4. 渲染分頁按鈕群
    renderPaginationButtons(totalPages); // 呼叫分頁生成函數
} // renderTradesTable 結束

// 渲染分頁控制按鈕
function renderPaginationButtons(totalPages) { // 分頁按鈕生成函數
    const container = document.getElementById('pagination-buttons-container'); // 取得容器 DOM
    let html = ''; // 按鈕 HTML

    // 首頁按鈕
    html += `<button class="page-btn" ${currentPage === 1 ? 'disabled' : ''} onclick="changePage(1)">«</button>`; // 首頁
    // 上一頁按鈕
    html += `<button class="page-btn" ${currentPage === 1 ? 'disabled' : ''} onclick="changePage(${currentPage - 1})">‹</button>`; // 上一頁

    // 計算顯示的頁碼範圍 (最多顯示 5 個數字)
    let startPage = Math.max(1, currentPage - 2); // 起始頁
    let endPage = Math.min(totalPages, startPage + 4); // 結束頁
    if (endPage - startPage < 4) startPage = Math.max(1, endPage - 4); // 補足 5 頁

    for (let p = startPage; p <= endPage; p++) { // 遍歷頁碼
        const activeClass = (p === currentPage) ? 'active' : ''; // 作用中樣式
        html += `<button class="page-btn ${activeClass}" onclick="changePage(${p})">${p}</button>`; // 數字按鈕
    } // 遍歷結束

    // 下一頁按鈕
    html += `<button class="page-btn" ${currentPage === totalPages ? 'disabled' : ''} onclick="changePage(${currentPage + 1})">›</button>`; // 下一頁
    // 末頁按鈕
    html += `<button class="page-btn" ${currentPage === totalPages ? 'disabled' : ''} onclick="changePage(${totalPages})">»</button>`; // 末頁

    container.innerHTML = html; // 填入容器
} // renderPaginationButtons 結束

// 切換頁碼函數
function changePage(page) { // 換頁函數
    currentPage = page; // 設定新頁碼
    renderTradesTable(); // 重新渲染表格
} // changePage 結束

// 點擊交易明細行，自動聚焦並切換圖表至該筆交易的 K 線圖
function focusTradeOnChart(symbol, globalId) { // 聚焦交易圖表函數
    highlightedTradeId = globalId; // 記錄高亮序號
    candlestickSymbol = symbol; // 設定 K 線標的
    document.getElementById('candlestick-symbol-select').value = symbol; // 同步下拉選單

    // 自動切換至 K 線圖分頁
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active')); // 清除其他分頁
    const candleTabBtn = document.querySelector('.tab-btn[data-chart="candlestick-signals"]'); // 取得 K 線按鈕
    if (candleTabBtn) candleTabBtn.classList.add('active'); // 設為啟用
    activeChartTab = 'candlestick-signals'; // 設定當前圖表
    document.getElementById('candlestick-options').style.display = 'flex'; // 顯示下拉

    renderMainChart(); // 重新繪製該標的 K 線圖
    renderTradesTable(); // 重新渲染表格以標記高亮列

    // 平滑滾動至圖表區域
    document.querySelector('.chart-section').scrollIntoView({ behavior: 'smooth' }); // 平滑滾動
} // focusTradeOnChart 結束

// 匯出當前篩選之交易明細為 CSV 檔案
function exportFilteredTradesCSV() { // 匯出 CSV 函數
    if (!globalData || !globalData.all_trades) return; // 檢查資料

    // 取得當前篩選的所有交易
    const filtered = globalData.all_trades.filter(t => { // 篩選交易
        if (!selectedSymbols.has(t.symbol)) return false; // 勾選過濾
        if (activeStrategyFilter === 'SCALPER' && !t.strategy.includes('Scalper')) return false; // 剝頭皮
        if (activeStrategyFilter === 'STRADDLE' && !t.strategy.includes('Straddle')) return false; // 跨式
        if (tableTradeType === 'BUY' && !t.type.includes('Buy')) return false; // 方向
        if (tableTradeType === 'SELL' && !t.type.includes('Sell')) return false; // 方向
        if (tableTradeOutcome === 'WIN' && !t.win) return false; // 勝負
        if (tableTradeOutcome === 'LOSS' && t.win) return false; // 勝負
        if (tableSearchQuery) { // 搜尋
            const str = `${t.symbol} ${t.strategy} ${t.exit_reason} ${t.type}`.toLowerCase(); // 字串
            if (!str.includes(tableSearchQuery)) return false; // 排除
        } // 搜尋結束
        return true; // 符合
    }); // 結束

    if (filtered.length === 0) { // 若無資料
        alert('當前無符合篩選條件的交易紀錄可供匯出！'); // 提示
        return; // 中止
    } // 判斷結束

    // 構建 CSV 表頭與資料列 (加入 UTF-8 BOM 防止 Excel 亂碼)
    const headers = ["序號", "策略名稱", "貨幣對", "交易方向", "手數", "進場時間(UTC)", "進場價格", "出場時間(UTC)", "出場價格", "淨利(USD)", "盈虧點數(pips)", "報酬率(%)", "平倉原因", "持倉分鐘數"]; // 表頭
    const csvRows = [headers.join(',')]; // 加入表頭

    filtered.forEach(t => { // 遍歷資料
        const row = [ // 單列資料
            t.global_id || t.trade_id, // 序號
            `"${t.strategy}"`, // 策略
            t.symbol, // 標的
            `"${t.type}"`, // 方向
            t.lot_size, // 手數
            t.entry_time, // 進場時間
            t.entry_price, // 進場價
            t.exit_time, // 出場時間
            t.exit_price, // 出場價
            t.pnl_usd, // 美金
            t.pnl_pips, // 點數
            t.return_pct, // 報酬率
            `"${t.exit_reason}"`, // 原因
            t.duration_mins // 持倉時間
        ]; // 單列結束
        csvRows.push(row.join(',')); // 加入列
    }); // 遍歷結束

    const csvString = '\uFEFF' + csvRows.join('\n'); // 加上 UTF-8 BOM 並以換行連接
    const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' }); // 建立 Blob 物件
    const link = document.createElement('a'); // 建立下載超連結
    const url = URL.createObjectURL(blob); // 建立物件 URL
    link.setAttribute('href', url); // 設定下載連結
    link.setAttribute('download', `5m_Strategy_Trades_Export_${new Date().toISOString().substring(0, 10)}.csv`); // 設定下載檔名
    document.body.appendChild(link); // 加入 DOM
    link.click(); // 觸發點擊下載
    document.body.removeChild(link); // 移除元素
} // exportFilteredTradesCSV 結束
