import numpy as np
import pandas as pd

from models.trader_config import TraderConfig


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


def previous_candle_otherside(position_type, previous_low, previous_high, config):
    if position_type == 'long':
        new_stoploss = previous_low - config.stoploss_buffer_pips
        return round(new_stoploss, 3)
    elif position_type == 'short':
        new_stoploss = previous_high + config.stoploss_buffer_pips + config.static_spread
        return round(new_stoploss, 3)


def support_or_registance(position_type, current_sup, current_regist):
    if position_type == 'long':
        stoploss = current_sup
        return stoploss
    elif position_type == 'short':
        stoploss = current_regist
        return stoploss
