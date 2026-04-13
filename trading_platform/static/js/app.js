/* ── MAIN APP CONTROLLER ──────────────────────────────────────── */

// ── API Helper ────────────────────────────────────────────────
async function api(url, method = 'GET', body = null) {
  const opts = { method, headers: {} };
  if (body && method !== 'GET') {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || JSON.stringify(err));
  }
  return res.json();
}

function setStatus(text) {
  const el = document.getElementById('header-status');
  el.textContent = text;
  el.style.color = text === 'READY' ? '#5a5' : '#cc6';
}

// ── Clock ─────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  document.getElementById('clock').textContent = now.toLocaleString('en-US', {
    hour12: false, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}
setInterval(updateClock, 1000);
updateClock();

// ── Tab Navigation ────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
    onTabActivated(tab.dataset.tab);
  });
});

function onTabActivated(tabName) {
  if (tabName === 'dashboard') refreshDashboard();
  else if (tabName === 'trading') refreshTrading();
  else if (tabName === 'backtest') initBacktestUI();
  else if (tabName === 'data') refreshDataTab();
  else if (tabName === 'analysis') refreshAnalysis();
}

// ══════════════════════════════════════════════════════════════
// ── DASHBOARD ────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════
async function refreshDashboard() {
  await Promise.all([
    loadPortfolioSummary(),
    loadWatchlist(),
    loadDashRecentTrades(),
    loadDashDataSources(),
    populateSymbolSelectors(),
  ]);
  loadDashChart();
}

async function loadPortfolioSummary() {
  try {
    const p = await api('/api/portfolios/1');
    document.getElementById('ps-cash').textContent = '$' + fmtN(p.cash);
    document.getElementById('ps-holdings').textContent = '$' + fmtN(p.holdings_value);
    document.getElementById('ps-total').textContent = '$' + fmtN(p.total_value);
    const retEl = document.getElementById('ps-return');
    retEl.textContent = p.total_return_pct.toFixed(2) + '%';
    retEl.className = p.total_return_pct >= 0 ? 'positive' : 'negative';

    const tbody = document.getElementById('holdings-body');
    tbody.innerHTML = '';
    for (const h of p.holdings) {
      const cls = h.pnl >= 0 ? 'positive' : 'negative';
      tbody.innerHTML += `<tr>
        <td>${h.symbol}</td>
        <td class="num">${h.quantity}</td>
        <td class="num">$${fmtN(h.avg_cost)}</td>
        <td class="num">$${fmtN(h.current_price)}</td>
        <td class="num">$${fmtN(h.market_value)}</td>
        <td class="num ${cls}">$${fmtN(h.pnl)}</td>
        <td class="num ${cls}">${h.pnl_pct.toFixed(2)}%</td>
      </tr>`;
    }
  } catch (e) {
    console.error('Portfolio load error:', e);
  }
}

async function loadWatchlist() {
  try {
    const items = await api('/api/watchlist');
    const tbody = document.getElementById('watchlist-body');
    tbody.innerHTML = '';
    for (const w of items) {
      tbody.innerHTML += `<tr>
        <td>${w.symbol}</td>
        <td>${w.notes || ''}</td>
        <td><button class="btn-del" onclick="removeWatchlist('${w.symbol}')">X</button></td>
      </tr>`;
    }
  } catch (e) {
    console.error('Watchlist load error:', e);
  }
}

async function addWatchlist() {
  const sym = document.getElementById('wl-symbol').value.trim().toUpperCase();
  if (!sym) return;
  const notes = document.getElementById('wl-notes').value.trim();
  await api('/api/watchlist', 'POST', { symbol: sym, notes });
  document.getElementById('wl-symbol').value = '';
  document.getElementById('wl-notes').value = '';
  await loadWatchlist();
}

async function removeWatchlist(symbol) {
  await api(`/api/watchlist/${symbol}`, 'DELETE');
  await loadWatchlist();
}

async function loadDashRecentTrades() {
  try {
    const trades = await api('/api/trades/1');
    const tbody = document.getElementById('recent-trades-body');
    tbody.innerHTML = '';
    for (const t of trades.slice(0, 20)) {
      const cls = t.side === 'BUY' ? 'positive' : 'negative';
      tbody.innerHTML += `<tr>
        <td>${t.executed_at.substring(0, 16)}</td>
        <td>${t.symbol}</td>
        <td class="${cls}">${t.side}</td>
        <td class="num">${t.quantity}</td>
        <td class="num">$${fmtN(t.price)}</td>
        <td class="num">$${fmtN(Math.abs(t.total_cost))}</td>
      </tr>`;
    }
  } catch (e) {
    console.error('Recent trades load error:', e);
  }
}

