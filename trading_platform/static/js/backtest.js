/* ── BACKTEST UI MODULE ────────────────────────────────────────── */

let availableStrategies = [];
let savedStrategies = [];

async function initBacktestUI() {
  await loadAvailableStrategies();
  await loadSavedStrategies();
  await loadBacktestHistory();
}

async function loadAvailableStrategies() {
  try {
    availableStrategies = await api('/api/strategies/available');
    const sel = document.getElementById('bt-strategy');
    sel.innerHTML = '';
    for (const s of availableStrategies) {
      sel.innerHTML += `<option value="${s.name}">${s.label}</option>`;
    }
    onStrategyChange();
  } catch (e) {
    console.error('Failed to load strategies:', e);
  }
}

function onStrategyChange() {
  const type = document.getElementById('bt-strategy').value;
  const strategy = availableStrategies.find(s => s.name === type);
  const container = document.getElementById('bt-strategy-params');
  container.innerHTML = '';
  if (!strategy) return;

  for (const p of strategy.param_schema) {
    const inputType = p.type === 'float' ? 'number' : 'number';
    const step = p.type === 'float' ? '0.1' : '1';
    container.innerHTML += `
      <label>${p.label}</label>
      <input type="${inputType}" id="bt-param-${p.key}" class="input-md"
             value="${p.default}" min="${p.min || ''}" max="${p.max || ''}" step="${step}">
    `;
  }
}

function getStrategyParams() {
  const type = document.getElementById('bt-strategy').value;
  const strategy = availableStrategies.find(s => s.name === type);
  if (!strategy) return {};
  const params = {};
  for (const p of strategy.param_schema) {
    const el = document.getElementById(`bt-param-${p.key}`);
    if (el) params[p.key] = parseFloat(el.value);
  }
  return params;
}

async function runBacktest() {
  const statusEl = document.getElementById('bt-status');
  statusEl.style.display = 'block';
  statusEl.className = 'result-box';
  statusEl.textContent = 'Running backtest...';
  setStatus('BACKTESTING...');

  const symbolsRaw = document.getElementById('bt-symbols').value.trim();
  if (!symbolsRaw) {
    statusEl.className = 'result-box error';
    statusEl.textContent = 'Error: Enter at least one symbol.';
    setStatus('READY');
    return;
  }

  const config = {
    strategy_type: document.getElementById('bt-strategy').value,
    strategy_params: getStrategyParams(),
    symbols: symbolsRaw.split(',').map(s => s.trim().toUpperCase()),
    start_date: document.getElementById('bt-start').value,
    end_date: document.getElementById('bt-end').value,
    timeframe: document.getElementById('bt-timeframe').value,
    initial_capital: parseFloat(document.getElementById('bt-capital').value),
    position_sizing: document.getElementById('bt-pos-sizing').value,
    position_size_value: parseFloat(document.getElementById('bt-pos-value').value),
    commission_pct: parseFloat(document.getElementById('bt-commission').value),
    slippage_pct: parseFloat(document.getElementById('bt-slippage').value),
    allow_short: document.getElementById('bt-short').value === 'true',
    benchmark: document.getElementById('bt-benchmark').value.trim() || null,
  };

  const sl = document.getElementById('bt-stoploss').value;
  const tp = document.getElementById('bt-takeprofit').value;
  if (sl) config.stop_loss_pct = parseFloat(sl);
  if (tp) config.take_profit_pct = parseFloat(tp);

  try {
    const result = await api('/api/backtest', 'POST', config);
    if (result.status === 'failed') {
      statusEl.className = 'result-box error';
      statusEl.textContent = `Failed: ${result.error}`;
      setStatus('READY');
      return;
    }

    statusEl.className = 'result-box success';
    statusEl.textContent = `Backtest completed. Run ID: ${result.run_id}`;
    setStatus('READY');
    displayBacktestResults(result);
    await loadBacktestHistory();
  } catch (e) {
    statusEl.className = 'result-box error';
    statusEl.textContent = `Error: ${e.message}`;
    setStatus('READY');
  }
}

