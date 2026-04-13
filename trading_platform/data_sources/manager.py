import io
import json
import datetime
import pandas as pd
from sqlalchemy.orm import Session

from ..database import crud


# Expected column name mappings (flexible CSV ingestion)
COLUMN_ALIASES = {
    "date": ["date", "datetime", "timestamp", "time", "dt", "trade_date", "Date", "DATE"],
    "open": ["open", "Open", "OPEN", "open_price", "o"],
    "high": ["high", "High", "HIGH", "high_price", "h"],
    "low": ["low", "Low", "LOW", "low_price", "l"],
    "close": ["close", "Close", "CLOSE", "close_price", "c", "adj_close", "Adj Close", "adj close"],
    "volume": ["volume", "Volume", "VOLUME", "vol", "v", "Vol"],
    "adj_close": ["adj_close", "Adj Close", "adj close", "adjusted_close", "Adj_Close"],
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map various column names to our standard names."""
    col_map = {}
    df_cols_lower = {c.strip().lower(): c for c in df.columns}

    for standard, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias.lower() in df_cols_lower:
                col_map[df_cols_lower[alias.lower()]] = standard
                break

    df = df.rename(columns=col_map)
    return df


def load_csv(db: Session, file_content: bytes, filename: str,
             symbol: str = None, source_name: str = None) -> dict:
    """Parse and load CSV market data into the database."""
    try:
        text = file_content.decode("utf-8")
    except UnicodeDecodeError:
        text = file_content.decode("latin-1")

    df = pd.read_csv(io.StringIO(text))
    df = _normalize_columns(df)

    # Detect symbol from filename if not provided
    if not symbol:
        symbol = filename.replace(".csv", "").replace(".CSV", "").split("_")[0].upper()

    if "date" not in df.columns:
        return {"error": "No date column found. Expected one of: date, datetime, timestamp, time"}

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    required = ["close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return {"error": f"Missing required columns: {missing}. Found: {list(df.columns)}"}

    # Build records
    records = []
    for _, row in df.iterrows():
        record = {
            "symbol": symbol,
            "date": row["date"],
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": row["close"],
            "volume": row.get("volume"),
            "adj_close": row.get("adj_close"),
            "source": source_name or "csv",
        }
        # Clean NaN values
        for k, v in record.items():
            if isinstance(v, float) and pd.isna(v):
                record[k] = None
        records.append(record)

    count = crud.upsert_market_data(db, records)

    # Register data source
    ds = crud.register_data_source(
        db, name=source_name or f"csv_{filename}",
        source_type="csv",
        config={"filename": filename, "symbol": symbol, "rows": len(records)},
    )
    crud.update_data_source_sync(db, ds.id, [symbol])

    return {
        "symbol": symbol,
        "rows_loaded": count,
        "total_rows": len(records),
        "date_range": {
            "start": df["date"].min().strftime("%Y-%m-%d"),
            "end": df["date"].max().strftime("%Y-%m-%d"),
        },
        "columns_found": [c for c in ["open", "high", "low", "close", "volume", "adj_close"] if c in df.columns],
    }


def load_manual_data(db: Session, symbol: str, rows: list[dict]) -> dict:
    """Load manually entered OHLCV data."""
    records = []
    for row in rows:
        record = {
            "symbol": symbol.upper(),
            "date": datetime.datetime.fromisoformat(row["date"]),
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": row["close"],
            "volume": row.get("volume"),
            "source": "manual",
        }
        records.append(record)

    count = crud.upsert_market_data(db, records)
    return {"symbol": symbol.upper(), "rows_loaded": count}


def get_data_summary(db: Session) -> list[dict]:
    """Get summary of all loaded data."""
    symbols = crud.get_available_symbols(db)
    result = []
    for s in symbols:
        data = crud.get_market_data(db, s["symbol"])
        if data:
            result.append({
                "symbol": s["symbol"],
                "bars": s["count"],
                "start_date": data[0].date.strftime("%Y-%m-%d") if data else None,
                "end_date": data[-1].date.strftime("%Y-%m-%d") if data else None,
                "source": data[0].source if data else None,
            })
    return result
