import pandas as pd
import numpy as np


class BaseStrategy:
    """Base class for all trading strategies."""

    name = "base"

    def __init__(self, params: dict):
        self.params = params

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Return DataFrame with 'signal' column: 1=buy, -1=sell, 0=hold."""
        raise NotImplementedError

    @classmethod
    def default_params(cls) -> dict:
        return {}

    @classmethod
    def param_schema(cls) -> list[dict]:
        """Return list of parameter definitions for the UI."""
        return []


class SMAcrossover(BaseStrategy):
    name = "sma_crossover"

    @classmethod
    def default_params(cls):
        return {"fast_period": 10, "slow_period": 30}

    @classmethod
    def param_schema(cls):
        return [
            {"key": "fast_period", "label": "Fast Period", "type": "int", "min": 2, "max": 500, "default": 10},
            {"key": "slow_period", "label": "Slow Period", "type": "int", "min": 5, "max": 500, "default": 30},
        ]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        fast = int(self.params.get("fast_period", 10))
        slow = int(self.params.get("slow_period", 30))
        df["sma_fast"] = df["close"].rolling(window=fast).mean()
        df["sma_slow"] = df["close"].rolling(window=slow).mean()
        df["signal"] = 0
        df.loc[df["sma_fast"] > df["sma_slow"], "signal"] = 1
        df.loc[df["sma_fast"] <= df["sma_slow"], "signal"] = -1
        df["signal"] = df["signal"].diff().clip(-1, 1)
        return df


class EMAcrossover(BaseStrategy):
    name = "ema_crossover"

    @classmethod
    def default_params(cls):
        return {"fast_period": 12, "slow_period": 26}

    @classmethod
    def param_schema(cls):
        return [
            {"key": "fast_period", "label": "Fast Period", "type": "int", "min": 2, "max": 500, "default": 12},
            {"key": "slow_period", "label": "Slow Period", "type": "int", "min": 5, "max": 500, "default": 26},
        ]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        fast = int(self.params.get("fast_period", 12))
        slow = int(self.params.get("slow_period", 26))
        df["ema_fast"] = df["close"].ewm(span=fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=slow, adjust=False).mean()
        df["signal"] = 0
        df.loc[df["ema_fast"] > df["ema_slow"], "signal"] = 1
        df.loc[df["ema_fast"] <= df["ema_slow"], "signal"] = -1
        df["signal"] = df["signal"].diff().clip(-1, 1)
        return df


class RSIStrategy(BaseStrategy):
    name = "rsi"

    @classmethod
    def default_params(cls):
        return {"period": 14, "overbought": 70, "oversold": 30}

    @classmethod
    def param_schema(cls):
        return [
            {"key": "period", "label": "RSI Period", "type": "int", "min": 2, "max": 200, "default": 14},
            {"key": "overbought", "label": "Overbought Level", "type": "float", "min": 50, "max": 100, "default": 70},
            {"key": "oversold", "label": "Oversold Level", "type": "float", "min": 0, "max": 50, "default": 30},
        ]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        period = int(self.params.get("period", 14))
        ob = float(self.params.get("overbought", 70))
        os_ = float(self.params.get("oversold", 30))

        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["rsi"] = 100 - (100 / (1 + rs))

        df["signal"] = 0
        df.loc[df["rsi"] < os_, "signal"] = 1
        df.loc[df["rsi"] > ob, "signal"] = -1
        return df


class MACDStrategy(BaseStrategy):
    name = "macd"

    @classmethod
    def default_params(cls):
        return {"fast_period": 12, "slow_period": 26, "signal_period": 9}

    @classmethod
    def param_schema(cls):
        return [
            {"key": "fast_period", "label": "Fast Period", "type": "int", "min": 2, "max": 200, "default": 12},
            {"key": "slow_period", "label": "Slow Period", "type": "int", "min": 5, "max": 200, "default": 26},
            {"key": "signal_period", "label": "Signal Period", "type": "int", "min": 2, "max": 100, "default": 9},
        ]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        fast = int(self.params.get("fast_period", 12))
        slow = int(self.params.get("slow_period", 26))
        sig = int(self.params.get("signal_period", 9))

        df["ema_fast"] = df["close"].ewm(span=fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=slow, adjust=False).mean()
        df["macd"] = df["ema_fast"] - df["ema_slow"]
        df["macd_signal"] = df["macd"].ewm(span=sig, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        df["signal"] = 0
        df.loc[df["macd"] > df["macd_signal"], "signal"] = 1
        df.loc[df["macd"] <= df["macd_signal"], "signal"] = -1
        df["signal"] = df["signal"].diff().clip(-1, 1)
        return df


class BollingerBands(BaseStrategy):
    name = "bollinger_bands"

    @classmethod
    def default_params(cls):
        return {"period": 20, "std_dev": 2.0}

    @classmethod
    def param_schema(cls):
        return [
            {"key": "period", "label": "Period", "type": "int", "min": 5, "max": 200, "default": 20},
            {"key": "std_dev", "label": "Std Deviations", "type": "float", "min": 0.5, "max": 5.0, "default": 2.0},
        ]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        period = int(self.params.get("period", 20))
        std = float(self.params.get("std_dev", 2.0))

        df["bb_mid"] = df["close"].rolling(window=period).mean()
        rolling_std = df["close"].rolling(window=period).std()
        df["bb_upper"] = df["bb_mid"] + std * rolling_std
        df["bb_lower"] = df["bb_mid"] - std * rolling_std

        df["signal"] = 0
        df.loc[df["close"] < df["bb_lower"], "signal"] = 1   # Buy at lower band
        df.loc[df["close"] > df["bb_upper"], "signal"] = -1  # Sell at upper band
        return df


class MeanReversion(BaseStrategy):
    name = "mean_reversion"

    @classmethod
    def default_params(cls):
        return {"lookback": 20, "entry_z": 2.0, "exit_z": 0.0}

    @classmethod
    def param_schema(cls):
        return [
            {"key": "lookback", "label": "Lookback Period", "type": "int", "min": 5, "max": 500, "default": 20},
            {"key": "entry_z", "label": "Entry Z-Score", "type": "float", "min": 0.5, "max": 5.0, "default": 2.0},
            {"key": "exit_z", "label": "Exit Z-Score", "type": "float", "min": 0.0, "max": 3.0, "default": 0.0},
        ]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        lookback = int(self.params.get("lookback", 20))
        entry_z = float(self.params.get("entry_z", 2.0))
        exit_z = float(self.params.get("exit_z", 0.0))

        rolling_mean = df["close"].rolling(window=lookback).mean()
        rolling_std = df["close"].rolling(window=lookback).std()
        df["zscore"] = (df["close"] - rolling_mean) / rolling_std.replace(0, np.nan)

        df["signal"] = 0
        df.loc[df["zscore"] < -entry_z, "signal"] = 1   # Buy when oversold
        df.loc[df["zscore"] > entry_z, "signal"] = -1   # Sell when overbought
        # Exit on mean reversion
        df.loc[(df["zscore"].abs() < exit_z) & (df["zscore"].shift(1).abs() >= exit_z), "signal"] = 0
        return df


class MomentumStrategy(BaseStrategy):
    name = "momentum"

    @classmethod
    def default_params(cls):
        return {"lookback": 20, "threshold": 0.0}

    @classmethod
    def param_schema(cls):
        return [
            {"key": "lookback", "label": "Lookback Period", "type": "int", "min": 5, "max": 500, "default": 20},
            {"key": "threshold", "label": "Momentum Threshold (%)", "type": "float", "min": 0, "max": 50, "default": 0},
        ]

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        lookback = int(self.params.get("lookback", 20))
        threshold = float(self.params.get("threshold", 0)) / 100

        df["momentum"] = df["close"].pct_change(periods=lookback)
        df["signal"] = 0
        df.loc[df["momentum"] > threshold, "signal"] = 1
        df.loc[df["momentum"] < -threshold, "signal"] = -1
        df["signal"] = df["signal"].diff().clip(-1, 1)
        return df


STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    "sma_crossover": SMAcrossover,
    "ema_crossover": EMAcrossover,
    "rsi": RSIStrategy,
    "macd": MACDStrategy,
    "bollinger_bands": BollingerBands,
    "mean_reversion": MeanReversion,
    "momentum": MomentumStrategy,
}


def get_strategy(name: str, params: dict) -> BaseStrategy:
    cls = STRATEGY_REGISTRY.get(name)
    if not cls:
        raise ValueError(f"Unknown strategy: {name}. Available: {list(STRATEGY_REGISTRY.keys())}")
    return cls(params)


def list_strategies() -> list[dict]:
    result = []
    for name, cls in STRATEGY_REGISTRY.items():
        result.append({
            "name": name,
            "label": name.replace("_", " ").title(),
            "default_params": cls.default_params(),
            "param_schema": cls.param_schema(),
        })
    return result
