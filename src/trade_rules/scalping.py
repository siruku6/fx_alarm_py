from typing import Optional

import numpy as np
import pandas as pd


# - - - - - - - - - - - - - - - - - - - - - - - -
#                Driver of logics
# - - - - - - - - - - - - - - - - - - - - - - - -
def generate_repulsion_column(candles: pd.DataFrame, ema: pd.Series) -> np.ndarray:
    method_thrust_checker = np.frompyfunc(repulsion_exist, 6, 1)
    result: np.ndarray = method_thrust_checker(
        candles["trend"],
        ema.shift(1),
        candles["high"].shift(2),
        candles["high"].shift(1),
        candles["low"].shift(2),
        candles["low"].shift(1),
    )
    return result


def generate_entryable_prices(candles: pd.DataFrame, spread: float) -> np.ndarray:
    """
    Generate possible prices assuming that entries are done

    Parameters
    ----------
    candles : pd.DataFrame
        Index:
            Any
        Columns:
            Name: open,      dtype: float64 (required)
            Name: entryable, dtype: object  (required)
    spread : float

    Returns
    -------
    np.ndarray
    """
    result: np.ndarray = np.full_like(candles["open"], np.nan, dtype=np.float64)
    long_index: pd.Series = candles["entryable"] == "long"
    short_index: pd.Series = candles["entryable"] == "short"

    # TODO: 実際には open で entry することはなかなかできない
    result[long_index] = candles.loc[long_index, "open"] + spread
    result[short_index] = candles.loc[short_index, "open"]
    return result


# - - - - - - - - - - - - - - - - - - - - - - - -
#                  Trade Logics
# - - - - - - - - - - - - - - - - - - - - - - - -
def repulsion_exist(
    trend: str,
    previous_ema: float,
    two_before_high: float,
    previous_high: float,
    two_before_low: float,
    previous_low: float,
) -> Optional[str]:
    """
    "long": the price surpass 10ema in bull trend
    "short": the price underperform 10ema in bear trend
    1, 2本前の足から見て、trend方向にcrossしていればentry可のsignを出す
    """
    # OPTIMIZE: rising, falling は試験的に削除したが、検証が必要
    #   => 他の条件が整っていさえすれば、早いタイミングでエントリーするようになった
    if trend == "bull":
        # rising = two_before_high < previous_high
        touch_ema = two_before_low < previous_ema or previous_low < previous_ema
        leave_from_ema = previous_ema < previous_high
        # if rising and leave_from_ema and touch_ema:
        if leave_from_ema and touch_ema:
            return "long"
    elif trend == "bear":
        # falling = two_before_low > previous_low
        touch_ema = previous_ema < two_before_high or previous_ema < previous_high
        leave_from_ema = previous_ema > previous_low
        # if falling and leave_from_ema and touch_ema:
        if leave_from_ema and touch_ema:
            return "short"
    return None