function displayBacktestResults(result) {
  document.getElementById('bt-no-results').style.display = 'none';
  document.getElementById('bt-results').style.display = 'block';

  const m = result.metrics;

  // Metrics grid
  const grid = document.getElementById('bt-metrics-grid');
  grid.innerHTML = '';
  const metricDefs = [
    ['Total Return', fmt(m.total_return, '%'), m.total_return >= 0],
    ['Ann. Return', fmt(m.annualized_return, '%'), m.annualized_return >= 0],
    ['Sharpe Ratio', fmt(m.sharpe_ratio), m.sharpe_ratio >= 0],
    ['Sortino Ratio', fmt(m.sortino_ratio), m.sortino_ratio >= 0],
    ['Max Drawdown', fmt(m.max_drawdown, '%'), false],
    ['Max DD Days', m.max_drawdown_duration_days, false],
    ['Calmar Ratio', fmt(m.calmar_ratio), m.calmar_ratio >= 0],
    ['Win Rate', fmt(m.win_rate, '%'), m.win_rate >= 50],
    ['Profit Factor', fmt(m.profit_factor), m.profit_factor >= 1],
    ['Total Trades', m.total_trades, null],
    ['Avg Win', '$' + fmt(m.avg_win), true],
    ['Avg Loss', '$' + fmt(m.avg_loss), false],
    ['Largest Win', '$' + fmt(m.largest_win), true],
    ['Largest Loss', '$' + fmt(m.largest_loss), false],
    ['Exposure', fmt(m.exposure_pct, '%'), null],
  ];

  for (const [label, value, positive] of metricDefs) {
    const colorClass = positive === true ? 'positive' : positive === false ? 'negative' : '';
    grid.innerHTML += `
      <div class="metric-cell">
        <div class="metric-label">${label}</div>
        <div class="metric-value ${colorClass}">${value}</div>
      </div>
    `;
  }

  // Charts
  Charts.equityCurve('bt-equity-chart', m.equity_curve);
  Charts.drawdownChart('bt-drawdown-chart', m.drawdown_curve);
  Charts.monthlyReturnsHeatmap('bt-monthly-chart', m.monthly_returns);
  Charts.pnlDistribution('bt-pnl-dist-chart', result.trades);

  // Trade log
  const tbody = document.getElementById('bt-trade-log-body');
  tbody.innerHTML = '';
  (result.trades || []).forEach((t, i) => {
    const cls = t.pnl >= 0 ? 'positive' : 'negative';
    tbody.innerHTML += `<tr>
      <td>${i + 1}</td>
      <td>${t.entry_date}</td>
      <td>${t.exit_date}</td>
      <td>${t.side}</td>
      <td class="num">${fmt(t.entry_price)}</td>
      <td class="num">${fmt(t.exit_price)}</td>
      <td class="num">${t.quantity}</td>
      <td class="num ${cls}">$${fmt(t.pnl)}</td>
      <td class="num ${cls}">${fmt(t.pnl_pct)}%</td>
      <td>${t.exit_reason}</td>
    </tr>`;
  });
}

async function loadBacktestHistory() {
  try {
    const runs = await api('/api/backtest/runs');
    const tbody = document.getElementById('bt-history-body');
    tbody.innerHTML = '';
    for (const r of runs) {
      const cls = (r.total_return || 0) >= 0 ? 'positive' : 'negative';
      tbody.innerHTML += `<tr>
        <td>${r.id}</td>
        <td>${r.strategy_type}</td>
        <td>${(r.symbols || []).join(',')}</td>
        <td>${r.start_date} - ${r.end_date}</td>
        <td class="num">$${fmtK(r.initial_capital)}</td>
        <td class="num ${cls}">${fmt(r.total_return)}%</td>
        <td class="num">${fmt(r.sharpe_ratio)}</td>
        <td class="num negative">${fmt(r.max_drawdown)}%</td>
        <td class="num">${r.total_trades || 0}</td>
        <td class="num">${fmt(r.win_rate)}%</td>
        <td>${r.status}</td>
        <td><button class="btn-sm" onclick="viewBacktestRun(${r.id})">VIEW</button> <button class="btn-del" onclick="deleteBacktestRun(${r.id})">DEL</button></td>
      </tr>`;
    }
  } catch (e) {
    console.error('Failed to load backtest history:', e);
  }
}

