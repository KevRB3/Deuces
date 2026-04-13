import numpy as np
import pandas as pd


def compute_metrics(equity_curve: pd.Series, trades: list[dict],
                    initial_capital: float, risk_free_rate: float = 0.02) -> dict:
    """Compute comprehensive backtest performance metrics."""
    if equity_curve.empty:
        return _empty_metrics()

    returns = equity_curve.pct_change().dropna()
    total_return = (equity_curve.iloc[-1] / initial_capital) - 1
    n_days = (equity_curve.index[-1] - equity_curve.index[0]).days
    n_years = max(n_days / 365.25, 1 / 365.25)
    annualized_return = (1 + total_return) ** (1 / n_years) - 1

    # Sharpe ratio (annualized)
    if returns.std() > 0:
        excess_returns = returns - risk_free_rate / 252
        sharpe = np.sqrt(252) * excess_returns.mean() / returns.std()
    else:
        sharpe = 0.0

    # Sortino ratio
    downside = returns[returns < 0]
    if len(downside) > 0 and downside.std() > 0:
        sortino = np.sqrt(252) * (returns.mean() - risk_free_rate / 252) / downside.std()
    else:
        sortino = 0.0

    # Drawdown
    peak = equity_curve.cummax()
    drawdown = (equity_curve - peak) / peak
    max_dd = drawdown.min()

    # Max drawdown duration
    dd_duration = 0
    max_dd_duration = 0
    for i in range(1, len(drawdown)):
        if drawdown.iloc[i] < 0:
            dd_duration += 1
            max_dd_duration = max(max_dd_duration, dd_duration)
        else:
            dd_duration = 0

    # Calmar ratio
    calmar = annualized_return / abs(max_dd) if max_dd != 0 else 0.0

    # Trade metrics
    wins = [t for t in trades if t.get("pnl", 0) > 0]
    losses = [t for t in trades if t.get("pnl", 0) < 0]
    total_trades = len(trades)
    win_rate = len(wins) / total_trades if total_trades > 0 else 0

    total_win = sum(t["pnl"] for t in wins) if wins else 0
    total_loss = abs(sum(t["pnl"] for t in losses)) if losses else 0
    profit_factor = total_win / total_loss if total_loss > 0 else float("inf") if total_win > 0 else 0

    avg_win = total_win / len(wins) if wins else 0
    avg_loss = -total_loss / len(losses) if losses else 0
    largest_win = max((t["pnl"] for t in wins), default=0)
    largest_loss = min((t["pnl"] for t in losses), default=0)

    # Exposure
    if total_trades > 0 and n_days > 0:
        in_market_days = set()
        for t in trades:
            entry = pd.Timestamp(t.get("entry_date", equity_curve.index[0]))
            exit_ = pd.Timestamp(t.get("exit_date", equity_curve.index[-1]))
            rng = pd.date_range(entry, exit_, freq="D")
            in_market_days.update(rng)
        exposure = len(in_market_days) / n_days * 100
    else:
        exposure = 0

    # Monthly returns
    monthly = returns.resample("ME").apply(lambda x: (1 + x).prod() - 1)
    monthly_dict = {dt.strftime("%Y-%m"): round(v * 100, 2) for dt, v in monthly.items()}

    return {
        "total_return": round(total_return * 100, 4),
        "annualized_return": round(annualized_return * 100, 4),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "max_drawdown": round(max_dd * 100, 4),
        "max_drawdown_duration_days": max_dd_duration,
        "calmar_ratio": round(calmar, 4),
        "win_rate": round(win_rate * 100, 2),
        "profit_factor": round(profit_factor, 4),
        "total_trades": total_trades,
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "largest_win": round(largest_win, 2),
        "largest_loss": round(largest_loss, 2),
        "exposure_pct": round(exposure, 2),
        "monthly_returns": monthly_dict,
        "equity_curve": [
            {"date": dt.strftime("%Y-%m-%d"), "value": round(v, 2)}
            for dt, v in equity_curve.items()
        ],
        "drawdown_curve": [
            {"date": dt.strftime("%Y-%m-%d"), "value": round(v * 100, 4)}
            for dt, v in drawdown.items()
        ],
    }


def _empty_metrics():
    return {
        "total_return": 0, "annualized_return": 0, "sharpe_ratio": 0,
        "sortino_ratio": 0, "max_drawdown": 0, "max_drawdown_duration_days": 0,
        "calmar_ratio": 0, "win_rate": 0, "profit_factor": 0,
        "total_trades": 0, "avg_win": 0, "avg_loss": 0,
        "largest_win": 0, "largest_loss": 0, "exposure_pct": 0,
        "monthly_returns": {}, "equity_curve": [], "drawdown_curve": [],
    }
