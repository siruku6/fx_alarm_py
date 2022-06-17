from typing import Optional

import numpy as np
import pandas as pd

from src.trader_config import TraderConfig


def previous_candle_othersides(
    candles: pd.DataFrame, entry_direction: pd.Series, config: TraderConfig
):
    possible_stoploss: np.ndarray = np.full_like(candles['low'], np.nan)
    long_indexes = entry_direction == 'long'
    short_indexes = entry_direction == 'short'

    possible_stoploss[long_indexes] = candles.shift(1)[long_indexes]['low'] - config.stoploss_buffer_pips
    possible_stoploss[short_indexes] = candles.shift(1)[short_indexes]['high'] \
        + config.stoploss_buffer_pips \
        + config.static_spread

    return possible_stoploss


def step_trailing(
    position_type: str, previous_low: float, previous_high: float, config: TraderConfig, **_
) -> Optional[float]:
    new_stoploss: float
    if position_type == 'long':
        new_stoploss = previous_low - config.stoploss_buffer_pips
        return round(new_stoploss, 3)
    elif position_type == 'short':
        new_stoploss = previous_high + config.stoploss_buffer_pips + config.static_spread
        return round(new_stoploss, 3)


def support_or_registance(position_type: str, current_sup: float, current_regist: float, **_) -> Optional[float]:
    stoploss: float
    if position_type == 'long':
        stoploss = current_sup
        return stoploss
    elif position_type == 'short':
        stoploss = current_regist
        return stoploss


STRATEGIES = {
    'step': step_trailing,
    'support': support_or_registance,
}
