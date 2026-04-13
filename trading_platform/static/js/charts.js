/* ── CHART MODULE ─────────────────────────────────────────────── */
/* Plotly-based charting for the trading platform */

const CHART_LAYOUT_BASE = {
  paper_bgcolor: '#111',
  plot_bgcolor: '#111',
  font: { family: 'Consolas, Monaco, monospace', size: 10, color: '#999' },
  margin: { t: 10, r: 30, b: 30, l: 50 },
  xaxis: {
    gridcolor: '#222', linecolor: '#333', zerolinecolor: '#333',
    tickfont: { size: 9 },
  },
  yaxis: {
    gridcolor: '#222', linecolor: '#333', zerolinecolor: '#333',
    tickfont: { size: 9 },
  },
  showlegend: true,
  legend: { x: 0, y: 1.12, orientation: 'h', font: { size: 9 } },
};

const CHART_CONFIG = {
  responsive: true,
  displayModeBar: true,
  modeBarButtonsToRemove: ['sendDataToCloud', 'lasso2d', 'select2d'],
  displaylogo: false,
};


const Charts = {

  // ── Price Chart (Line or Candlestick) ──────────────────────
  priceChart(containerId, data, options = {}) {
    if (!data || data.length === 0) {
      document.getElementById(containerId).innerHTML = '<div class="loading">No data</div>';
      return;
    }
    const dates = data.map(d => d.date);
    const traces = [];
    const chartType = options.type || 'line';

    if (chartType === 'candlestick' && data[0].open != null) {
      traces.push({
        type: 'candlestick',
        x: dates,
        open: data.map(d => d.open),
        high: data.map(d => d.high),
        low: data.map(d => d.low),
        close: data.map(d => d.close),
        increasing: { line: { color: '#26a69a' } },
        decreasing: { line: { color: '#ef5350' } },
        name: options.symbol || 'Price',
      });
    } else if (chartType === 'ohlc' && data[0].open != null) {
      traces.push({
        type: 'ohlc',
        x: dates,
        open: data.map(d => d.open),
        high: data.map(d => d.high),
        low: data.map(d => d.low),
        close: data.map(d => d.close),
        increasing: { line: { color: '#26a69a' } },
        decreasing: { line: { color: '#ef5350' } },
        name: options.symbol || 'Price',
      });
    } else {
      traces.push({
        type: 'scatter', mode: 'lines',
        x: dates, y: data.map(d => d.close),
        line: { color: '#4a9eff', width: 1 },
        name: options.symbol || 'Close',
      });
    }

    // Overlays
    if (options.overlays) {
      const closes = data.map(d => d.close);
      for (const ov of options.overlays) {
        if (ov === 'none') continue;
        const match = ov.match(/^(sma|ema)(\d+)$/);
        if (match) {
          const type = match[1];
          const period = parseInt(match[2]);
          const vals = type === 'sma' ? sma(closes, period) : ema(closes, period);
          traces.push({
            type: 'scatter', mode: 'lines',
            x: dates, y: vals,
            line: { width: 1, dash: 'dot' },
            name: `${type.toUpperCase()} ${period}`,
          });
        } else if (ov === 'bb') {
          const mid = sma(closes, 20);
          const std = rollingStd(closes, 20);
          const upper = mid.map((m, i) => m != null && std[i] != null ? m + 2 * std[i] : null);
          const lower = mid.map((m, i) => m != null && std[i] != null ? m - 2 * std[i] : null);
          traces.push(
            { type: 'scatter', mode: 'lines', x: dates, y: upper, line: { color: '#888', width: 1, dash: 'dot' }, name: 'BB Upper' },
            { type: 'scatter', mode: 'lines', x: dates, y: lower, line: { color: '#888', width: 1, dash: 'dot' }, name: 'BB Lower', fill: 'tonexty', fillcolor: 'rgba(100,100,100,0.05)' },
          );
        }
      }
    }

    const layout = {
      ...CHART_LAYOUT_BASE,
      xaxis: { ...CHART_LAYOUT_BASE.xaxis, rangeslider: { visible: false } },
      yaxis: { ...CHART_LAYOUT_BASE.yaxis, title: { text: 'Price', font: { size: 10 } } },
    };

    Plotly.newPlot(containerId, traces, layout, CHART_CONFIG);
  },


  // ── Volume / RSI / MACD Sub-chart ──────────────────────────
  subChart(containerId, data, type = 'volume') {
    if (!data || data.length === 0) return;
    const dates = data.map(d => d.date);
    const traces = [];
    const layout = { ...CHART_LAYOUT_BASE, margin: { ...CHART_LAYOUT_BASE.margin, t: 5 } };

    if (type === 'volume') {
      const colors = data.map((d, i) => {
        if (i === 0) return '#555';
        return d.close >= data[i - 1].close ? '#26a69a' : '#ef5350';
      });
      traces.push({
        type: 'bar', x: dates, y: data.map(d => d.volume),
        marker: { color: colors }, name: 'Volume',
      });
      layout.yaxis = { ...layout.yaxis, title: { text: 'Volume', font: { size: 10 } } };
    } else if (type === 'rsi') {
      const closes = data.map(d => d.close);
      const rsiVals = computeRSI(closes, 14);
      traces.push({
        type: 'scatter', mode: 'lines',
        x: dates, y: rsiVals,
        line: { color: '#cc6', width: 1 }, name: 'RSI 14',
      });
      // Add 70/30 lines
      traces.push(
        { type: 'scatter', mode: 'lines', x: [dates[0], dates[dates.length - 1]], y: [70, 70], line: { color: '#633', width: 1, dash: 'dash' }, showlegend: false },
        { type: 'scatter', mode: 'lines', x: [dates[0], dates[dates.length - 1]], y: [30, 30], line: { color: '#363', width: 1, dash: 'dash' }, showlegend: false },
      );
      layout.yaxis = { ...layout.yaxis, range: [0, 100], title: { text: 'RSI', font: { size: 10 } } };
    } else if (type === 'macd') {
      const closes = data.map(d => d.close);
      const ema12 = ema(closes, 12);
      const ema26 = ema(closes, 26);
      const macdLine = ema12.map((v, i) => v != null && ema26[i] != null ? v - ema26[i] : null);
      const macdSignal = ema(macdLine.filter(v => v != null), 9);
      // Pad signal line
      const padLen = macdLine.length - macdSignal.length;
      const paddedSignal = Array(padLen).fill(null).concat(macdSignal);
      const hist = macdLine.map((v, i) => v != null && paddedSignal[i] != null ? v - paddedSignal[i] : null);

      traces.push(
        { type: 'scatter', mode: 'lines', x: dates, y: macdLine, line: { color: '#4a9eff', width: 1 }, name: 'MACD' },
        { type: 'scatter', mode: 'lines', x: dates, y: paddedSignal, line: { color: '#ff6a4a', width: 1 }, name: 'Signal' },
        {
          type: 'bar', x: dates, y: hist,
          marker: { color: hist.map(v => v != null && v >= 0 ? '#26a69a' : '#ef5350') },
          name: 'Histogram',
        },
      );
      layout.yaxis = { ...layout.yaxis, title: { text: 'MACD', font: { size: 10 } } };
    }

    Plotly.newPlot(containerId, traces, layout, CHART_CONFIG);
  },


  // ── Equity Curve ───────────────────────────────────────────
  equityCurve(containerId, eqData) {
    if (!eqData || eqData.length === 0) return;
    const traces = [{
      type: 'scatter', mode: 'lines',
      x: eqData.map(d => d.date), y: eqData.map(d => d.value),
      line: { color: '#4a9eff', width: 1.5 },
      fill: 'tozeroy', fillcolor: 'rgba(74,158,255,0.05)',
      name: 'Equity',
    }];
    const layout = {
      ...CHART_LAYOUT_BASE,
      yaxis: { ...CHART_LAYOUT_BASE.yaxis, title: { text: 'Portfolio Value ($)', font: { size: 10 } } },
    };
    Plotly.newPlot(containerId, traces, layout, CHART_CONFIG);
  },


  // ── Drawdown Chart ─────────────────────────────────────────
  drawdownChart(containerId, ddData) {
    if (!ddData || ddData.length === 0) return;
    const traces = [{
      type: 'scatter', mode: 'lines',
      x: ddData.map(d => d.date), y: ddData.map(d => d.value),
      line: { color: '#ef5350', width: 1 },
      fill: 'tozeroy', fillcolor: 'rgba(239,83,80,0.1)',
      name: 'Drawdown %',
    }];
    const layout = {
      ...CHART_LAYOUT_BASE,
      yaxis: { ...CHART_LAYOUT_BASE.yaxis, title: { text: 'Drawdown (%)', font: { size: 10 } } },
    };
    Plotly.newPlot(containerId, traces, layout, CHART_CONFIG);
  },


  // ── Monthly Returns Heatmap ────────────────────────────────
  monthlyReturnsHeatmap(containerId, monthlyData) {
    if (!monthlyData || Object.keys(monthlyData).length === 0) {
      document.getElementById(containerId).innerHTML = '<div class="loading">No monthly data</div>';
      return;
    }
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const entries = Object.entries(monthlyData).sort();
    const years = [...new Set(entries.map(([k]) => k.split('-')[0]))];
    const z = [];
    const text = [];
    for (const year of years) {
      const row = [];
      const textRow = [];
      for (let m = 1; m <= 12; m++) {
        const key = `${year}-${String(m).padStart(2, '0')}`;
        const val = monthlyData[key] ?? null;
        row.push(val);
        textRow.push(val != null ? val.toFixed(1) + '%' : '');
      }
      z.push(row);
      text.push(textRow);
    }

    const traces = [{
      type: 'heatmap',
      x: months, y: years, z: z, text: text,
      texttemplate: '%{text}',
      colorscale: [
        [0, '#ef5350'],
        [0.5, '#1a1a1a'],
        [1, '#26a69a'],
      ],
      zmid: 0,
      colorbar: { title: { text: '%', font: { size: 10 } }, tickfont: { size: 9 } },
    }];

    const layout = {
      ...CHART_LAYOUT_BASE,
      xaxis: { ...CHART_LAYOUT_BASE.xaxis },
      yaxis: { ...CHART_LAYOUT_BASE.yaxis, autorange: 'reversed' },
    };
    Plotly.newPlot(containerId, traces, layout, CHART_CONFIG);
  },


  // ── P&L Distribution ───────────────────────────────────────
  pnlDistribution(containerId, trades) {
    if (!trades || trades.length === 0) {
      document.getElementById(containerId).innerHTML = '<div class="loading">No trades</div>';
      return;
    }
    const pnls = trades.map(t => t.pnl);
    const colors = pnls.map(v => v >= 0 ? '#26a69a' : '#ef5350');
    const traces = [{
      type: 'histogram',
      x: pnls,
      marker: { color: '#4a9eff', line: { color: '#333', width: 1 } },
      name: 'Trade P&L',
      nbinsx: Math.min(50, Math.max(10, Math.ceil(Math.sqrt(pnls.length)))),
    }];
    const layout = {
      ...CHART_LAYOUT_BASE,
      xaxis: { ...CHART_LAYOUT_BASE.xaxis, title: { text: 'P&L ($)', font: { size: 10 } } },
      yaxis: { ...CHART_LAYOUT_BASE.yaxis, title: { text: 'Count', font: { size: 10 } } },
    };
    Plotly.newPlot(containerId, traces, layout, CHART_CONFIG);
  },
};


