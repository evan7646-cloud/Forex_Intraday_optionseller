// 全域資料與狀態管理變數
let globalData = null; // 策略結果 JSON 原始數據
let selectedSymbols = new Set(); // 當前使用者勾選的貨幣對集合
let activeStrategyFilter = 'ALL'; // 當前策略過濾 ('ALL', 'DAY_CHANNEL', 'US_AFTERNOON')
let activeChartTab = 'combined-equity'; // 當前啟用的圖表分頁標籤
let candlestickSymbol = 'GBPJPY'; // 當前 K 線圖所選取的貨幣對標的
let currentPage = 1; // 當前歷史交易表格分頁
let pageSize = 15; // 每頁顯示交易筆數
let tableSearchQuery = ''; // 交易明細搜尋關鍵字
let tableTradeType = 'ALL'; // 交易明細方向過濾 ('ALL', 'BUY', 'SELL')
let tableTradeOutcome = 'ALL'; // 交易明細勝負過濾 ('ALL', 'WIN', 'LOSS')
let highlightedTradeId = null; // 當前點擊聚焦高亮的交易序號

// 方案 A 穩健組合 8 大王牌貨幣對圖表配色調色盤 (v5.10 汰弱留強精銳版)
const symbolColors = { // 配色字典
    "GBPJPY": "#ff7043", // 亮橘紅 (1h/15m 鎊日美盤+白天收租) 💎
    "EURJPY": "#ff4081", // 亮粉紅 (1h/15m 歐日美盤+白天收租)
    "GBPUSD": "#29b6f6", // 科技天藍 (15m 鎊美美盤極速收租)
    "EURCAD": "#00e676", // 翡翠綠 (1h 歐加美盤高盈虧收租) 🆕
    "AUDCHF": "#ffd600", // 亮金黃 (1h 澳瑞全天避險均值回歸)
    "AUDUSD": "#00bcd4"  // 科技青 (1h 澳美白天低點差收租) 🆕
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

        // 初始化商品勾選集合 (支援自動防禦容錯)
        if (!globalData.symbols_meta && globalData.modules_summary) { // 若中繼字典為空則自動從模組摘要建構
            globalData.symbols_meta = {}; // 初始化物件
            globalData.modules_summary.forEach(m => { // 遍歷模組
                if (!globalData.symbols_meta[m.symbol]) { // 若不存在
                    globalData.symbols_meta[m.symbol] = { symbol: m.symbol, spread_pips: 1.5, current_price: 1.0, price_change_24h_pct: 0.0, current_rsi: 50.0, current_zscore: 0.0 }; // 填入預設值
                } // 判斷結束
            }); // 遍歷結束
        } // 容錯結束
        const allSyms = Object.keys(globalData.symbols_meta || {}); // 取得全部貨幣對清單
        selectedSymbols = new Set(allSyms); // 放入集合
        if (allSyms.length > 0) candlestickSymbol = allSyms[0]; // 設定預設 K 線標的

        // 渲染各區塊內容
        const btnToggleAll = document.getElementById('btn-toggle-all'); // 取得全部模組按鈕
        if (btnToggleAll && globalData.portfolio_metrics) { // 若按鈕與指標存在
            const m = globalData.portfolio_metrics; // 取得總組合指標
            btnToggleAll.textContent = `全部 8 大分工收租模組 (勝率 ${m.win_rate}% / PF ${m.profit_factor} / 淨利 $${Math.round(m.total_net_pnl_usd).toLocaleString()})`; // 動態更新按鈕文字
        } // 判斷結束
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
    document.getElementById('btn-toggle-all').addEventListener('click', () => applyStrategyPreset('ALL')); // 全部 8 大模組
    document.getElementById('btn-toggle-scalper').addEventListener('click', () => applyStrategyPreset('DAY_CHANNEL')); // ☀️ 白天全天通道組
    document.getElementById('btn-toggle-straddle').addEventListener('click', () => applyStrategyPreset('US_AFTERNOON')); // 🌙 晚間美盤收斂組
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
    const searchInput = document.getElementById('trade-search-input'); // 搜尋框
    if (searchInput) { // 存在
        searchInput.addEventListener('input', (e) => { // 輸入事件
            tableSearchQuery = e.target.value.trim().toLowerCase(); // 取得搜尋關鍵字
            currentPage = 1; // 重設回第一頁
            renderTradesTable(); // 重新渲染表格
        }); // 搜尋監聽結束
    } // 判斷結束

    // 交易表格方向下拉篩選
    const typeFilter = document.getElementById('trade-type-filter'); // 方向下拉
    if (typeFilter) { // 存在
        typeFilter.addEventListener('change', (e) => { // 變更事件
            tableTradeType = e.target.value; // 更新方向篩選變數
            currentPage = 1; // 重設第一頁
            renderTradesTable(); // 重新渲染表格
        }); // 監聽結束
    } // 判斷結束

    // 交易表格勝負下拉篩選
    const outcomeFilter = document.getElementById('trade-outcome-filter'); // 勝負下拉
    if (outcomeFilter) { // 存在
        outcomeFilter.addEventListener('change', (e) => { // 變更事件
            tableTradeOutcome = e.target.value; // 更新勝負篩選變數
            currentPage = 1; // 重設第一頁
            renderTradesTable(); // 重新渲染表格
        }); // 監聽結束
    } // 判斷結束

    // 分頁上一頁按鈕
    const btnPrev = document.getElementById('btn-page-prev'); // 上一頁
    if (btnPrev) { // 存在
        btnPrev.addEventListener('click', () => { // 點擊
            if (currentPage > 1) { // 大於第一頁
                currentPage--; // 遞減
                renderTradesTable(); // 重新渲染
            } // 判斷結束
        }); // 結束
    } // 判斷結束

    // 分頁下一頁按鈕
    const btnNext = document.getElementById('btn-page-next'); // 下一頁
    if (btnNext) { // 存在
        btnNext.addEventListener('click', () => { // 點擊
            currentPage++; // 遞增
            renderTradesTable(); // 重新渲染
        }); // 結束
    } // 判斷結束
} // setupEventListeners 結束

