import json
import datetime
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from .strategies import get_strategy
from .metrics import compute_metrics
from ..database import crud, models


def run_backtest(db: Session, config: dict) -> dict:
    """Execute a full backtest and persist results."""
    # Create the run record
    run = crud.create_backtest_run(
        db,
        strategy_type=config["strategy_type"],
        strategy_params=json.dumps(config.get("strategy_params", {})),
        symbols=json.dumps(config.get("symbols", [])),
        start_date=datetime.date.fromisoformat(config["start_date"]),
        end_date=datetime.date.fromisoformat(config["end_date"]),
        timeframe=config.get("timeframe", "1d"),
        initial_capital=config.get("initial_capital", 100000),
        commission_pct=config.get("commission_pct", 0),
        slippage_pct=config.get("slippage_pct", 0),
        position_sizing=config.get("position_sizing", "percent"),
        position_size_value=config.get("position_size_value", 10),
        stop_loss_pct=config.get("stop_loss_pct"),
        take_profit_pct=config.get("take_profit_pct"),
        allow_short=config.get("allow_short", False),
        benchmark=config.get("benchmark"),
        strategy_id=config.get("strategy_id"),
        status="running",
    )

    try:
        symbols = config.get("symbols", [])
        if not symbols:
            raise ValueError("No symbols provided")

        # Load market data for primary symbol
        symbol = symbols[0]
        market_data = crud.get_market_data(
            db, symbol,
            start_date=datetime.datetime.fromisoformat(config["start_date"]),
            end_date=datetime.datetime.fromisoformat(config["end_date"]),
        )

        if not market_data:
            raise ValueError(f"No market data found for {symbol} in date range")

        # Build DataFrame
        df = pd.DataFrame([{
            "date": m.date,
            "open": m.open,
            "high": m.high,
            "low": m.low,
            "close": m.close,
            "volume": m.volume,
        } for m in market_data])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

        if len(df) < 5:
            raise ValueError(f"Insufficient data: only {len(df)} bars for {symbol}")

        # Generate signals
        strategy = get_strategy(config["strategy_type"], config.get("strategy_params", {}))
        df = strategy.generate_signals(df)

        # Execute simulation
        result = _simulate(df, config)

        # Compute metrics
        metrics = compute_metrics(
            result["equity_curve"],
            result["trades"],
            config.get("initial_capital", 100000),
        )

        # Update run record
        crud.update_backtest_run(
            db, run.id,
            status="completed",
            completed_at=datetime.datetime.utcnow(),
            total_return=metrics["total_return"],
            annualized_return=metrics["annualized_return"],
            sharpe_ratio=metrics["sharpe_ratio"],
            sortino_ratio=metrics["sortino_ratio"],
            max_drawdown=metrics["max_drawdown"],
            max_drawdown_duration_days=metrics["max_drawdown_duration_days"],
            win_rate=metrics["win_rate"],
            profit_factor=metrics["profit_factor"],
            total_trades=metrics["total_trades"],
            avg_win=metrics["avg_win"],
            avg_loss=metrics["avg_loss"],
            largest_win=metrics["largest_win"],
            largest_loss=metrics["largest_loss"],
            exposure_pct=metrics["exposure_pct"],
            calmar_ratio=metrics["calmar_ratio"],
            equity_curve=json.dumps(metrics["equity_curve"]),
            drawdown_curve=json.dumps(metrics["drawdown_curve"]),
            monthly_returns=json.dumps(metrics["monthly_returns"]),
            trade_log=json.dumps(result["trades"]),
        )

        return {
            "run_id": run.id,
            "status": "completed",
            "metrics": metrics,
            "trades": result["trades"],
        }

    except Exception as e:
        crud.update_backtest_run(
            db, run.id,
            status="failed",
            error_message=str(e),
            completed_at=datetime.datetime.utcnow(),
        )
        return {"run_id": run.id, "status": "failed", "error": str(e)}


