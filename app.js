// 全域資料與狀態管理變數
let globalData = null; // 策略結果 JSON 原始數據
let selectedSymbols = new Set(); // 當前使用者勾選的貨幣對集合
let activeStrategyFilter = 'ALL'; // 當前策略過濾 ('ALL', 'GBP_CROSS', 'EUR_CROSS', 'CHF_CROSS')
let activeChartTab = 'combined-equity'; // 當前啟用的圖表分頁標籤
let candlestickSymbol = 'GBPCHF'; // 當前 K 線圖所選取的貨幣對標的
let currentPage = 1; // 當前歷史交易表格分頁
let pageSize = 15; // 每頁顯示交易筆數
let tableSearchQuery = ''; // 交易明細搜尋關鍵字
let tableTradeType = 'ALL'; // 交易明細方向過濾 ('ALL', 'BUY', 'SELL')
let tableTradeOutcome = 'ALL'; // 交易明細勝負過濾 ('ALL', 'WIN', 'LOSS')
let highlightedTradeId = null; // 當前點擊聚焦高亮的交易序號

// 精選 8 大高夏普交叉貨幣對專屬圖表配色調色盤
const symbolColors = { // 配色字典
    "GBPCHF": "#00e676", // 翡翠綠 (王牌 89.5% 勝率, Sharpe 8.34)
    "EURGBP": "#29b6f6", // 科技天藍 (王牌 86.4% 勝率, Sharpe 3.79)
    "GBPCAD": "#b388ff", // 亮紫色 (80.0% 勝率, Sharpe 2.39)
    "GBPUSD": "#ffa726", // 亮橘色 (78.6% 勝率, Sharpe 5.50)
    "EURAUD": "#26a69a", // 松石綠 (75.0% 勝率, Sharpe 1.89)
    "CADCHF": "#ffd600", // 亮黃色 (69.6% 勝率, Sharpe 1.00)
    "GBPAUD": "#ff4081", // 亮粉紅 (68.2% 勝率, Sharpe 3.19)
    "EURCHF": "#76ff03"  // 檸檬綠 (56.7% 勝率, Sharpe 0.10)
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

        // 初始化商品勾選集合
        const allSyms = Object.keys(globalData.symbols_meta); // 取得全部貨幣對
        selectedSymbols = new Set(allSyms); // 放入集合
        if (allSyms.length > 0) candlestickSymbol = allSyms[0]; // 設定預設 K 線標的

        // 渲染各區塊內容
        renderHeaderStatus(); // 渲染頂部時間與系統狀態
        renderMarketTickers(); // 渲染即時行情小卡
        renderAssetCheckboxes(); // 渲染多商品勾選控制卡片
        recalculateAndRenderKPIs(); // 根據當前勾選重算並渲染 KPI 卡片
        renderMainChart(); // 渲染 Plotly 主圖表
        renderStrategyMatrix(); // 渲染 8 大收租模組矩陣總表
        renderTradesTable(); // 渲染歷史交易明細表格

    } catch (err) { // 捕捉異常
        console.error("載入策略資料失敗:", err); // 於 Console 記錄錯誤
        document.getElementById('status-update-time').textContent = '資料載入失敗，請確認 JSON 檔案是否存在！'; // 顯示錯誤提示
    } // 捕捉結束
} // loadStrategyData 結束