// 渲染頂部狀態列
function renderHeaderStatus() { // 頂部狀態渲染函數
    const timeEl = document.getElementById('status-update-time'); // 取得時間元素
    if (globalData && globalData.system_info) { // 若系統資訊存在
        timeEl.innerHTML = `⚡ <strong>MT5:</strong> ${globalData.system_info.last_updated_mt5} | <strong>台北:</strong> ${globalData.system_info.last_updated_tpe}`; // 填入時間文字
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
        
        let sessionTag = (sym === 'AUDCHF' || sym === 'AUDUSD') ? // 純白天全天通道組判斷
            '<span class="badge-scalper">☀️ 白天通道收租 (06:15~23:00)</span>' : // 白天通道標籤
            ((sym === 'EURJPY' || sym === 'GBPJPY') ? '<span class="badge-scalper">☀️🌙 白天+美盤雙時段</span>' : // 雙時段標籤
            '<span class="badge-straddle">🌙 晚間美盤收租 (18:00~00:00)</span>'); // 晚間美盤標籤

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
    const container = document.getElementById('asset-checkboxes-container'); // 取得容器
    if (!container || !globalData || !globalData.symbols_meta) return; // 檢查資料

    const meta = globalData.symbols_meta; // 取得商品資訊
    container.innerHTML = Object.keys(meta).map(sym => { // 遍歷生成 Checkbox
        const item = meta[sym]; // 商品資料
        const isChecked = selectedSymbols.has(sym); // 是否已勾選
        const activeClass = isChecked ? 'checked' : ''; // 樣式類別
        
        const isDayOnly = (sym === 'AUDCHF' || sym === 'AUDUSD'); // 純白天組判斷
        const isDual = (sym === 'EURJPY' || sym === 'GBPJPY'); // 雙時段組判斷
        const tagText = isDayOnly ? '☀️ 白天全天通道組' : (isDual ? '☀️🌙 白天+美盤雙時段' : '🌙 晚間美盤收斂組 (超窄點差)'); // 標籤文字
        const tagBadge = isDayOnly ? 'badge-scalper' : (isDual ? 'badge-scalper' : 'badge-straddle'); // 樣式

        return `
            <div class="asset-checkbox-item ${activeClass}" data-symbol="${sym}" onclick="toggleSymbolSelection('${sym}')">
                <div class="asset-check-left">
                    <div class="custom-checkbox"></div>
                    <span class="asset-symbol-name" style="color:${symbolColors[sym] || '#fff'};">${sym}</span>
                    <span style="font-size:11px; color:var(--text-secondary); font-family:var(--font-mono);">(${item.spread_pips}p)</span>
                </div>
                <div class="asset-strategy-tags" style="display:flex; gap:4px; flex-wrap:wrap;">
                    <span class="${tagBadge}" style="font-size:10px; padding:2px 6px;">${tagText}</span>
                </div>
            </div>
        `; // 回傳 Checkbox HTML
    }).join(''); // 串接結束

    // 同步更新 K 線下拉選單選項
    const candleSelect = document.getElementById('candlestick-symbol-select'); // 下拉選單 DOM
    if (candleSelect) { // 存在
        candleSelect.innerHTML = Object.keys(meta).map(sym => { // 生成 option
            return `<option value="${sym}" ${sym === candlestickSymbol ? 'selected' : ''}>${sym} (點差 ${meta[sym].spread_pips}p)</option>`; // 選項 HTML
        }).join(''); // 串接結束
    } // 判斷結束
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

    if (preset === 'ALL') { // 全部 8 大模組
        Object.keys(globalData.symbols_meta).forEach(s => selectedSymbols.add(s)); // 全部加入
    } else if (preset === 'DAY_CHANNEL') { // ☀️ 白天全天通道組 (EURJPY, AUDCHF, AUDUSD, GBPJPY)
        ["EURJPY", "AUDCHF", "AUDUSD", "GBPJPY"].forEach(s => { if (globalData.symbols_meta[s]) selectedSymbols.add(s); }); // 加入
    } else if (preset === 'US_AFTERNOON') { // 🌙 晚間美盤午後組 (GBPJPY, EURJPY, GBPUSD, EURCAD)
        ["GBPJPY", "EURJPY", "GBPUSD", "EURCAD"].forEach(s => { if (globalData.symbols_meta[s]) selectedSymbols.add(s); }); // 加入
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
    const bDay = document.getElementById('btn-toggle-scalper'); // 白天按鈕
    const bUs = document.getElementById('btn-toggle-straddle'); // 美盤按鈕
    if (!bAll || !bDay || !bUs) return; // 檢查

    bAll.classList.remove('active'); // 移除
    bDay.classList.remove('active'); // 移除
    bUs.classList.remove('active'); // 移除

    if (activeStrategyFilter === 'ALL' && selectedSymbols.size === Object.keys(globalData.symbols_meta).length) { // 符合全部
        bAll.classList.add('active'); // 啟用全部
    } else if (activeStrategyFilter === 'DAY_CHANNEL') { // 符合白天
        bDay.classList.add('active'); // 啟用
    } else if (activeStrategyFilter === 'US_AFTERNOON') { // 符合美盤
        bUs.classList.add('active'); // 啟用
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

    // 計算歷史最大回撤 (MDD) 與目前即時回撤 (Current Drawdown) — 均換算為美金金額與百分比
    let mddPct = '0.00'; // MDD 百分比
    let mddDollars = '0.00'; // MDD 美金
    let currentDdDollars = '0.00'; // 目前回撤美金
    let currentDdPct = '0.00'; // 目前回撤百分比
    if (totalTrades > 0) { // 交易筆數大於 0
        const sortedTrades = [...filtered].sort((a, b) => new Date(a.exit_time) - new Date(b.exit_time)); // 依出場時間正序
        let runningBal = 100000.0; // 起始本金 $100,000 USD
        let peakBal = 100000.0; // 歷史高點
        let maxDdVal = 0.0; // 最大美金回撤
        let maxDdPval = 0.0; // 最大百分比回撤

        sortedTrades.forEach(t => { // 遍歷交易
            runningBal += t.pnl_usd; // 累加淨值
            if (runningBal > peakBal) peakBal = runningBal; // 更新歷史新高
            const curDrawdown = peakBal - runningBal; // 該筆當前回撤
            const curDrawdownPct = (curDrawdown / 100000.0 * 100); // 以 $100,000 為基準換算回撤百分比
            if (curDrawdown > maxDdVal) maxDdVal = curDrawdown; // 更新最大回撤美金
            if (curDrawdownPct > maxDdPval) maxDdPval = curDrawdownPct; // 更新最大回撤百分比
        }); // 遍歷結束

        mddPct = maxDdPval.toFixed(2); // 格式化 MDD 百分比
        mddDollars = maxDdVal.toFixed(2); // 格式化 MDD 美金

        const finalDrawdownVal = Math.max(0, peakBal - runningBal); // 計算最新目前即時回撤美金
        const finalDrawdownPct = (finalDrawdownVal / 100000.0 * 100); // 換算最新目前即時回撤百分比
        currentDdDollars = finalDrawdownVal.toFixed(2); // 格式化目前回撤美金
        currentDdPct = finalDrawdownPct.toFixed(2); // 格式化目前回撤百分比
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

    // 渲染卡片 4：最大歷史回撤與目前即時回撤 (均以 金額 (％) 格式顯示)
    const mddEl = document.getElementById('kpi-max-drawdown'); // 取得 MDD 主顯示 DOM
    if (mddEl) { // 若存在
        mddEl.textContent = `-$${parseFloat(mddDollars).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (${mddPct}%)`; // 金額(%)顯示
    } // 判斷結束
    
    const curDdEl = document.getElementById('kpi-current-drawdown'); // 取得目前回撤 DOM
    if (curDdEl) { // 若存在
        const curDdV = parseFloat(currentDdDollars); // 轉浮點數
        curDdEl.textContent = `-$${curDdV.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (${currentDdPct}%)`; // 金額(%)顯示
        curDdEl.className = curDdV === 0 ? 'val-bull' : 'val-bear'; // 0 回撤為綠色，有回撤為紅色
    } // 判斷結束

    // 渲染卡片 5：當前持倉
    const activeCountEl = document.getElementById('kpi-active-count'); // DOM
    activeCountEl.textContent = '0 部位 (空手)'; // 顯示空手
    activeCountEl.className = 'card-main-val val-cyan'; // 配色
    document.getElementById('kpi-unrealized-pnl').textContent = '$0.00'; // $0
    document.getElementById('kpi-active-status').textContent = '100% 零隔夜合規'; // 狀態
} // recalculateAndRenderKPIs 結束

// 渲染 8 大策略模組參數規格與實盤回測績效矩陣總表
function renderStrategyMatrix() { // 矩陣渲染函數
    const tbody = document.getElementById('strategy-matrix-body'); // 取得表體 DOM
    if (!tbody || !globalData || !globalData.modules_summary) return; // 檢查

    tbody.innerHTML = globalData.modules_summary.map(m => { // 遍歷模組
        const symColor = symbolColors[m.symbol] || '#fff'; // 標的顏色
        const pnlClass = m.total_pnl_usd >= 0 ? 'val-bull' : 'val-bear'; // 損益顏色
        const tfBadge = m.timeframe === '1h' ? '<span class="badge-straddle">1H 週期</span>' : '<span class="badge-scalper">15M 週期</span>'; // 週期標籤
        const isDayGroup = m.module_id.includes('_DAY'); // 依模組 ID 判斷分組 (避免 EURJPY 雙組問題)
        const sessionGroupBadge = isDayGroup ? 
            '<span class="badge-scalper" style="font-size:11px; padding:3px 8px;">☀️ 白天全天通道組</span>' : 
            '<span class="badge-straddle" style="font-size:11px; padding:3px 8px;">🌙 晚間美盤收斂組</span>'; // 標籤

        // 方案 A 參數映射表 (v5.10 精銳版依 module_id 精準對應)
        const sigmaMap = {'Opt_GBPJPY_1H_US':'2.2σ', 'Opt_EURJPY_1H_US':'2.5σ', 'Opt_GBPUSD_15M_US':'2.2σ', 'Opt_EURCAD_1H_US':'3.0σ', 'Opt_EURJPY_15M_DAY':'3.0σ', 'Opt_AUDCHF_1H_DAY':'2.8σ', 'Opt_AUDUSD_1H_DAY':'3.0σ', 'Opt_GBPJPY_15M_DAY':'2.8σ'}; // 標準差表
        const slMap = {'Opt_GBPJPY_1H_US':'1.5 ATR', 'Opt_EURJPY_1H_US':'1.5 ATR', 'Opt_GBPUSD_15M_US':'2.0 ATR', 'Opt_EURCAD_1H_US':'2.0 ATR', 'Opt_EURJPY_15M_DAY':'2.0 ATR', 'Opt_AUDCHF_1H_DAY':'2.5 ATR', 'Opt_AUDUSD_1H_DAY':'2.0 ATR', 'Opt_GBPJPY_15M_DAY':'2.5 ATR'}; // 停損表
        const sigmaVal = sigmaMap[m.module_id] || '2.2σ'; // 標準差
        const slVal = slMap[m.module_id] || '2.0 ATR'; // 止損

        return `
            <tr>
                <td>${sessionGroupBadge}</td>
                <td style="font-family:var(--font-mono); font-weight:700; color:var(--text-secondary); font-size:12px;">${m.module_id}</td>
                <td><strong style="color:${symColor}; font-family:var(--font-mono); font-size:14px;">${m.symbol}</strong></td>
                <td>${tfBadge}</td>
                <td style="font-family:var(--font-mono);">${m.trades_count} 筆 (${m.wins}W / ${m.losses}L)</td>
                <td><strong class="val-blue" style="font-family:var(--font-mono); font-size:13px;">${m.win_rate}%</strong></td>
                <td><strong class="val-purple" style="font-family:var(--font-mono); font-size:13px;">${m.profit_factor}</strong></td>
                <td><strong class="${pnlClass}" style="font-family:var(--font-mono); font-size:14px;">+$${m.total_pnl_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong></td>
                <td><strong class="val-bull" style="font-family:var(--font-mono);">+${m.roi_pct}%</strong></td>
                <td style="font-family:var(--font-mono); color:#e6edf3;">BB (${sigmaVal}) + 中軌止盈</td>
                <td style="font-family:var(--font-mono); color:var(--color-bear);">${slVal} 停損 (03:00前清倉)</td>
            </tr>
        `; // 回傳一列 HTML
    }).join(''); // 串接結束
} // renderStrategyMatrix 結束

// 渲染主 Plotly 互動圖表
function renderMainChart() { // 主圖表調度函數
    if (!globalData) return; // 檢查資料

    if (activeChartTab === 'combined-equity') { // 分頁 1: 組合資金權益曲線
        renderCombinedEquityChart(); // 繪製組合權益線
    } else if (activeChartTab === 'candlestick-signals') { // 分頁 2: K 線與訊號標記
        renderCandlestickChart(candlestickSymbol); // 繪製 K 線圖
    } else if (activeChartTab === 'pnl-distribution') { // 分頁 3: 損益分布
        renderPnlDistributionChart(); // 繪製損益分布
    } else if (activeChartTab === 'monthly-bar') { // 分頁 4: 模組貢獻柱狀圖
        renderMonthlyBarChart(); // 繪製模組貢獻柱狀圖
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
        x: timeSeries, y: pnlSeries, mode: 'lines', name: '累積淨利 ($0起計)',
        line: { color: '#00e676', width: 3.0 }, fill: 'tozeroy', fillcolor: 'rgba(0, 230, 118, 0.12)'
    }; // 軌跡結束

    const layout = { // 定義圖表面版樣式
        paper_bgcolor: '#131722', plot_bgcolor: '#131722', margin: { l: 70, r: 40, t: 40, b: 40 },
        title: { text: `方案 D 專屬 ${selectedSymbols.size} 款王牌分工收租組合累積淨損益 (時間基準: MT5 伺服器時間)`, font: { color: '#f0f6fc', family: 'Outfit', size: 16 } },
        xaxis: { type: 'date', gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' } },
        yaxis: { gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, tickprefix: '$', zeroline: true, zerolinecolor: 'rgba(255,255,255,0.3)', zerolinewidth: 1.5 },
        hovermode: 'x unified', legend: { orientation: 'h', y: 1.1, font: { color: '#8b949e' } }
    }; // 面版結束

    Plotly.newPlot('main-plotly-chart', [trace], layout, { responsive: true, displayModeBar: true }); // 渲染 Plotly 圖表
} // renderCombinedEquityChart 結束

// 繪製分頁 2：K 線圖與真實進出場買賣訊號點標記
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

    const traceBBUpper = { x: cdata.timestamps, y: cdata.bb_upper, mode: 'lines', name: 'BB 上軌', line: { color: 'rgba(41, 182, 246, 0.4)', width: 1.2, dash: 'dot' }, yaxis: 'y' };
    const traceBBMid   = { x: cdata.timestamps, y: cdata.bb_mid, mode: 'lines', name: 'BB 中軌 (20SMA)', line: { color: 'rgba(255, 167, 38, 0.6)', width: 1.2 }, yaxis: 'y' };
    const traceBBLower = { x: cdata.timestamps, y: cdata.bb_lower, mode: 'lines', name: 'BB 下軌', line: { color: 'rgba(41, 182, 246, 0.4)', width: 1.2, dash: 'dot' }, yaxis: 'y' };

    const buyEntries = symTrades.filter(t => t.type.includes('Buy')); // 多單進場
    const sellEntries = symTrades.filter(t => t.type.includes('Sell')); // 空單進場
    const exits = symTrades; // 全部出場

    const traceBuyMarkers = { // 買入標記 (綠色三角向上)
        x: buyEntries.map(t => t.entry_time), y: buyEntries.map(t => t.entry_price), mode: 'markers', name: '賣出 Put (多單開倉)',
        marker: { symbol: 'triangle-up', size: 11, color: '#00e676', line: { color: '#ffffff', width: 1.5 } }, yaxis: 'y'
    }; // 買入標記結束

    const traceSellMarkers = { // 賣出標記 (紅色三角向下)
        x: sellEntries.map(t => t.entry_time), y: sellEntries.map(t => t.entry_price), mode: 'markers', name: '賣出 Call (空單開倉)',
        marker: { symbol: 'triangle-down', size: 11, color: '#ff1744', line: { color: '#ffffff', width: 1.5 } }, yaxis: 'y'
    }; // 賣出標記結束

    const traceExitMarkers = { // 出場標記 (黃色方塊)
        x: exits.map(t => t.exit_time), y: exits.map(t => t.exit_price), mode: 'markers', name: '平倉出場 (Exit)',
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

// 繪製分頁 3：每筆交易損益分布直方圖
function renderPnlDistributionChart() { // 直方圖繪製函數
    const filteredTrades = globalData.all_trades.filter(t => selectedSymbols.has(t.symbol)); // 取得過濾交易
    const winTrades = filteredTrades.filter(t => t.pnl_usd > 0).map(t => t.pnl_usd); // 獲利金額陣列
    const lossTrades = filteredTrades.filter(t => t.pnl_usd <= 0).map(t => t.pnl_usd); // 虧損金額陣列

    const traceWins = {
        x: winTrades, type: 'histogram', name: '獲利交易 (Wins)',
        marker: { color: '#00e676' }, opacity: 0.85
    }; // 獲利長條

    const traceLosses = {
        x: lossTrades, type: 'histogram', name: '虧損交易 (Losses)',
        marker: { color: '#ff1744' }, opacity: 0.85
    }; // 虧損長條

    const layout = {
        paper_bgcolor: '#131722', plot_bgcolor: '#131722', margin: { l: 70, r: 40, t: 40, b: 40 },
        title: { text: '方案 D 每筆交易實質損益分布 (已扣手續費與點差)', font: { color: '#f0f6fc', family: 'Outfit', size: 16 } },
        xaxis: { gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, tickprefix: '$' },
        yaxis: { gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, title: '交易筆數' },
        barmode: 'overlay', legend: { orientation: 'h', y: 1.1, font: { color: '#8b949e' } }
    }; // 面版結束

    Plotly.newPlot('main-plotly-chart', [traceWins, traceLosses], layout, { responsive: true, displayModeBar: true }); // 渲染圖表
} // renderPnlDistributionChart 結束

// 繪製分頁 4：模組貢獻柱狀圖
function renderMonthlyBarChart() { // 模組貢獻柱狀圖繪製函數
    if (!globalData || !globalData.modules_summary) return; // 檢查

    const modData = globalData.modules_summary.filter(m => selectedSymbols.has(m.symbol)); // 取得勾選模組
    const syms = modData.map(m => `${m.symbol} (${m.timeframe})`); // 標的標籤
    const pnls = modData.map(m => m.total_pnl_usd); // 淨利陣列
    const colors = modData.map(m => symbolColors[m.symbol] || '#00e676'); // 顏色陣列

    const trace = {
        x: syms, y: pnls, type: 'bar', name: '模組實質淨利 (USD)',
        marker: { color: colors }, text: pnls.map(p => `$${p.toFixed(2)}`), textposition: 'auto'
    }; // 柱狀圖

    const layout = {
        paper_bgcolor: '#131722', plot_bgcolor: '#131722', margin: { l: 70, r: 40, t: 40, b: 40 },
        title: { text: '方案 D 各王牌收租模組實質淨利貢獻總覽 (USD)', font: { color: '#f0f6fc', family: 'Outfit', size: 16 } },
        xaxis: { gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' } },
        yaxis: { gridcolor: 'rgba(255,255,255,0.06)', tickfont: { color: '#8b949e', family: 'JetBrains Mono' }, tickprefix: '$' }
    }; // 面版結束

    Plotly.newPlot('main-plotly-chart', [trace], layout, { responsive: true, displayModeBar: true }); // 渲染圖表
} // renderMonthlyBarChart 結束

// 渲染歷史交易明細表格
function renderTradesTable() { // 表格渲染函數
    const tbody = document.getElementById('trades-table-body'); // 取得表體 DOM
    const infoText = document.getElementById('pagination-info-text'); // 取得計數器 DOM
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
    }).sort((a, b) => new Date(b.exit_time || b.entry_time) - new Date(a.exit_time || a.entry_time)); // 依最新出場時間倒序排列 (最新交易顯示於第 1 頁)

    const totalPages = Math.ceil(filtered.length / pageSize) || 1; // 總頁數
    if (currentPage > totalPages) currentPage = totalPages; // 校正頁碼
    const startIndex = (currentPage - 1) * pageSize; // 起始索引
    const endIndex = Math.min(startIndex + pageSize, filtered.length); // 結束索引
    const pageTrades = filtered.slice(startIndex, endIndex); // 抽取

    if (infoText) { // 存在
        infoText.textContent = `顯示第 ${filtered.length > 0 ? startIndex + 1 : 0} - ${endIndex} 筆，共 ${filtered.length} 筆交易 (全量庫: ${globalData.all_trades.length} 筆)`; // 顯示資訊
    } // 判斷結束

    const curPageNum = document.getElementById('current-page-num'); // 頁碼標籤
    if (curPageNum) curPageNum.textContent = currentPage; // 更新頁碼

    if (pageTrades.length === 0) { // 空資料
        tbody.innerHTML = `<tr><td colspan="12" style="text-align:center; padding:30px; color:var(--text-muted);">無符合條件之交易紀錄</td></tr>`; // 提示
    } else { // 有資料
        tbody.innerHTML = pageTrades.map(t => { // 遍歷
            const isWin = t.win; // 獲利
            const pnlClass = isWin ? 'val-bull' : 'val-bear'; // 配色
            const typeBadge = t.type.includes('Buy') ? '<span class="badge-bull">買多 (Short Put)</span>' : '<span class="badge-bear">賣空 (Short Call)</span>'; // 標籤
            const symColor = symbolColors[t.symbol] || '#fff'; // 顏色
            const tradeNum = t.trade_id || t.global_id || 1; // 取得交易序號 (避免 undefined)
            const isHighlight = highlightedTradeId === tradeNum ? 'style="background:rgba(41,182,246,0.15);"' : ''; // 高亮

            return `
                <tr ${isHighlight} onclick="focusTradeOnChart('${t.symbol}', ${tradeNum})" style="cursor:pointer;" title="點擊切換聚焦 ${t.symbol} K線圖">
                    <td style="font-family:var(--font-mono); color:var(--text-secondary); font-size:12px;">#${tradeNum}</td>
                    <td><strong style="color:${symColor}; font-family:var(--font-mono);">${t.symbol}</strong></td>
                    <td style="font-family:var(--font-mono); font-size:12px; color:var(--text-secondary);">${t.timeframe || '15m'}</td>
                    <td>${typeBadge}</td>
                    <td style="font-family:var(--font-mono); font-size:12px; color:var(--text-secondary);">${t.entry_time}</td>
                    <td style="font-family:var(--font-mono);">${t.entry_price}</td>
                    <td style="font-family:var(--font-mono); font-size:12px; color:var(--text-secondary);">${t.exit_time}</td>
                    <td style="font-family:var(--font-mono);">${t.exit_price}</td>
                    <td><strong class="${pnlClass}" style="font-family:var(--font-mono);">${t.pnl_usd >= 0 ? '+' : ''}$${t.pnl_usd.toFixed(2)}</strong></td>
                    <td class="${pnlClass}" style="font-family:var(--font-mono);">${t.pnl_pips >= 0 ? '+' : ''}${t.pnl_pips.toFixed(1)}p</td>
                    <td style="font-family:var(--font-mono); font-size:12px; color:var(--text-muted);">${t.duration_mins} 分</td>
                    <td style="font-size:12px; color:var(--text-secondary);">${t.exit_reason}</td>
                </tr>
            `; // 回傳一列
        }).join(''); // 串接結束
    } // 判斷結束
} // renderTradesTable 結束

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
