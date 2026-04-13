import json
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from . import models


# --- Market Data ---
def upsert_market_data(db: Session, records: list[dict]) -> int:
    count = 0
    for r in records:
        existing = db.query(models.MarketData).filter(
            and_(
                models.MarketData.symbol == r["symbol"],
                models.MarketData.date == r["date"],
                models.MarketData.source == r.get("source", "csv"),
            )
        ).first()
        if existing:
            for k, v in r.items():
                setattr(existing, k, v)
        else:
            db.add(models.MarketData(**r))
            count += 1
    db.commit()
    return count


def get_market_data(db: Session, symbol: str, start_date=None, end_date=None):
    q = db.query(models.MarketData).filter(models.MarketData.symbol == symbol)
    if start_date:
        q = q.filter(models.MarketData.date >= start_date)
    if end_date:
        q = q.filter(models.MarketData.date <= end_date)
    return q.order_by(models.MarketData.date.asc()).all()


def get_available_symbols(db: Session):
    rows = db.query(models.MarketData.symbol, func.count(models.MarketData.id)).group_by(
        models.MarketData.symbol
    ).all()
    return [{"symbol": r[0], "count": r[1]} for r in rows]


def delete_market_data(db: Session, symbol: str, source: str = None):
    q = db.query(models.MarketData).filter(models.MarketData.symbol == symbol)
    if source:
        q = q.filter(models.MarketData.source == source)
    count = q.delete()
    db.commit()
    return count


# --- Portfolio ---
def create_portfolio(db: Session, name: str, initial_capital: float):
    p = models.Portfolio(name=name, initial_capital=initial_capital, current_cash=initial_capital)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def get_portfolio(db: Session, portfolio_id: int):
    return db.query(models.Portfolio).filter(models.Portfolio.id == portfolio_id).first()


def get_portfolios(db: Session):
    return db.query(models.Portfolio).all()


def get_portfolio_value(db: Session, portfolio_id: int):
    p = get_portfolio(db, portfolio_id)
    if not p:
        return None
    holdings_value = sum(h.quantity * (h.current_price or h.avg_cost) for h in p.holdings)
    return {
        "portfolio_id": p.id,
        "name": p.name,
        "cash": p.current_cash,
        "holdings_value": holdings_value,
        "total_value": p.current_cash + holdings_value,
        "initial_capital": p.initial_capital,
        "total_return_pct": ((p.current_cash + holdings_value) / p.initial_capital - 1) * 100,
        "holdings": [
            {
                "symbol": h.symbol,
                "quantity": h.quantity,
                "avg_cost": h.avg_cost,
                "current_price": h.current_price or h.avg_cost,
                "market_value": h.quantity * (h.current_price or h.avg_cost),
                "pnl": h.quantity * ((h.current_price or h.avg_cost) - h.avg_cost),
                "pnl_pct": (((h.current_price or h.avg_cost) / h.avg_cost) - 1) * 100 if h.avg_cost else 0,
            }
            for h in p.holdings if h.quantity != 0
        ],
    }


# --- Trades ---
def execute_trade(db: Session, portfolio_id: int, symbol: str, side: str,
                  quantity: float, price: float, commission: float = 0,
                  slippage: float = 0, notes: str = None, source: str = "manual"):
    p = get_portfolio(db, portfolio_id)
    if not p:
        raise ValueError("Portfolio not found")

    side = side.upper()
    slip_cost = price * slippage / 100 if slippage else 0
    exec_price = price + slip_cost if side == "BUY" else price - slip_cost
    comm = abs(exec_price * quantity * commission / 100) if commission else 0
    total_cost = exec_price * quantity + comm if side == "BUY" else -(exec_price * quantity - comm)

    if side == "BUY" and total_cost > p.current_cash:
        raise ValueError(f"Insufficient cash: need {total_cost:.2f}, have {p.current_cash:.2f}")

    trade = models.Trade(
        portfolio_id=portfolio_id, symbol=symbol, side=side,
        quantity=quantity, price=exec_price, commission=comm,
        slippage=slip_cost * quantity, total_cost=total_cost,
        notes=notes, source=source,
    )
    db.add(trade)

    # Update holdings
    holding = db.query(models.Holding).filter(
        and_(models.Holding.portfolio_id == portfolio_id, models.Holding.symbol == symbol)
    ).first()

    if side == "BUY":
        p.current_cash -= total_cost
        if holding:
            new_qty = holding.quantity + quantity
            holding.avg_cost = ((holding.avg_cost * holding.quantity) + (exec_price * quantity)) / new_qty
            holding.quantity = new_qty
        else:
            holding = models.Holding(
                portfolio_id=portfolio_id, symbol=symbol,
                quantity=quantity, avg_cost=exec_price, current_price=exec_price,
            )
            db.add(holding)
    else:  # SELL
        if not holding or holding.quantity < quantity:
            raise ValueError(f"Insufficient shares: have {holding.quantity if holding else 0}, selling {quantity}")
        p.current_cash += abs(total_cost)
        holding.quantity -= quantity
        if holding.quantity == 0:
            db.delete(holding)

    db.commit()
    db.refresh(trade)
    return trade


