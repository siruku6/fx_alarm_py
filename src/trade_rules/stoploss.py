from typing import Any, Optional, Tuple

import numpy as np
import pandas as pd

from src.trader_config import TraderConfig


def previous_candle_othersides(
    candles: pd.DataFrame, entry_direction: pd.Series, config: TraderConfig
) -> np.ndarray:
    possible_stoploss: np.ndarray = np.full_like(candles["low"], np.nan)
    long_indexes = entry_direction == "long"
    short_indexes = entry_direction == "short"

    possible_stoploss[long_indexes] = (
        candles.shift(1)[long_indexes]["low"] - config.stoploss_buffer_pips
    )
    possible_stoploss[short_indexes] = (
        candles.shift(1)[short_indexes]["high"] + config.stoploss_buffer_pips + config.static_spread
    )

    return possible_stoploss


def step_trailing(
    position_type: str, previous_low: float, previous_high: float, config: TraderConfig, **_: Any
) -> Optional[float]:
    new_stoploss: float
    if position_type == "long":
        new_stoploss = previous_low - config.stoploss_buffer_pips
        return round(new_stoploss, 3)
    elif position_type == "short":
        new_stoploss = previous_high + config.stoploss_buffer_pips + config.static_spread
        return round(new_stoploss, 3)


def generate_sup_reg_stoploss(
    series_supports: pd.Series,
    series_resgistance: pd.Series,
) -> Tuple["pd.Series", "pd.Series"]:
    previous_support: pd.Series = series_supports.shift(1)
    previous_resgistance: pd.Series = series_resgistance.shift(1)
    return previous_support, previous_resgistance


def support_or_registance(
    position_type: str, current_sup: float, current_regist: float, **_: Any
) -> Optional[float]:
    stoploss: Optional[float] = None
    if position_type == "long":
        stoploss = current_sup
    elif position_type == "short":
        stoploss = current_regist
    return stoploss


STRATEGIES = {
    "step": step_trailing,
    "support": support_or_registance,
}