async function viewBacktestRun(runId) {
  try {
    const r = await api(`/api/backtest/runs/${runId}`);
    if (r.status !== 'completed') {
      alert(`Run ${runId} status: ${r.status}. ${r.error_message || ''}`);
      return;
    }
    displayBacktestResults({
      run_id: r.id,
      metrics: {
        total_return: r.total_return,
        annualized_return: r.annualized_return,
        sharpe_ratio: r.sharpe_ratio,
        sortino_ratio: r.sortino_ratio,
        max_drawdown: r.max_drawdown,
        max_drawdown_duration_days: r.max_drawdown_duration_days,
        calmar_ratio: r.calmar_ratio,
        win_rate: r.win_rate,
        profit_factor: r.profit_factor,
        total_trades: r.total_trades,
        avg_win: r.avg_win,
        avg_loss: r.avg_loss,
        largest_win: r.largest_win,
        largest_loss: r.largest_loss,
        exposure_pct: r.exposure_pct,
        equity_curve: r.equity_curve,
        drawdown_curve: r.drawdown_curve,
        monthly_returns: r.monthly_returns,
      },
      trades: r.trade_log,
    });
  } catch (e) {
    alert('Error loading run: ' + e.message);
  }
}

async function deleteBacktestRun(runId) {
  try {
    await api(`/api/backtest/runs/${runId}`, 'DELETE');
    await loadBacktestHistory();
  } catch (e) {
    alert('Delete failed: ' + e.message);
  }
}

async function saveStrategy() {
  const name = document.getElementById('bt-save-name').value.trim();
  if (!name) { alert('Enter a strategy name'); return; }
  try {
    await api('/api/strategies', 'POST', {
      name,
      strategy_type: document.getElementById('bt-strategy').value,
      parameters: getStrategyParams(),
    });
    await loadSavedStrategies();
  } catch (e) {
    alert('Save failed: ' + e.message);
  }
}

async function loadSavedStrategies() {
  try {
    savedStrategies = await api('/api/strategies');
    const sel = document.getElementById('bt-load-strategy');
    sel.innerHTML = '<option value="">-- Load --</option>';
    for (const s of savedStrategies) {
      sel.innerHTML += `<option value="${s.id}">${s.name} (${s.strategy_type})</option>`;
    }
  } catch (e) {
    console.error('Failed to load saved strategies:', e);
  }
}

async function loadSavedStrategy() {
  const id = document.getElementById('bt-load-strategy').value;
  if (!id) return;
  const s = savedStrategies.find(x => x.id === parseInt(id));
  if (!s) return;

  document.getElementById('bt-strategy').value = s.strategy_type;
  onStrategyChange();

  // Populate params after a short delay to let DOM update
  setTimeout(() => {
    for (const [k, v] of Object.entries(s.parameters)) {
      const el = document.getElementById(`bt-param-${k}`);
      if (el) el.value = v;
    }
  }, 50);
}

function fmt(val, suffix = '') {
  if (val == null || isNaN(val)) return '--';
  return parseFloat(val).toFixed(2) + suffix;
}

function fmtK(val) {
  if (val == null) return '--';
  if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
  if (val >= 1000) return (val / 1000).toFixed(0) + 'K';
  return val.toFixed(0);
}