def get_trades(db: Session, portfolio_id: int, symbol: str = None, limit: int = 100):
    q = db.query(models.Trade).filter(models.Trade.portfolio_id == portfolio_id)
    if symbol:
        q = q.filter(models.Trade.symbol == symbol)
    return q.order_by(models.Trade.executed_at.desc()).limit(limit).all()


# --- Strategy ---
def save_strategy(db: Session, name: str, strategy_type: str, parameters: dict, description: str = None):
    existing = db.query(models.Strategy).filter(models.Strategy.name == name).first()
    if existing:
        existing.strategy_type = strategy_type
        existing.parameters = json.dumps(parameters)
        existing.description = description
        existing.updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    s = models.Strategy(
        name=name, strategy_type=strategy_type,
        parameters=json.dumps(parameters), description=description,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def get_strategies(db: Session):
    return db.query(models.Strategy).all()


def get_strategy(db: Session, strategy_id: int):
    return db.query(models.Strategy).filter(models.Strategy.id == strategy_id).first()


def delete_strategy(db: Session, strategy_id: int):
    s = get_strategy(db, strategy_id)
    if s:
        db.delete(s)
        db.commit()
        return True
    return False


# --- Backtest Runs ---
def create_backtest_run(db: Session, **kwargs):
    run = models.BacktestRun(**kwargs)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def update_backtest_run(db: Session, run_id: int, **kwargs):
    run = db.query(models.BacktestRun).filter(models.BacktestRun.id == run_id).first()
    if not run:
        return None
    for k, v in kwargs.items():
        setattr(run, k, v)
    db.commit()
    db.refresh(run)
    return run


def get_backtest_runs(db: Session, limit: int = 50):
    return db.query(models.BacktestRun).order_by(models.BacktestRun.created_at.desc()).limit(limit).all()


def get_backtest_run(db: Session, run_id: int):
    return db.query(models.BacktestRun).filter(models.BacktestRun.id == run_id).first()


def delete_backtest_run(db: Session, run_id: int):
    run = get_backtest_run(db, run_id)
    if run:
        db.delete(run)
        db.commit()
        return True
    return False


# --- Watchlist ---
def add_to_watchlist(db: Session, symbol: str, notes: str = None):
    existing = db.query(models.Watchlist).filter(models.Watchlist.symbol == symbol).first()
    if existing:
        existing.notes = notes
        db.commit()
        return existing
    w = models.Watchlist(symbol=symbol, notes=notes)
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


def get_watchlist(db: Session):
    return db.query(models.Watchlist).order_by(models.Watchlist.added_at.desc()).all()


def remove_from_watchlist(db: Session, symbol: str):
    w = db.query(models.Watchlist).filter(models.Watchlist.symbol == symbol).first()
    if w:
        db.delete(w)
        db.commit()
        return True
    return False


# --- Data Sources ---
def register_data_source(db: Session, name: str, source_type: str, config: dict = None):
    existing = db.query(models.DataSource).filter(models.DataSource.name == name).first()
    if existing:
        existing.config = json.dumps(config or {})
        existing.source_type = source_type
        db.commit()
        db.refresh(existing)
        return existing
    ds = models.DataSource(
        name=name, source_type=source_type, config=json.dumps(config or {}),
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


def get_data_sources(db: Session):
    return db.query(models.DataSource).all()


def update_data_source_sync(db: Session, source_id: int, symbols: list):
    ds = db.query(models.DataSource).filter(models.DataSource.id == source_id).first()
    if ds:
        ds.symbols_loaded = json.dumps(symbols)
        ds.last_sync = datetime.datetime.utcnow()
        db.commit()
    return ds
