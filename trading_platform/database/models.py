import datetime
from sqlalchemy import (
    Column, Integer, Float, String, Text, DateTime, Date, Boolean,
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from .engine import Base


class MarketData(Base):
    __tablename__ = "market_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    adj_close = Column(Float)
    source = Column(String(50), default="csv")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("symbol", "date", "source", name="uq_symbol_date_source"),
        Index("ix_market_data_symbol_date", "symbol", "date"),
    )


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    initial_capital = Column(Float, nullable=False, default=100000.0)
    current_cash = Column(Float, nullable=False, default=100000.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    holdings = relationship("Holding", back_populates="portfolio", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="portfolio", cascade="all, delete-orphan")


class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    quantity = Column(Float, nullable=False, default=0)
    avg_cost = Column(Float, nullable=False, default=0)
    current_price = Column(Float, default=0)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    portfolio = relationship("Portfolio", back_populates="holdings")

    __table_args__ = (
        UniqueConstraint("portfolio_id", "symbol", name="uq_portfolio_symbol"),
    )


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(4), nullable=False)  # BUY or SELL
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    commission = Column(Float, default=0)
    slippage = Column(Float, default=0)
    total_cost = Column(Float, nullable=False)
    notes = Column(Text)
    executed_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    source = Column(String(20), default="manual")  # manual, backtest

    portfolio = relationship("Portfolio", back_populates="trades")


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    strategy_type = Column(String(50), nullable=False)
    parameters = Column(Text, nullable=False)  # JSON
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    backtest_runs = relationship("BacktestRun", back_populates="strategy", cascade="all, delete-orphan")


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    strategy_type = Column(String(50), nullable=False)
    strategy_params = Column(Text, nullable=False)  # JSON
    symbols = Column(Text, nullable=False)  # JSON array
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    timeframe = Column(String(10), default="1d")
    initial_capital = Column(Float, nullable=False)
    commission_pct = Column(Float, default=0)
    slippage_pct = Column(Float, default=0)
    position_sizing = Column(String(30), default="percent")
    position_size_value = Column(Float, default=10.0)
    stop_loss_pct = Column(Float, nullable=True)
    take_profit_pct = Column(Float, nullable=True)
    allow_short = Column(Boolean, default=False)
    benchmark = Column(String(20), nullable=True)

    # Results
    total_return = Column(Float)
    annualized_return = Column(Float)
    sharpe_ratio = Column(Float)
    sortino_ratio = Column(Float)
    max_drawdown = Column(Float)
    max_drawdown_duration_days = Column(Integer)
    win_rate = Column(Float)
    profit_factor = Column(Float)
    total_trades = Column(Integer)
    avg_win = Column(Float)
    avg_loss = Column(Float)
    largest_win = Column(Float)
    largest_loss = Column(Float)
    exposure_pct = Column(Float)
    calmar_ratio = Column(Float)
    equity_curve = Column(Text)  # JSON array
    drawdown_curve = Column(Text)  # JSON array
    monthly_returns = Column(Text)  # JSON
    trade_log = Column(Text)  # JSON array

    status = Column(String(20), default="pending")  # pending, running, completed, failed
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime)

    strategy = relationship("Strategy", back_populates="backtest_runs")


class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, unique=True)
    notes = Column(Text)
    added_at = Column(DateTime, default=datetime.datetime.utcnow)


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    source_type = Column(String(30), nullable=False)  # csv, api, manual
    config = Column(Text)  # JSON
    status = Column(String(20), default="active")
    symbols_loaded = Column(Text)  # JSON array
    last_sync = Column(DateTime)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
