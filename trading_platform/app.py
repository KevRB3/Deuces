import json
import datetime
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .database.engine import get_db, init_db
from .database import crud
from .backtesting.engine import run_backtest
from .backtesting.strategies import list_strategies
from .data_sources.manager import load_csv, load_manual_data, get_data_summary

BASE_DIR = Path(__file__).parent

app = FastAPI(title="Deuces Trading Platform", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.on_event("startup")
def startup():
    init_db()
    # Ensure a default portfolio exists
    db = next(get_db())
    try:
        portfolios = crud.get_portfolios(db)
        if not portfolios:
            crud.create_portfolio(db, "Default", 100000.0)
    finally:
        db.close()


# ── UI ──────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── Market Data ─────────────────────────────────────────────────────
@app.get("/api/symbols")
def api_symbols(db: Session = Depends(get_db)):
    return crud.get_available_symbols(db)


@app.get("/api/market-data/{symbol}")
def api_market_data(
    symbol: str,
    start: str = Query(None),
    end: str = Query(None),
    db: Session = Depends(get_db),
):
    start_dt = datetime.datetime.fromisoformat(start) if start else None
    end_dt = datetime.datetime.fromisoformat(end) if end else None
    data = crud.get_market_data(db, symbol.upper(), start_dt, end_dt)
    return [
        {
            "date": d.date.strftime("%Y-%m-%d %H:%M:%S") if isinstance(d.date, datetime.datetime) else str(d.date),
            "open": d.open, "high": d.high, "low": d.low,
            "close": d.close, "volume": d.volume, "adj_close": d.adj_close,
        }
        for d in data
    ]


@app.post("/api/market-data/upload")
async def api_upload_csv(
    file: UploadFile = File(...),
    symbol: str = Form(None),
    source_name: str = Form(None),
    db: Session = Depends(get_db),
):
    content = await file.read()
    result = load_csv(db, content, file.filename, symbol, source_name)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/market-data/manual")
def api_manual_data(payload: dict, db: Session = Depends(get_db)):
    symbol = payload.get("symbol")
    rows = payload.get("rows", [])
    if not symbol or not rows:
        raise HTTPException(status_code=400, detail="symbol and rows required")
    result = load_manual_data(db, symbol, rows)
    return result


@app.delete("/api/market-data/{symbol}")
def api_delete_market_data(symbol: str, db: Session = Depends(get_db)):
    count = crud.delete_market_data(db, symbol.upper())
    return {"deleted": count}


@app.get("/api/data-summary")
def api_data_summary(db: Session = Depends(get_db)):
    return get_data_summary(db)


# ── Portfolio ───────────────────────────────────────────────────────
@app.get("/api/portfolios")
def api_portfolios(db: Session = Depends(get_db)):
    portfolios = crud.get_portfolios(db)
    return [
        {"id": p.id, "name": p.name, "initial_capital": p.initial_capital,
         "current_cash": p.current_cash, "created_at": str(p.created_at)}
        for p in portfolios
    ]


@app.post("/api/portfolios")
def api_create_portfolio(payload: dict, db: Session = Depends(get_db)):
    name = payload.get("name", "New Portfolio")
    capital = payload.get("initial_capital", 100000)
    p = crud.create_portfolio(db, name, capital)
    return {"id": p.id, "name": p.name, "initial_capital": p.initial_capital}


@app.get("/api/portfolios/{portfolio_id}")
def api_portfolio_detail(portfolio_id: int, db: Session = Depends(get_db)):
    result = crud.get_portfolio_value(db, portfolio_id)
    if not result:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return result


# ── Trades ──────────────────────────────────────────────────────────
@app.post("/api/trades")
def api_execute_trade(payload: dict, db: Session = Depends(get_db)):
    try:
        trade = crud.execute_trade(
            db,
            portfolio_id=payload.get("portfolio_id", 1),
            symbol=payload["symbol"].upper(),
            side=payload["side"],
            quantity=float(payload["quantity"]),
            price=float(payload["price"]),
            commission=float(payload.get("commission", 0)),
            slippage=float(payload.get("slippage", 0)),
            notes=payload.get("notes"),
        )
        return {
            "id": trade.id, "symbol": trade.symbol, "side": trade.side,
            "quantity": trade.quantity, "price": trade.price,
            "total_cost": trade.total_cost, "executed_at": str(trade.executed_at),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/trades/{portfolio_id}")
def api_trades(portfolio_id: int, symbol: str = None, db: Session = Depends(get_db)):
    trades = crud.get_trades(db, portfolio_id, symbol)
    return [
        {
            "id": t.id, "symbol": t.symbol, "side": t.side,
            "quantity": t.quantity, "price": t.price,
            "commission": t.commission, "total_cost": t.total_cost,
            "notes": t.notes, "executed_at": str(t.executed_at), "source": t.source,
        }
        for t in trades
    ]


# ── Strategies ──────────────────────────────────────────────────────
@app.get("/api/strategies/available")
def api_available_strategies():
    return list_strategies()


@app.get("/api/strategies")
def api_saved_strategies(db: Session = Depends(get_db)):
    strategies = crud.get_strategies(db)
    return [
        {
            "id": s.id, "name": s.name, "strategy_type": s.strategy_type,
            "parameters": json.loads(s.parameters), "description": s.description,
            "created_at": str(s.created_at),
        }
        for s in strategies
    ]


@app.post("/api/strategies")
def api_save_strategy(payload: dict, db: Session = Depends(get_db)):
    s = crud.save_strategy(
        db,
        name=payload["name"],
        strategy_type=payload["strategy_type"],
        parameters=payload.get("parameters", {}),
        description=payload.get("description"),
    )
    return {"id": s.id, "name": s.name}


@app.delete("/api/strategies/{strategy_id}")
def api_delete_strategy(strategy_id: int, db: Session = Depends(get_db)):
    if crud.delete_strategy(db, strategy_id):
        return {"deleted": True}
    raise HTTPException(status_code=404, detail="Strategy not found")


# ── Backtesting ─────────────────────────────────────────────────────
@app.post("/api/backtest")
def api_run_backtest(payload: dict, db: Session = Depends(get_db)):
    required = ["strategy_type", "symbols", "start_date", "end_date"]
    missing = [f for f in required if f not in payload]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing fields: {missing}")
    result = run_backtest(db, payload)
    return result


@app.get("/api/backtest/runs")
def api_backtest_runs(db: Session = Depends(get_db)):
    runs = crud.get_backtest_runs(db)
    return [
        {
            "id": r.id, "strategy_type": r.strategy_type, "symbols": json.loads(r.symbols),
            "start_date": str(r.start_date), "end_date": str(r.end_date),
            "initial_capital": r.initial_capital, "status": r.status,
            "total_return": r.total_return, "sharpe_ratio": r.sharpe_ratio,
            "max_drawdown": r.max_drawdown, "total_trades": r.total_trades,
            "win_rate": r.win_rate, "created_at": str(r.created_at),
        }
        for r in runs
    ]


@app.get("/api/backtest/runs/{run_id}")
def api_backtest_detail(run_id: int, db: Session = Depends(get_db)):
    r = crud.get_backtest_run(db, run_id)
    if not r:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": r.id, "strategy_type": r.strategy_type,
        "strategy_params": json.loads(r.strategy_params) if r.strategy_params else {},
        "symbols": json.loads(r.symbols) if r.symbols else [],
        "start_date": str(r.start_date), "end_date": str(r.end_date),
        "timeframe": r.timeframe, "initial_capital": r.initial_capital,
        "commission_pct": r.commission_pct, "slippage_pct": r.slippage_pct,
        "position_sizing": r.position_sizing, "position_size_value": r.position_size_value,
        "stop_loss_pct": r.stop_loss_pct, "take_profit_pct": r.take_profit_pct,
        "allow_short": r.allow_short, "benchmark": r.benchmark,
        "status": r.status, "error_message": r.error_message,
        "total_return": r.total_return, "annualized_return": r.annualized_return,
        "sharpe_ratio": r.sharpe_ratio, "sortino_ratio": r.sortino_ratio,
        "max_drawdown": r.max_drawdown, "max_drawdown_duration_days": r.max_drawdown_duration_days,
        "win_rate": r.win_rate, "profit_factor": r.profit_factor,
        "total_trades": r.total_trades, "avg_win": r.avg_win, "avg_loss": r.avg_loss,
        "largest_win": r.largest_win, "largest_loss": r.largest_loss,
        "exposure_pct": r.exposure_pct, "calmar_ratio": r.calmar_ratio,
        "equity_curve": json.loads(r.equity_curve) if r.equity_curve else [],
        "drawdown_curve": json.loads(r.drawdown_curve) if r.drawdown_curve else [],
        "monthly_returns": json.loads(r.monthly_returns) if r.monthly_returns else {},
        "trade_log": json.loads(r.trade_log) if r.trade_log else [],
        "created_at": str(r.created_at), "completed_at": str(r.completed_at) if r.completed_at else None,
    }


@app.delete("/api/backtest/runs/{run_id}")
def api_delete_backtest(run_id: int, db: Session = Depends(get_db)):
    if crud.delete_backtest_run(db, run_id):
        return {"deleted": True}
    raise HTTPException(status_code=404, detail="Run not found")


# ── Watchlist ───────────────────────────────────────────────────────
@app.get("/api/watchlist")
def api_watchlist(db: Session = Depends(get_db)):
    items = crud.get_watchlist(db)
    return [{"symbol": w.symbol, "notes": w.notes, "added_at": str(w.added_at)} for w in items]


@app.post("/api/watchlist")
def api_add_watchlist(payload: dict, db: Session = Depends(get_db)):
    w = crud.add_to_watchlist(db, payload["symbol"].upper(), payload.get("notes"))
    return {"symbol": w.symbol}


@app.delete("/api/watchlist/{symbol}")
def api_remove_watchlist(symbol: str, db: Session = Depends(get_db)):
    if crud.remove_from_watchlist(db, symbol.upper()):
        return {"deleted": True}
    raise HTTPException(status_code=404, detail="Not found")


# ── Data Sources ────────────────────────────────────────────────────
@app.get("/api/data-sources")
def api_data_sources(db: Session = Depends(get_db)):
    sources = crud.get_data_sources(db)
    return [
        {
            "id": s.id, "name": s.name, "source_type": s.source_type,
            "config": json.loads(s.config) if s.config else {},
            "status": s.status,
            "symbols_loaded": json.loads(s.symbols_loaded) if s.symbols_loaded else [],
            "last_sync": str(s.last_sync) if s.last_sync else None,
        }
        for s in sources
    ]