async function loadDashDataSources() {
  try {
    const summary = await api('/api/data-summary');
    const tbody = document.getElementById('dash-data-body');
    tbody.innerHTML = '';
    for (const s of summary) {
      tbody.innerHTML += `<tr>
        <td>${s.symbol}</td>
        <td class="num">${s.bars}</td>
        <td>${s.start_date || '--'}</td>
        <td>${s.end_date || '--'}</td>
        <td>${s.source || '--'}</td>
      </tr>`;
    }
  } catch (e) {
    console.error('Data sources load error:', e);
  }
}

async function loadDashChart() {
  const sel = document.getElementById('dash-chart-symbol');
  const symbol = sel.value;
  if (!symbol) {
    document.getElementById('dash-price-chart').innerHTML = '<div class="loading">No data loaded. Upload data in DATA MGMT tab.</div>';
    return;
  }
  try {
    const data = await api(`/api/market-data/${symbol}`);
    Charts.priceChart('dash-price-chart', data, { symbol, type: 'line' });
  } catch (e) {
    console.error('Chart load error:', e);
  }
}


// ══════════════════════════════════════════════════════════════
// ── TRADING ──────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════
async function refreshTrading() {
  await loadPortfolioSelector();
  await Promise.all([loadTradeHistory(), loadTradingPositions()]);
}

async function loadPortfolioSelector() {
  try {
    const portfolios = await api('/api/portfolios');
    const sel = document.getElementById('trade-portfolio');
    sel.innerHTML = '';
    for (const p of portfolios) {
      sel.innerHTML += `<option value="${p.id}">${p.name} ($${fmtN(p.current_cash)} cash)</option>`;
    }
  } catch (e) {
    console.error('Portfolio selector error:', e);
  }
}

async function executeTrade() {
  const resultEl = document.getElementById('trade-result');
  const symbol = document.getElementById('trade-symbol').value.trim();
  const price = document.getElementById('trade-price').value;
  if (!symbol || !price) {
    resultEl.style.display = 'block';
    resultEl.className = 'result-box error';
    resultEl.textContent = 'Symbol and price are required.';
    return;
  }

  setStatus('EXECUTING...');
  try {
    const result = await api('/api/trades', 'POST', {
      portfolio_id: parseInt(document.getElementById('trade-portfolio').value),
      symbol,
      side: document.getElementById('trade-side').value,
      quantity: document.getElementById('trade-qty').value,
      price,
      commission: document.getElementById('trade-comm').value,
      slippage: document.getElementById('trade-slip').value,
      notes: document.getElementById('trade-notes').value,
    });
    resultEl.style.display = 'block';
    resultEl.className = 'result-box success';
    resultEl.textContent = `${result.side} ${result.quantity} ${result.symbol} @ $${fmtN(result.price)} | Total: $${fmtN(Math.abs(result.total_cost))}`;
    await Promise.all([loadTradeHistory(), loadTradingPositions(), loadPortfolioSelector()]);
  } catch (e) {
    resultEl.style.display = 'block';
    resultEl.className = 'result-box error';
    resultEl.textContent = e.message;
  }
  setStatus('READY');
}

async function loadTradeHistory() {
  try {
    const pid = document.getElementById('trade-portfolio').value || 1;
    const trades = await api(`/api/trades/${pid}`);
    const tbody = document.getElementById('trade-history-body');
    tbody.innerHTML = '';
    for (const t of trades) {
      const cls = t.side === 'BUY' ? 'positive' : 'negative';
      tbody.innerHTML += `<tr>
        <td>${t.id}</td>
        <td>${t.executed_at.substring(0, 19)}</td>
        <td>${t.symbol}</td>
        <td class="${cls}">${t.side}</td>
        <td class="num">${t.quantity}</td>
        <td class="num">$${fmtN(t.price)}</td>
        <td class="num">$${fmtN(t.commission)}</td>
        <td class="num">$${fmtN(Math.abs(t.total_cost))}</td>
        <td>${t.source}</td>
        <td>${t.notes || ''}</td>
      </tr>`;
    }
  } catch (e) {
    console.error('Trade history error:', e);
  }
}

async function loadTradingPositions() {
  try {
    const pid = document.getElementById('trade-portfolio').value || 1;
    const p = await api(`/api/portfolios/${pid}`);
    const tbody = document.getElementById('trading-positions-body');
    tbody.innerHTML = '';
    for (const h of p.holdings) {
      const cls = h.pnl >= 0 ? 'positive' : 'negative';
      tbody.innerHTML += `<tr>
        <td>${h.symbol}</td>
        <td class="num">${h.quantity}</td>
        <td class="num">$${fmtN(h.avg_cost)}</td>
        <td class="num">$${fmtN(h.current_price)}</td>
        <td class="num">$${fmtN(h.market_value)}</td>
        <td class="num ${cls}">$${fmtN(h.pnl)}</td>
        <td class="num ${cls}">${h.pnl_pct.toFixed(2)}%</td>
      </tr>`;
    }
  } catch (e) {
    console.error('Positions error:', e);
  }
}


