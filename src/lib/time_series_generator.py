import numpy as np
import pandas as pd

import src.trade_rules.scalping as scalping


#
# Methods for judging Entry or Close
#
def generate_thrust_column_for_swing(
    candles: pd.DataFrame,
    trend: pd.DataFrame,
    _: pd.DataFrame,
) -> pd.Series:
    # INFO: the most highest or lowest in last 3 candles
    recent_highests: pd.Series = candles["high"] == candles["high"].rolling(window=3).max()
    recent_lowests: pd.Series = candles["low"] == candles["low"].rolling(window=3).min()

    up_thrusts: pd.Series = recent_highests & trend["bull"]
    down_thrusts: pd.Series = recent_lowests & trend["bear"]

    thrust_type_series: pd.Series = pd.Series(np.full(len(candles), None))
    thrust_type_series[up_thrusts] = "long"
    thrust_type_series[down_thrusts] = "short"
    return thrust_type_series

    # INFO: decide 'thrust' by only comparing with shift(1)
    # method_thrust_checker = np.frompyfunc(base_rules.detect_thrust, 5, 1)
    # result = method_thrust_checker(
    #     candles.trend,
    #     candles.high.shift(1), candles.high,
    #     candles.low.shift(1), candles.low
    # )
    # return result


def generate_thrust_column(
    method_type: str,
    candles: pd.DataFrame,
    trend: pd.Series,
    indicators: pd.DataFrame,
) -> pd.Series:
    if method_type == "swing":
        return generate_thrust_column_for_swing(candles, trend, indicators)
    elif method_type == "scalping":
        return scalping.generate_repulsion_column(candles, ema=indicators["10EMA"])


# 60EMA is necessary?
def generate_ema_allows_column(candles: pd.DataFrame, indicators: pd.DataFrame) -> np.ndarray:
    ema60 = indicators["60EMA"]
    ema60_allows_bull = np.all(np.array([candles.bull, ema60 < candles.close]), axis=0)
    ema60_allows_bear = np.all(np.array([candles.bear, ema60 > candles.close]), axis=0)
    return np.any(np.array([ema60_allows_bull, ema60_allows_bear]), axis=0)  # type: ignore


def generate_in_bands_column(
    indicators: pd.DataFrame,
    entryable_prices: pd.Series,
) -> np.ndarray:
    """
    Generate the column shows whether if the price is remaining between 2-sigma-bands
    """
    df_over_band_detection = pd.DataFrame(
        {
            "under_positive_band": indicators["sigma*2_band"] > entryable_prices,
            "above_negative_band": indicators["sigma*-2_band"] < entryable_prices,
        }
    )
    return np.all(df_over_band_detection, axis=1)  # type: ignore


def generate_band_expansion_column(df_bands: pd.DataFrame, shift_size: int = 3) -> pd.Series:
    """
    generate boolean series
        True: bollinger_band is expanding
        False: bollinger_band is shrinking
    """
    # OPTIMIZE: bandについては、1足前(shift(1))に広がっていることを条件にしてもよさそう
    #   その場合、広がっていることの確定を待つことになるので、条件としては厳しくなる
    bands_gap = df_bands["sigma*2_band"] - df_bands["sigma*-2_band"]  # .shift(1).fillna(0.0)
    return bands_gap.rolling(window=shift_size).max() == bands_gap
    # return bands_gap.shift(shift_size) < bands_gap


def generate_getting_steeper_column(df_trend: pd.DataFrame, indicators: pd.DataFrame) -> np.ndarray:
    """
    generate boolean series
        True: Moving Averageが勢いづいている
    """
    gap_of_ma: pd.Series = indicators["10EMA"] - indicators["20SMA"]
    result: pd.Series = gap_of_ma.shift(1) < gap_of_ma

    # INFO: 上昇方向に勢いづいている
    is_long_steeper: pd.Series = df_trend["bull"].fillna(False) & result
    # INFO: 下降方向に勢いづいている
    is_short_steeper: pd.Series = df_trend["bear"].fillna(False) & np.where(result, False, True)

    return np.any([is_long_steeper, is_short_steeper], axis=0)  # type: ignore


def generate_following_trend_column(df_trend: pd.DataFrame, series_sma: pd.Series) -> np.ndarray:
    """
    generate boolean series
        True: Moving Average is following the direction of trend
    """
    # series_sma = indicators["20SMA"].copy()
    df_tmp = df_trend.copy()
    df_tmp["sma_up"] = series_sma.shift(1) < series_sma
    df_tmp["sma_down"] = series_sma.shift(1) > series_sma

    both_up: np.ndarray = np.all(df_tmp[["bull", "sma_up"]], axis=1)
    both_down: np.ndarray = np.all(df_tmp[["bear", "sma_down"]], axis=1)
    return np.any([both_up, both_down], axis=0)  # type: ignore
