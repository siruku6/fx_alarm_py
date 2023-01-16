from typing import List, Union

import numpy as np
import pandas as pd

from src.analyzer import Analyzer
from src.candle_storage import FXBase
from src.lib.time_series_generator import (  # generate_ema_allows_column,
    generate_band_expansion_column,
    generate_following_trend_column,
    generate_getting_steeper_column,
    generate_in_bands_column,
    generate_thrust_column,
)
from src.trade_rules import base, scalping
from src.trader_config import TraderConfig


# -------------------------------------------------------------
# Public methods
# -------------------------------------------------------------
def prepare_indicators() -> pd.DataFrame:
    ana = Analyzer()
    ana.calc_indicators(
        FXBase.get_candles(),
        long_span_candles=FXBase.get_long_span_candles(),
    )
    indicators: pd.DataFrame = ana.get_indicators()

    candles: pd.DataFrame = _merge_long_indicators(ana.get_long_indicators())
    FXBase.set_candles(candles)
    return indicators


# -------------------------------------------------------------
# Private methods
# -------------------------------------------------------------
def _merge_long_indicators(long_indicators: pd.DataFrame) -> pd.DataFrame:
    candles: pd.DataFrame = FXBase.get_candles()
    if "stoD_over_stoSD" in candles.columns:
        return candles

    tmp_df = candles.merge(long_indicators, on="time", how="left")
    # tmp_df['long_stoD'].fillna(method='ffill', inplace=True)
    # tmp_df['long_stoSD'].fillna(method='ffill', inplace=True)
    tmp_df.loc[:, "stoD_over_stoSD"] = (
        tmp_df["stoD_over_stoSD"].fillna(method="ffill").fillna(False)
    )

    tmp_df["long_20SMA"].fillna(method="ffill", inplace=True)
    tmp_df["long_10EMA"].fillna(method="ffill", inplace=True)
    long_ma = (
        tmp_df[["long_10EMA", "long_20SMA"]]
        .copy()
        .rename(columns={"long_10EMA": "10EMA", "long_20SMA": "20SMA"})
    )
    tmp_df["long_trend"] = base.generate_trend_column(long_ma, candles.close)

    return tmp_df


def prepare_trade_signs(
    config: TraderConfig,
    rule: str,
    candles: pd.DataFrame,
    indicators: pd.DataFrame,
) -> pd.DataFrame:
    print("[Trader] preparing base-data for judging ...")

    candles["trend"] = base.generate_trend_column(indicators, candles.close)
    trend = pd.DataFrame(
        {
            "bull": np.where(candles["trend"] == "bull", True, False),
            "bear": np.where(candles["trend"] == "bear", True, False),
        }
    )
    candles["thrust"] = generate_thrust_column(rule, candles, trend, indicators)
    # 60EMA is necessary?
    # candles['ema60_allows'] = generate_ema_allows_column(candles=candles)

    entryable_prices: Union[np.ndarray, pd.Series]
    if config.operation in ["live", "forward_test"]:
        entryable_prices = candles["close"]
    else:
        entryable_prices = generate_entryable_price(
            rule,
            candles.rename(columns={"thrust": "entryable"}),
            config.static_spread,
        )

    # candles["entryable_price"] = entryable_prices
    candles["in_the_band"] = generate_in_bands_column(indicators, entryable_prices)
    candles["band_expansion"] = generate_band_expansion_column(
        df_bands=indicators[["sigma*2_band", "sigma*-2_band"]]
    )
    candles["ma_gap_expanding"] = generate_getting_steeper_column(trend, indicators)
    candles["sma_follow_trend"] = generate_following_trend_column(trend, indicators["20SMA"])
    candles["stoc_allows"] = base.generate_stoc_allows_column(indicators, sr_trend=candles["trend"])
    return candles


def generate_entryable_price(
    rule: str,
    candles: pd.DataFrame,
    static_spread: float,
) -> np.ndarray:
    """
    Generate possible prices assuming that entries are done

    Parameters
    ----------
    candles : pd.DataFrame
        Index:
            Any
        Columns:
            Name: open,      dtype: float64 (required)
            Name: high,      dtype: float64 (required)
            Name: low,       dtype: float64 (required)
            Name: entryable, dtype: object  (required)

    Returns
    -------
    np.ndarray
    """
    if rule == "scalping":
        entryable_price: np.ndarray = scalping.generate_entryable_prices(
            candles[["open", "entryable"]],
            static_spread,
        )
    elif rule == "swing":
        entryable_price = base.generate_entryable_prices(
            candles[["open", "high", "low", "entryable"]],
            static_spread,
        )
    return entryable_price


def mark_entryable_rows(entry_filters: List[str], candles: pd.DataFrame) -> pd.DataFrame:
    """
    Judge whether it is entryable or not on each row.
    Then set the result in the column 'entryable'.
    """
    entryable = np.all(candles[entry_filters], axis=1)
    candles.loc[entryable, "entryable"] = candles[entryable]["thrust"]
    return candles
