import numpy as np
import pandas as pd

from models.trader_config import TraderConfig


def previous_candle_otherside(
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