/* ── TECHNICAL INDICATOR HELPERS ─────────────────────────────── */

function sma(data, period) {
  const result = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) { result.push(null); continue; }
    let sum = 0;
    for (let j = 0; j < period; j++) sum += data[i - j];
    result.push(sum / period);
  }
  return result;
}

function ema(data, period) {
  const k = 2 / (period + 1);
  const result = [];
  let prev = null;
  for (let i = 0; i < data.length; i++) {
    if (data[i] == null) { result.push(null); continue; }
    if (prev == null) { prev = data[i]; result.push(prev); continue; }
    prev = data[i] * k + prev * (1 - k);
    result.push(prev);
  }
  return result;
}

function rollingStd(data, period) {
  const result = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) { result.push(null); continue; }
    const slice = data.slice(i - period + 1, i + 1);
    const mean = slice.reduce((a, b) => a + b, 0) / period;
    const variance = slice.reduce((a, b) => a + (b - mean) ** 2, 0) / period;
    result.push(Math.sqrt(variance));
  }
  return result;
}

function computeRSI(data, period) {
  const result = Array(data.length).fill(null);
  if (data.length < period + 1) return result;
  let avgGain = 0, avgLoss = 0;
  for (let i = 1; i <= period; i++) {
    const change = data[i] - data[i - 1];
    if (change > 0) avgGain += change;
    else avgLoss += Math.abs(change);
  }
  avgGain /= period;
  avgLoss /= period;
  result[period] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);

  for (let i = period + 1; i < data.length; i++) {
    const change = data[i] - data[i - 1];
    avgGain = (avgGain * (period - 1) + Math.max(change, 0)) / period;
    avgLoss = (avgLoss * (period - 1) + Math.max(-change, 0)) / period;
    result[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  }
  return result;
}