def _simulate(df: pd.DataFrame, config: dict) -> dict:
    """Core simulation loop."""
    initial_capital = config.get("initial_capital", 100000)
    commission_pct = config.get("commission_pct", 0) / 100
    slippage_pct = config.get("slippage_pct", 0) / 100
    position_sizing = config.get("position_sizing", "percent")
    position_size_value = config.get("position_size_value", 10)
    stop_loss_pct = config.get("stop_loss_pct")
    take_profit_pct = config.get("take_profit_pct")
    allow_short = config.get("allow_short", False)

    if stop_loss_pct is not None:
        stop_loss_pct = stop_loss_pct / 100
    if take_profit_pct is not None:
        take_profit_pct = take_profit_pct / 100

    cash = initial_capital
    position = 0  # shares held (negative = short)
    entry_price = 0
    trades = []
    equity_values = []
    entry_date = None

    for idx, row in df.iterrows():
        price = row["close"]
        signal = row.get("signal", 0)

        # Check stop loss / take profit on existing position
        if position != 0 and entry_price > 0:
            if position > 0:
                pnl_pct = (price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - price) / entry_price

            forced_exit = False
            if stop_loss_pct is not None and pnl_pct <= -stop_loss_pct:
                forced_exit = True
            if take_profit_pct is not None and pnl_pct >= take_profit_pct:
                forced_exit = True

            if forced_exit:
                exec_price = price * (1 - slippage_pct) if position > 0 else price * (1 + slippage_pct)
                comm = abs(exec_price * abs(position) * commission_pct)
                proceeds = exec_price * abs(position) - comm if position > 0 else -exec_price * abs(position) - comm
                pnl = proceeds - (entry_price * abs(position)) if position > 0 else (entry_price * abs(position)) - (-proceeds)

                if position > 0:
                    pnl = (exec_price - entry_price) * position - comm
                    cash += exec_price * position - comm
                else:
                    pnl = (entry_price - exec_price) * abs(position) - comm
                    cash += (entry_price - exec_price) * abs(position) - comm

                trades.append({
                    "entry_date": entry_date.strftime("%Y-%m-%d") if entry_date else "",
                    "exit_date": idx.strftime("%Y-%m-%d"),
                    "side": "LONG" if position > 0 else "SHORT",
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exec_price, 2),
                    "quantity": abs(position),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl / (entry_price * abs(position)) * 100, 2) if entry_price else 0,
                    "exit_reason": "stop_loss" if pnl < 0 else "take_profit",
                })
                position = 0
                entry_price = 0
                entry_date = None

        # Process signals
        if signal == 1 and position <= 0:
            # Close short if exists
            if position < 0:
                exec_price = price * (1 + slippage_pct)
                comm = abs(exec_price * abs(position) * commission_pct)
                pnl = (entry_price - exec_price) * abs(position) - comm
                cash += pnl
                trades.append({
                    "entry_date": entry_date.strftime("%Y-%m-%d") if entry_date else "",
                    "exit_date": idx.strftime("%Y-%m-%d"),
                    "side": "SHORT",
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exec_price, 2),
                    "quantity": abs(position),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl / (entry_price * abs(position)) * 100, 2) if entry_price else 0,
                    "exit_reason": "signal",
                })
                position = 0

            # Open long
            exec_price = price * (1 + slippage_pct)
            shares = _calc_position_size(cash, exec_price, position_sizing, position_size_value)
            if shares > 0:
                comm = exec_price * shares * commission_pct
                cash -= exec_price * shares + comm
                position = shares
                entry_price = exec_price
                entry_date = idx

        elif signal == -1 and position >= 0:
            # Close long if exists
            if position > 0:
                exec_price = price * (1 - slippage_pct)
                comm = abs(exec_price * position * commission_pct)
                pnl = (exec_price - entry_price) * position - comm
                cash += exec_price * position - comm
                trades.append({
                    "entry_date": entry_date.strftime("%Y-%m-%d") if entry_date else "",
                    "exit_date": idx.strftime("%Y-%m-%d"),
                    "side": "LONG",
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exec_price, 2),
                    "quantity": position,
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl / (entry_price * position) * 100, 2) if entry_price else 0,
                    "exit_reason": "signal",
                })
                position = 0
                entry_price = 0
                entry_date = None

            # Open short if allowed
            if allow_short:
                exec_price = price * (1 - slippage_pct)
                shares = _calc_position_size(cash, exec_price, position_sizing, position_size_value)
                if shares > 0:
                    comm = exec_price * shares * commission_pct
                    cash -= comm  # commission only; short proceeds come at close
                    position = -shares
                    entry_price = exec_price
                    entry_date = idx

        # Record equity
        mark_to_market = 0
        if position > 0:
            mark_to_market = position * price
        elif position < 0:
            mark_to_market = (entry_price - price) * abs(position)

        equity_values.append(cash + mark_to_market)

    # Close any remaining position at end
    if position != 0:
        price = df.iloc[-1]["close"]
        if position > 0:
            exec_price = price * (1 - slippage_pct)
            comm = abs(exec_price * position * commission_pct)
            pnl = (exec_price - entry_price) * position - comm
            cash += exec_price * position - comm
        else:
            exec_price = price * (1 + slippage_pct)
            comm = abs(exec_price * abs(position) * commission_pct)
            pnl = (entry_price - exec_price) * abs(position) - comm
            cash += pnl

        trades.append({
            "entry_date": entry_date.strftime("%Y-%m-%d") if entry_date else "",
            "exit_date": df.index[-1].strftime("%Y-%m-%d"),
            "side": "LONG" if position > 0 else "SHORT",
            "entry_price": round(entry_price, 2),
            "exit_price": round(exec_price, 2),
            "quantity": abs(position),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl / (entry_price * abs(position)) * 100, 2) if entry_price else 0,
            "exit_reason": "end_of_data",
        })
        equity_values[-1] = cash

    equity_curve = pd.Series(equity_values, index=df.index)

    return {"equity_curve": equity_curve, "trades": trades}


def _calc_position_size(cash: float, price: float, method: str, value: float) -> int:
    if price <= 0:
        return 0
    if method == "fixed_dollar":
        return max(int(value / price), 0)
    elif method == "fixed_shares":
        return max(int(value), 0)
    elif method == "percent":
        return max(int((cash * value / 100) / price), 0)
    elif method == "kelly":
        # Simplified Kelly - use value as estimated edge percentage
        kelly_frac = min(value / 100, 0.25)  # cap at 25%
        return max(int((cash * kelly_frac) / price), 0)
    else:
        return max(int((cash * 0.1) / price), 0)  # default 10%