// ══════════════════════════════════════════════════════════════
// ── DATA MANAGEMENT ──────────────────────────────────────────
// ══════════════════════════════════════════════════════════════
async function refreshDataTab() {
  await Promise.all([loadDataSources(), populateSymbolSelectors()]);
  loadDataView();
}

async function uploadCSV() {
  const fileInput = document.getElementById('csv-file');
  const resultEl = document.getElementById('csv-result');
  if (!fileInput.files.length) {
    resultEl.style.display = 'block';
    resultEl.className = 'result-box error';
    resultEl.textContent = 'Select a CSV file.';
    return;
  }

  setStatus('UPLOADING...');
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  const symbol = document.getElementById('csv-symbol').value.trim();
  const source = document.getElementById('csv-source').value.trim();
  if (symbol) formData.append('symbol', symbol);
  if (source) formData.append('source_name', source);

  try {
    const res = await fetch('/api/market-data/upload', { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Upload failed');
    resultEl.style.display = 'block';
    resultEl.className = 'result-box success';
    resultEl.textContent = `Loaded ${data.rows_loaded} rows for ${data.symbol} (${data.date_range.start} to ${data.date_range.end})`;
    await Promise.all([loadDataSources(), populateSymbolSelectors()]);
    loadDataView();
  } catch (e) {
    resultEl.style.display = 'block';
    resultEl.className = 'result-box error';
    resultEl.textContent = e.message;
  }
  setStatus('READY');
}

function addManualRow() {
  const tbody = document.getElementById('manual-entry-body');
  tbody.innerHTML += `<tr>
    <td><input type="date" class="input-sm me-date"></td>
    <td><input type="number" class="input-sm me-open" step="0.01"></td>
    <td><input type="number" class="input-sm me-high" step="0.01"></td>
    <td><input type="number" class="input-sm me-low" step="0.01"></td>
    <td><input type="number" class="input-sm me-close" step="0.01"></td>
    <td><input type="number" class="input-sm me-vol" step="1"></td>
  </tr>`;
}

async function submitManualData() {
  const symbol = document.getElementById('manual-symbol').value.trim();
  const resultEl = document.getElementById('manual-result');
  if (!symbol) {
    resultEl.style.display = 'block';
    resultEl.className = 'result-box error';
    resultEl.textContent = 'Enter a symbol.';
    return;
  }

  const rows = [];
  document.querySelectorAll('#manual-entry-body tr').forEach(tr => {
    const date = tr.querySelector('.me-date').value;
    const close = tr.querySelector('.me-close').value;
    if (date && close) {
      rows.push({
        date,
        open: parseFloat(tr.querySelector('.me-open').value) || null,
        high: parseFloat(tr.querySelector('.me-high').value) || null,
        low: parseFloat(tr.querySelector('.me-low').value) || null,
        close: parseFloat(close),
        volume: parseFloat(tr.querySelector('.me-vol').value) || null,
      });
    }
  });

  if (rows.length === 0) {
    resultEl.style.display = 'block';
    resultEl.className = 'result-box error';
    resultEl.textContent = 'Enter at least one row with date and close price.';
    return;
  }

  try {
    const result = await api('/api/market-data/manual', 'POST', { symbol, rows });
    resultEl.style.display = 'block';
    resultEl.className = 'result-box success';
    resultEl.textContent = `Loaded ${result.rows_loaded} rows for ${result.symbol}`;
    await Promise.all([loadDataSources(), populateSymbolSelectors()]);
    loadDataView();
  } catch (e) {
    resultEl.style.display = 'block';
    resultEl.className = 'result-box error';
    resultEl.textContent = e.message;
  }
}

async function loadDataSources() {
  try {
    const sources = await api('/api/data-sources');
    const tbody = document.getElementById('sources-body');
    tbody.innerHTML = '';
    for (const s of sources) {
      tbody.innerHTML += `<tr>
        <td>${s.name}</td>
        <td>${s.source_type}</td>
        <td>${(s.symbols_loaded || []).join(', ')}</td>
        <td>${s.status}</td>
        <td>${s.last_sync ? s.last_sync.substring(0, 19) : '--'}</td>
      </tr>`;
    }
  } catch (e) {
    console.error('Data sources error:', e);
  }
}

async function loadDataView() {
  const sel = document.getElementById('data-view-symbol');
  const symbol = sel.value;
  if (!symbol) return;

  try {
    const data = await api(`/api/market-data/${symbol}`);
    const info = document.getElementById('data-view-info');
    info.textContent = `${data.length} bars`;

    // Table
    const tbody = document.getElementById('data-view-body');
    tbody.innerHTML = '';
    for (const d of data.slice(-200)) {
      tbody.innerHTML += `<tr>
        <td>${d.date}</td>
        <td class="num">${fmtN(d.open)}</td>
        <td class="num">${fmtN(d.high)}</td>
        <td class="num">${fmtN(d.low)}</td>
        <td class="num">${fmtN(d.close)}</td>
        <td class="num">${d.volume != null ? Math.round(d.volume).toLocaleString() : '--'}</td>
        <td class="num">${fmtN(d.adj_close)}</td>
      </tr>`;
    }

    // Chart
    Charts.priceChart('data-price-chart', data, { symbol, type: 'line' });
  } catch (e) {
    console.error('Data view error:', e);
  }
}


// ══════════════════════════════════════════════════════════════
// ── ANALYSIS ─────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════
async function refreshAnalysis() {
  await populateSymbolSelectors();
  loadAnalysis();
}

async function loadAnalysis() {
  const symbol = document.getElementById('analysis-symbol').value;
  if (!symbol) {
    document.getElementById('analysis-main-chart').innerHTML = '<div class="loading">No data loaded.</div>';
    return;
  }

  try {
    const data = await api(`/api/market-data/${symbol}`);
    if (data.length === 0) return;

    const chartType = document.getElementById('analysis-chart-type').value;
    const overlay1 = document.getElementById('analysis-overlay1').value;
    const overlay2 = document.getElementById('analysis-overlay2').value;
    const subType = document.getElementById('analysis-subchart').value;

    Charts.priceChart('analysis-main-chart', data, {
      symbol, type: chartType, overlays: [overlay1, overlay2],
    });
    Charts.subChart('analysis-sub-chart', data, subType);

    // Statistics
    const closes = data.map(d => d.close);
    const returns = [];
    for (let i = 1; i < closes.length; i++) {
      returns.push((closes[i] - closes[i - 1]) / closes[i - 1]);
    }

    const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
    const std = Math.sqrt(returns.reduce((a, b) => a + (b - mean) ** 2, 0) / returns.length);
    const totalRet = (closes[closes.length - 1] / closes[0] - 1) * 100;
    const minPrice = Math.min(...closes);
    const maxPrice = Math.max(...closes);
    const volumes = data.map(d => d.volume).filter(v => v != null);
    const avgVol = volumes.length > 0 ? volumes.reduce((a, b) => a + b, 0) / volumes.length : 0;

    const stats = document.getElementById('analysis-stats');
    stats.innerHTML = '';
    const statDefs = [
      ['Last Close', '$' + fmtN(closes[closes.length - 1])],
      ['Total Return', totalRet.toFixed(2) + '%'],
      ['Daily Avg Return', (mean * 100).toFixed(4) + '%'],
      ['Daily Volatility', (std * 100).toFixed(4) + '%'],
      ['Ann. Volatility', (std * Math.sqrt(252) * 100).toFixed(2) + '%'],
      ['52w High', '$' + fmtN(maxPrice)],
      ['52w Low', '$' + fmtN(minPrice)],
      ['Avg Volume', avgVol > 0 ? Math.round(avgVol).toLocaleString() : '--'],
      ['Data Points', data.length.toString()],
    ];
    for (const [label, value] of statDefs) {
      stats.innerHTML += `<div class="metric-cell"><div class="metric-label">${label}</div><div class="metric-value">${value}</div></div>`;
    }
  } catch (e) {
    console.error('Analysis error:', e);
  }
}


// ══════════════════════════════════════════════════════════════
// ── SHARED ───────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════
async function populateSymbolSelectors() {
  try {
    const symbols = await api('/api/symbols');
    const selectors = [
      'dash-chart-symbol', 'data-view-symbol', 'analysis-symbol',
    ];
    for (const selId of selectors) {
      const sel = document.getElementById(selId);
      if (!sel) continue;
      const current = sel.value;
      sel.innerHTML = '';
      for (const s of symbols) {
        sel.innerHTML += `<option value="${s.symbol}">${s.symbol} (${s.count})</option>`;
      }
      if (current && symbols.find(s => s.symbol === current)) {
        sel.value = current;
      }
    }
  } catch (e) {
    console.error('Symbol selectors error:', e);
  }
}

function fmtN(val) {
  if (val == null || isNaN(val)) return '--';
  return parseFloat(val).toFixed(2);
}


// ── INIT ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  refreshDashboard();
});