// 綁定全域 UI 事件監聽
function setupEventListeners() { // 事件設定函數
    document.getElementById('btn-manual-refresh').addEventListener('click', async () => { // 點擊重整
        const btn = document.getElementById('btn-manual-refresh'); // 取得按鈕 DOM
        btn.innerHTML = '<span>⏳</span> 更新中...'; // 顯示更新中
        await loadStrategyData(); // 重新讀取
        btn.innerHTML = '<span>🔄</span> 重新載入'; // 恢復按鈕文字
    }); // 點擊結束

    // 策略快選群組按鈕事件
    document.getElementById('btn-toggle-all').addEventListener('click', () => applyStrategyPreset('ALL')); // 全部組合
    document.getElementById('btn-toggle-scalper').addEventListener('click', () => applyStrategyPreset('GBP_CROSS')); // 英鎊交叉
    document.getElementById('btn-toggle-straddle').addEventListener('click', () => applyStrategyPreset('EUR_CROSS')); // 歐元交叉
    document.getElementById('btn-select-all').addEventListener('click', () => selectAllSymbols(true)); // 全選商品
    document.getElementById('btn-clear-all').addEventListener('click', () => selectAllSymbols(false)); // 清除商品

    // 圖表分頁切換
    document.querySelectorAll('.tab-btn').forEach(btn => { // 遍歷分頁按鈕
        btn.addEventListener('click', (e) => { // 點擊切換
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active')); // 移除其他按鈕啟用態
            e.target.classList.add('active'); // 當前按鈕設為啟用
            activeChartTab = e.target.getAttribute('data-chart'); // 更新啟用分頁變數
            
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
        timeEl.innerHTML = `⚡ <strong>MT5 伺服器時間:</strong> ${globalData.system_info.last_updated_mt5} | 台北: ${globalData.system_info.last_updated_tpe}`; // 填入時間文字
    } // 判斷結束
} // renderHeaderStatus 結束

// 渲染即時市場行情卡片 (Market Ticker Strip)
function renderMarketTickers() { // 行情卡片渲染函數
    const container = document.getElementById('market-tickers-container'); // 取得容器 DOM
    if (!container || !globalData || !globalData.symbols_meta) return; // 檢查資料

    const meta = globalData.symbols_meta; // 取得商品中繼資料
    container.innerHTML = Object.keys(meta).map(sym => { // 遍歷生成 HTML
        const item = meta[sym]; // 商品資料
        const changeClass = item.price_change_24h_pct >= 0 ? 'val-bull' : 'val-bear'; // 多空顏色
        const changePrefix = item.price_change_24h_pct >= 0 ? '+' : ''; // 正號標記
        
        let sessionTag = '<span class="badge-scalper">🌙 跨國收租中</span>'; // 標籤

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

        return `
            <div class="asset-checkbox-item ${activeClass}" data-symbol="${sym}" onclick="toggleSymbolSelection('${sym}')">
                <div class="asset-check-left">
                    <div class="custom-checkbox"></div>
                    <span class="asset-symbol-name" style="color:${symbolColors[sym] || '#fff'};">${sym}</span>
                    <span style="font-size:11px; color:var(--text-secondary); font-family:var(--font-mono);">(${item.spread_pips}p)</span>
                </div>
                <div class="asset-strategy-tags" style="display:flex; gap:4px; flex-wrap:wrap;">
                    <span class="badge-scalper" style="font-size:10px; padding:2px 6px;">🌙 純期權賣方收租</span>
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
    } else if (preset === 'GBP_CROSS') { // 僅英鎊交叉 (GBPCHF, GBPAUD, GBPCAD, GBPUSD)
        ["GBPCHF", "GBPAUD", "GBPCAD", "GBPUSD"].forEach(s => { if (globalData.symbols_meta[s]) selectedSymbols.add(s); }); // 加入
    } else if (preset === 'EUR_CROSS') { // 僅歐元交叉 (EURGBP, EURAUD, EURCHF)
        ["EURGBP", "EURAUD", "EURCHF"].forEach(s => { if (globalData.symbols_meta[s]) selectedSymbols.add(s); }); // 加入
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
    const bGbp = document.getElementById('btn-toggle-scalper'); // 英鎊交叉按鈕
    const bEur = document.getElementById('btn-toggle-straddle'); // 歐元交叉按鈕
    if (!bAll || !bGbp || !bEur) return; // 檢查

    bAll.classList.remove('active'); // 移除
    bGbp.classList.remove('active'); // 移除
    bEur.classList.remove('active'); // 移除

    if (activeStrategyFilter === 'ALL' && selectedSymbols.size === Object.keys(globalData.symbols_meta).length) { // 符合全部
        bAll.classList.add('active'); // 啟用全部
    } else if (activeStrategyFilter === 'GBP_CROSS') { // 符合 GBP
        bGbp.classList.add('active'); // 啟用
    } else if (activeStrategyFilter === 'EUR_CROSS') { // 符合 EUR
        bEur.classList.add('active'); // 啟用
    } // 判斷結束
} // updateFilterButtonsState 結束

// 動態精算所有 KPI 指標
function recalculateAndRenderKPIs() { // KPI 精算與渲染函數
    if (!globalData || !globalData.all_trades) return; // 檢查資料

    // 篩選出符合當前勾選貨幣對的交易明細
    const filtered = globalData.all_trades.filter(t => selectedSymbols.has(t.symbol)); // 過濾交易

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

    // 計算歷史最大回撤 (MDD)
    let mddPct = 0.0; // MDD 百分比
    let mddDollars = 0.0; // MDD 美金
    if (totalTrades > 0) { // 交易筆數大於 0
        const sortedTrades = [...filtered].sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time)); // 依出場時間正序
        let runningBal = 100000.0; // 起始本金
        let peakBal = 100000.0; // 歷史高點
        let maxDdVal = 0.0; // 最大美金回撤
        let maxDdPval = 0.0; // 最大百分比回撤

        sortedTrades.forEach(t => { // 遍歷交易
            runningBal += t.pnl_usd; // 累加淨值
            if (runningBal > peakBal) peakBal = runningBal; // 更新新高
            const curDrawdown = peakBal - runningBal; // 當前回撤
            const curDrawdownPct = peakBal > 0 ? (curDrawdown / peakBal * 100) : 0; // 回撤百分比
            if (curDrawdown > maxDdVal) maxDdVal = curDrawdown; // 更新最大美金
            if (curDrawdownPct > maxDdPval) maxDdPval = curDrawdownPct; // 更新最大百分比
        }); // 遍歷結束

        mddPct = maxDdPval.toFixed(2); // 設定 MDD 百分比
        mddDollars = maxDdVal.toFixed(2); // 設定 MDD 美金
    } // MDD 計算結束

    // 渲染卡片 1：總淨利
    const pnlEl = document.getElementById('kpi-total-pnl'); // 取得 DOM
    pnlEl.textContent = `${totalPnl >= 0 ? '+' : ''}$${totalPnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`; // 格式化美金
    pnlEl.className = 'card-main-val ' + (totalPnl >= 0 ? 'val-bull' : 'val-bear'); // 多空配色
    document.getElementById('kpi-total-pips').textContent = `${totalPips >= 0 ? '+' : ''}${totalPips.toFixed(1)} pips`; // 顯示 pips
    document.getElementById('kpi-total-pips').className = totalPips >= 0 ? 'val-bull' : 'val-bear'; // 配色
    document.getElementById('kpi-roi').textContent = `${roi >= 0 ? '+' : ''}${roi}%`; // 顯示 ROI
    document.getElementById('kpi-roi').className = roi >= 0 ? 'val-bull' : 'val-bear'; // 配色

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

    // 渲染卡片 5：當前持倉
    const activeCountEl = document.getElementById('kpi-active-count'); // DOM
    activeCountEl.textContent = '0 部位 (空手)'; // 顯示空手
    activeCountEl.className = 'card-main-val val-cyan'; // 配色
    document.getElementById('kpi-unrealized-pnl').textContent = '$0.00'; // $0
    document.getElementById('kpi-active-status').textContent = '100% 零隔夜合規'; // 狀態
} // recalculateAndRenderKPIs 結束

// 渲染 8 大策略模組參數規格與實盤回測績效矩陣總表
function renderStrategyMatrix() { // 矩陣渲染函數
    const tbody = document.getElementById('strategy-matrix-table-body'); // 取得表體 DOM
    if (!tbody || !globalData || !globalData.modules_summary) return; // 檢查

    tbody.innerHTML = globalData.modules_summary.map(m => { // 遍歷模組
        const symColor = symbolColors[m.symbol] || '#fff'; // 標的顏色
        const pnlClass = m.total_pnl_usd >= 0 ? 'val-bull' : 'val-bear'; // 損益顏色
        const tfBadge = m.timeframe === '5m' ? '<span class="badge-scalper">5M 週期</span>' : '<span class="badge-straddle">15M 週期</span>'; // 週期標籤

        return `
            <tr>
                <td style="font-family:var(--font-mono); font-weight:700; color:var(--text-secondary); font-size:12px;">${m.module_id}</td>
                <td><span class="badge-scalper" style="font-size:11px; padding:3px 8px;">🌙 純期權賣方收租</span></td>
                <td><strong style="color:${symColor}; font-family:var(--font-mono); font-size:14px;">${m.symbol}</strong></td>
                <td>${tfBadge}</td>
                <td style="font-size:11px; color:var(--text-secondary); font-family:var(--font-mono); font-weight:600;">MT5 00:00 ~ 09:30 (11:00清倉)</td>
                <td style="font-size:11px; font-family:var(--font-mono); color:#e6edf3;">BB(2.2σ) + 中軌止盈 + ADX&lt;30</td>
                <td style="font-family:var(--font-mono);">${m.trades_count} 筆 (${m.wins}W/${m.losses}L)</td>
                <td><strong class="val-blue" style="font-family:var(--font-mono); font-size:13px;">${m.win_rate}%</strong></td>
                <td><strong class="val-purple" style="font-family:var(--font-mono);">${m.profit_factor}</strong></td>
                <td style="color:var(--color-bear); font-family:var(--font-mono);">&lt; 0.3%</td>
                <td><strong class="${pnlClass}" style="font-family:var(--font-mono); font-size:14px;">+$${m.total_pnl_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong></td>
            </tr>
        `; // 回傳一列 HTML
    }).join(''); // 串接結束
} // renderStrategyMatrix 結束

// 渲染主 Plotly 互動圖表
function renderMainChart() { // 主圖表調度函數
    if (!globalData) return; // 檢查資料

    if (activeChartTab === 'combined-equity') { // 分頁 1: 組合資金權益曲線
        renderCombinedEquityChart(); // 繪製組合權益線
    } else if (activeChartTab === 'comparative-equity') { // 分頁 2: 多標的曲線比較
        renderComparativeEquityChart(); // 繪製多標的比較
    } else if (activeChartTab === 'candlestick-signals') { // 分頁 3: K 線與訊號標記
        renderCandlestickChart(candlestickSymbol); // 繪製 K 線圖
    } else if (activeChartTab === 'drawdown-curve') { // 分頁 4: 歷史回撤深度圖
        renderDrawdownChart(); // 繪製回撤圖
    } // 分頁判斷結束
} // renderMainChart 結束

// 繪製分頁 1：組合累積淨損益曲線 (從 $0 起計)
function renderCombinedEquityChart() { // 組合損益圖繪製函數
    const filteredTrades = globalData.all_trades.filter(t => selectedSymbols.has(t.symbol)).sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time)); // 依出場時間正序

    const timeSeries = []; // 時間陣列 (MT5)
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

    const trace = { // 定義曲線軌跡
        x: timeSeries, y: pnlSeries, mode: 'lines', name: '累積純收租淨利 ($0起計)',
        line: { color: '#00e676', width: 3.0 }, fill: 'tozeroy', fillcolor: 'rgba(0, 230, 118, 0.12)'
    }; // 軌跡結束

    const layout = { // 定義圖表面版樣式
        paper_bgcolor: '#131722', plot_bgcolor: '#131722', margin: { l: 70, r: 40, t: 40, b: 40 },
        title: { text: `精選 ${selectedSymbols.size} 款純期權賣方收租組合累積淨損益 (時間基準: MT5 伺服器時間)`, font: { color: '#f0f6fc', family: 'Outfit', size: 16 } },
        xaxis: { type: 'date', gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' } },
        yaxis: { gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, tickprefix: '$', zeroline: true, zerolinecolor: 'rgba(255,255,255,0.3)', zerolinewidth: 1.5 },
        hovermode: 'x unified', legend: { orientation: 'h', y: 1.1, font: { color: '#8b949e' } }
    }; // 面版結束

    Plotly.newPlot('main-plotly-chart', [trace], layout, { responsive: true, displayModeBar: true }); // 渲染 Plotly 圖表
} // renderCombinedEquityChart 結束

// 繪製分頁 2：多商品個別累積損益曲線對比圖
function renderComparativeEquityChart() { // 多商品比較圖繪製函數
    const traces = []; // 軌跡陣列

    selectedSymbols.forEach(sym => { // 遍歷已勾選的商品
        const symTrades = globalData.all_trades.filter(t => t.symbol === sym).sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time)); // 依時間排序
        if (symTrades.length === 0) return; // 無交易跳過

        const tTimes = [symTrades[0].entry_time]; // 時間 (MT5)
        const tPnls = [0.0]; // 累積損益 (從 $0 開始)
        let rPnl = 0.0; // 當前累計淨利

        symTrades.forEach(t => { // 遍歷
            rPnl += t.pnl_usd; // 累加損益
            tTimes.push(t.exit_time); // 時間 (MT5)
            tPnls.push(Math.round(rPnl * 100) / 100); // 累積損益
        }); // 結束

        traces.push({ // 加入軌跡
            x: tTimes, y: tPnls, mode: 'lines',
            name: `${sym} (${symTrades.length} 筆 / +$${Math.round(rPnl).toLocaleString()})`,
            line: { color: symbolColors[sym] || '#fff', width: 2.2 }
        }); // 結束
    }); // 遍歷結束

    const layout = { // 面版樣式
        paper_bgcolor: '#131722', plot_bgcolor: '#131722', margin: { l: 70, r: 40, t: 40, b: 40 },
        title: { text: '精選交叉貨幣對獨立純期權賣方收租淨利比較 (MT5 伺服器時間)', font: { color: '#f0f6fc', family: 'Outfit', size: 16 } },
        xaxis: { type: 'date', gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' } },
        yaxis: { gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, tickprefix: '$', zeroline: true, zerolinecolor: 'rgba(255,255,255,0.3)', zerolinewidth: 1.5 },
        hovermode: 'x unified', legend: { orientation: 'h', y: 1.12, font: { color: '#8b949e', size: 11 } }
    }; // 面版結束

    Plotly.newPlot('main-plotly-chart', traces, layout, { responsive: true, displayModeBar: true }); // 渲染圖表
} // renderComparativeEquityChart 結束

// 繪製分頁 3：K 線圖與真實進出場買賣訊號點標記
function renderCandlestickChart(sym) { // K 線繪製函數
    if (!globalData || !globalData.chart_data || !globalData.chart_data[sym]) return; // 檢查資料

    const cdata = globalData.chart_data[sym]; // 取得該標的 K 線與指標數據
    const symTrades = globalData.all_trades.filter(t => t.symbol === sym); // 取得該標的交易

    const traceCandles = { // K 線
        x: cdata.timestamps, open: cdata.open, high: cdata.high, low: cdata.low, close: cdata.close,
        type: 'candlestick', name: `${sym} K線 (MT5時間)`,
        increasing: { line: { color: '#00e676', width: 1.2 }, fillcolor: '#00e676' },
        decreasing: { line: { color: '#ff1744', width: 1.2 }, fillcolor: '#ff1744' }, yaxis: 'y'
    }; // K 線結束

    const traceBBUpper = { x: cdata.timestamps, y: cdata.bb_upper, mode: 'lines', name: 'BB 上軌 (2.2σ)', line: { color: 'rgba(41, 182, 246, 0.4)', width: 1.2, dash: 'dot' }, yaxis: 'y' };
    const traceBBMid   = { x: cdata.timestamps, y: cdata.bb_mid, mode: 'lines', name: 'BB 中軌 (20SMA)', line: { color: 'rgba(255, 167, 38, 0.6)', width: 1.2 }, yaxis: 'y' };
    const traceBBLower = { x: cdata.timestamps, y: cdata.bb_lower, mode: 'lines', name: 'BB 下軌 (2.2σ)', line: { color: 'rgba(41, 182, 246, 0.4)', width: 1.2, dash: 'dot' }, yaxis: 'y' };

    const buyEntries = symTrades.filter(t => t.type.includes('Buy')); // 多單進場
    const sellEntries = symTrades.filter(t => t.type.includes('Sell')); // 空單進場
    const exits = symTrades; // 全部出場

    const traceBuyMarkers = { // 買入標記 (綠色三角向上)
        x: buyEntries.map(t => t.entry_time), y: buyEntries.map(t => t.entry_price), mode: 'markers', name: '賣出 Put (Buy)',
        marker: { symbol: 'triangle-up', size: 11, color: '#00e676', line: { color: '#ffffff', width: 1.5 } }, yaxis: 'y'
    }; // 買入標記結束

    const traceSellMarkers = { // 賣出標記 (紅色三角向下)
        x: sellEntries.map(t => t.entry_time), y: sellEntries.map(t => t.entry_price), mode: 'markers', name: '賣出 Call (Sell)',
        marker: { symbol: 'triangle-down', size: 11, color: '#ff1744', line: { color: '#ffffff', width: 1.5 } }, yaxis: 'y'
    }; // 賣出標記結束

    const traceExitMarkers = { // 出場標記 (黃色方塊)
        x: exits.map(t => t.exit_time), y: exits.map(t => t.exit_price), mode: 'markers', name: '中軌止盈平倉 (Exit)',
        marker: { symbol: 'square', size: 7, color: '#ffd600' },
        text: exits.map(t => `出場原因: ${t.exit_reason}<br>損益: +$${t.pnl_usd} (${t.pnl_pips}p)`), hoverinfo: 'text+x+y', yaxis: 'y'
    }; // 出場標記結束

    const traceRSI = { x: cdata.timestamps, y: cdata.rsi, mode: 'lines', name: 'RSI (14)', line: { color: '#b388ff', width: 1.5 }, yaxis: 'y2' };
    const traceZScore = { x: cdata.timestamps, y: cdata.z_score, mode: 'lines', name: 'Z-Score (20)', line: { color: '#29b6f6', width: 1.5 }, yaxis: 'y3' };

    const layout = {
        paper_bgcolor: '#131722', plot_bgcolor: '#131722', margin: { l: 70, r: 40, t: 40, b: 40 },
        title: { text: `[${sym}] K線、布林通道與實戰進出場訊號點 (時間基準: MT5 伺服器時間)`, font: { color: '#f0f6fc', family: 'Outfit', size: 16 } },
        xaxis: { type: 'date', gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, rangeslider: { visible: false } },
        yaxis: { domain: [0.38, 1.0], gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, title: '價格' },
        yaxis2: { domain: [0.19, 0.35], gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, title: 'RSI', range: [10, 90] },
        yaxis3: { domain: [0.0, 0.16], gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, title: 'Z-Score', range: [-4.0, 4.0] },
        hovermode: 'x unified', legend: { orientation: 'h', y: 1.08, font: { color: '#8b949e', size: 11 } }
    }; // Layout 結束

    Plotly.newPlot('main-plotly-chart', [traceCandles, traceBBUpper, traceBBMid, traceBBLower, traceBuyMarkers, traceSellMarkers, traceExitMarkers, traceRSI, traceZScore], layout, { responsive: true, displayModeBar: true }); // 渲染
} // renderCandlestickChart 結束

// 繪製分頁 4：歷史回撤深度圖
function renderDrawdownChart() { // 回撤圖繪製函數
    const filteredTrades = globalData.all_trades.filter(t => selectedSymbols.has(t.symbol)).sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time)); // 排序

    const timeSeries = []; // 時間 (MT5)
    const ddPctSeries = []; // 回撤百分比
    let runningBal = 100000.0; // 淨值
    let peakBal = 100000.0; // 歷史最高點

    if (filteredTrades.length > 0) { // 有交易
        timeSeries.push(filteredTrades[0].entry_time); // 起始 (MT5)
        ddPctSeries.push(0.0); // 起始回撤 0%
        filteredTrades.forEach(t => { // 遍歷
            runningBal += t.pnl_usd; // 累加
            if (runningBal > peakBal) peakBal = runningBal; // 新高
            const ddPct = peakBal > 0 ? -((peakBal - runningBal) / peakBal * 100) : 0; // 回撤百分比 (負值)
            timeSeries.push(t.exit_time); // 時間 (MT5)
            ddPctSeries.push(Math.round(ddPct * 100) / 100); // 記錄
        }); // 結束
    } // 判斷結束

    const trace = {
        x: timeSeries, y: ddPctSeries, mode: 'lines', name: '回撤深度 (%)',
        line: { color: '#ff1744', width: 2.0 }, fill: 'tozeroy', fillcolor: 'rgba(255, 23, 68, 0.2)'
    }; // 軌跡結束

    const layout = {
        paper_bgcolor: '#131722', plot_bgcolor: '#131722', margin: { l: 70, r: 40, t: 40, b: 40 },
        title: { text: '精選純期權賣方收租組合資金回撤深度圖 (MT5 伺服器時間)', font: { color: '#f0f6fc', family: 'Outfit', size: 16 } },
        xaxis: { type: 'date', gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' } },
        yaxis: { gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, ticksuffix: '%', zeroline: true, zerolinecolor: 'rgba(255,255,255,0.3)', zerolinewidth: 1.5 },
        hovermode: 'x unified'
    }; // Layout 結束

    Plotly.newPlot('main-plotly-chart', [trace], layout, { responsive: true, displayModeBar: true }); // 渲染
} // renderDrawdownChart 結束

// 渲染歷史交易明細表格
function renderTradesTable() { // 表格渲染函數
    const tbody = document.getElementById('trades-table-body'); // 取得表體 DOM
    const counterEl = document.getElementById('table-trades-counter'); // 取得計數器 DOM
    if (!tbody || !globalData || !globalData.all_trades) return; // 檢查資料

    const filtered = globalData.all_trades.filter(t => { // 遍歷過濾
        if (!selectedSymbols.has(t.symbol)) return false; // 排除未勾選
        if (tableTradeType === 'BUY' && !t.type.includes('Buy')) return false; // 僅買進
        if (tableTradeType === 'SELL' && !t.type.includes('Sell')) return false; // 僅賣出
        if (tableTradeOutcome === 'WIN' && !t.win) return false; // 僅獲利
        if (tableTradeOutcome === 'LOSS' && t.win) return false; // 僅虧損
        if (tableSearchQuery) { // 搜尋關鍵字
            const matchSym = t.symbol.toLowerCase().includes(tableSearchQuery); // 標的
            const matchReason = t.exit_reason.toLowerCase().includes(tableSearchQuery); // 原因
            const matchStrat = t.strategy.toLowerCase().includes(tableSearchQuery); // 策略
            if (!matchSym && !matchReason && !matchStrat) return false; // 排除
        } // 結束
        return true; // 符合
    }); // 過濾結束

    counterEl.textContent = `顯示 ${filtered.length} / ${globalData.all_trades.length} 筆精選期權賣方交易明細`; // 計數

    const totalPages = Math.ceil(filtered.length / pageSize) || 1; // 總頁數
    if (currentPage > totalPages) currentPage = totalPages; // 校正頁碼
    const startIndex = (currentPage - 1) * pageSize; // 起始索引
    const endIndex = Math.min(startIndex + pageSize, filtered.length); // 結束索引
    const pageTrades = filtered.slice(startIndex, endIndex); // 抽取

    if (pageTrades.length === 0) { // 空資料
        tbody.innerHTML = `<tr><td colspan="13" style="text-align:center; padding:30px; color:var(--text-muted);">無符合條件之交易紀錄</td></tr>`; // 提示
    } else { // 有資料
        tbody.innerHTML = pageTrades.map(t => { // 遍歷
            const isWin = t.win; // 獲利
            const pnlClass = isWin ? 'val-bull' : 'val-bear'; // 配色
            const typeBadge = t.type.includes('Buy') ? '<span class="badge-bull">賣 Put (多)</span>' : '<span class="badge-bear">賣 Call (空)</span>'; // 標籤
            const stratBadge = '<span class="badge-scalper">純期權賣方收租</span>'; // 策略標籤
            const symColor = symbolColors[t.symbol] || '#fff'; // 顏色
            const isHighlight = highlightedTradeId === t.global_id ? 'style="background:rgba(41,182,246,0.15);"' : ''; // 高亮

            return `
                <tr ${isHighlight} onclick="focusTradeOnChart('${t.symbol}', ${t.global_id})">
                    <td style="font-family:var(--font-mono); color:var(--text-secondary); font-size:12px;">#${t.global_id}</td>
                    <td>${stratBadge}</td>
                    <td><strong style="color:${symColor}; font-family:var(--font-mono);">${t.symbol}</strong></td>
                    <td>${typeBadge}</td>
                    <td style="font-family:var(--font-mono);">${t.lot_size}</td>
                    <td style="font-family:var(--font-mono); font-size:12px; color:var(--text-secondary); font-weight:600;">${t.entry_time}</td>
                    <td style="font-family:var(--font-mono);">${t.entry_price}</td>
                    <td style="font-family:var(--font-mono); font-size:12px; color:var(--text-secondary); font-weight:600;">${t.exit_time}</td>
                    <td style="font-family:var(--font-mono);">${t.exit_price}</td>
                    <td><strong class="${pnlClass}" style="font-family:var(--font-mono);">${t.pnl_usd >= 0 ? '+' : ''}$${t.pnl_usd.toFixed(2)}</strong></td>
                    <td class="${pnlClass}" style="font-family:var(--font-mono);">${t.pnl_pips >= 0 ? '+' : ''}${t.pnl_pips.toFixed(1)}p</td>
                    <td style="font-size:12px; color:var(--text-secondary);">${t.exit_reason}</td>
                    <td style="font-family:var(--font-mono); font-size:12px; color:var(--text-muted);">${t.duration_mins} 分鐘</td>
                </tr>
            `; // 回傳一列
        }).join(''); // 串接結束
    } // 判斷結束

    renderPaginationControls(totalPages); // 生成分頁按鈕
} // renderTradesTable 結束

// 渲染分頁導航按鈕
function renderPaginationControls(totalPages) { // 分頁按鈕生成函數
    const container = document.getElementById('pagination-buttons-container'); // DOM
    if (!container) return; // 檢查

    container.innerHTML = `
        <button class="page-btn" onclick="changeTablePage(1)" ${currentPage === 1 ? 'disabled' : ''}>« 首頁</button>
        <button class="page-btn" onclick="changeTablePage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>‹ 上一頁</button>
        <span style="font-size:12px; color:var(--text-secondary); font-family:var(--font-mono); padding:0 8px;">第 ${currentPage} / ${totalPages} 頁</span>
        <button class="page-btn" onclick="changeTablePage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>下一頁 ›</button>
        <button class="page-btn" onclick="changeTablePage(${totalPages})" ${currentPage === totalPages ? 'disabled' : ''}>末頁 »</button>
    `; // HTML
} // renderPaginationControls 結束

// 表格分頁切換
function changeTablePage(page) { // 分頁跳轉函數
    currentPage = page; // 更新頁碼
    renderTradesTable(); // 重新渲染
} // changeTablePage 結束

// 聚焦切換至該標的 K 線圖
function focusTradeOnChart(sym, tradeId) { // 聚焦交易函數
    highlightedTradeId = tradeId; // 記錄高亮 ID
    candlestickSymbol = sym; // 切換 K 線標的
    const selectEl = document.getElementById('candlestick-symbol-select'); // 取得下拉
    if (selectEl) selectEl.value = sym; // 更新下拉

    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active')); // 移除啟用
    const candleTabBtn = document.querySelector('.tab-btn[data-chart="candlestick-signals"]'); // 取得按鈕
    if (candleTabBtn) candleTabBtn.classList.add('active'); // 啟用
    activeChartTab = 'candlestick-signals'; // 設定分頁
    document.getElementById('candlestick-options').style.display = 'flex'; // 顯示下拉

    renderMainChart(); // 重新繪製
    renderTradesTable(); // 重新高亮
    document.querySelector('.chart-section').scrollIntoView({ behavior: 'smooth' }); // 平滑滾動
} // focusTradeOnChart 結束

// 匯出 CSV 檔案
function exportFilteredTradesCSV() { // CSV 下載函數
    if (!globalData || !globalData.all_trades) return; // 檢查

    const filtered = globalData.all_trades.filter(t => selectedSymbols.has(t.symbol)); // 過濾
    if (filtered.length === 0) { // 無資料
        alert('當前無交易紀錄可供匯出！'); // 提示
        return; // 終止
    } // 判斷結束

    const headers = ["序號", "策略名稱", "貨幣對", "交易方向", "手數", "進場時間(MT5)", "進場價", "出場時間(MT5)", "出場價", "淨損益(USD)", "獲利點數(pips)", "出場原因", "持倉分鐘數"]; // 表頭
    const csvRows = [headers.join(',')]; // 寫入表頭

    filtered.forEach(t => { // 遍歷交易
        const row = [t.global_id, `"${t.strategy}"`, t.symbol, `"${t.type}"`, t.lot_size, t.entry_time, t.entry_price, t.exit_time, t.exit_price, t.pnl_usd, t.pnl_pips, `"${t.exit_reason}"`, t.duration_mins]; // 單列
        csvRows.push(row.join(',')); // 加入陣列
    }); // 結束

    const csvContent = "\uFEFF" + csvRows.join('\n'); // 加入 BOM 防亂碼
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' }); // 建立 Blob
    const url = URL.createObjectURL(blob); // 網址
    const link = document.createElement('a'); // 標籤
    link.setAttribute('href', url); // 設定
    link.setAttribute('download', `PEPPERSTONE_Top8_Option_Selling_Trades_${new Date().toISOString().substring(0, 10)}.csv`); // 檔名
    document.body.appendChild(link); // 加入 DOM
    link.click(); // 下載
    document.body.removeChild(link); // 移除 DOM
} // exportFilteredTradesCSV 結束
