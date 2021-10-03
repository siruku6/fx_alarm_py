import numpy as np
import pandas as pd

from models.candle_storage import FXBase


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#                       Multople rows Processor
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def generate_entryable_prices(candles: pd.DataFrame, spread: float) -> np.ndarray:
    '''
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
    spread : float
        Example:
            0.014

    Returns
    -------
    np.ndarray
    '''
    entryable_prices: np.ndarray = np.full_like(candles['open'], np.nan)

    # INFO: long-entry
    long_index: pd.Series = candles['entryable'] == 'long'
    long_entry_prices: pd.Series = pd.DataFrame({
        'previous_high': candles.shift(1).loc[long_index, 'high'],
        'current_open': candles.loc[long_index, 'open']
    }).max(axis=1) + spread
    entryable_prices[long_index] = long_entry_prices

    # INFO: short-entry
    short_index: pd.Series = candles['entryable'] == 'short'
    short_entry_prices: pd.Series = pd.DataFrame({
        'previous_low': candles.shift(1).loc[short_index, 'low'],
        'current_open': candles.loc[short_index, 'open']
    }).min(axis=1)
    entryable_prices[short_index] = short_entry_prices
    return entryable_prices


def commit_positions(
    candles: pd.DataFrame, long_indexes: pd.Series, short_indexes: pd.Series, spread: float
) -> None:
    '''
    set timing and price of exit

    Parameters
    ----------
    candles : pd.DataFrame
        Index:
            Any
        Columns:
            Name: high,              dtype: float64 (required)
            Name: low,               dtype: float64 (required)
            Name: entryable,         dtype: object  (required)
            Name: entryable_price,   dtype: float64 (required)
            Name: possible_stoploss, dtype: float64 (required)
            Name: time,              dtype: object  # datetime64[ns]

    Returns
    -------
    None
    '''
    candles.loc[:, 'position'] = candles['entryable'].copy()

    long_exits = long_indexes & (candles['low'] < candles['possible_stoploss'])
    candles.loc[long_exits, 'position'] = 'sell_exit'
    candles.loc[long_exits, 'exitable_price'] = candles.loc[long_exits, 'possible_stoploss']

    short_exits = short_indexes & (candles['high'] + spread > candles['possible_stoploss'])
    candles.loc[short_exits, 'position'] = 'buy_exit'
    candles.loc[short_exits, 'exitable_price'] = candles.loc[short_exits, 'possible_stoploss']

    # INFO: position column の整理
    candles['position'].fillna(method='ffill', inplace=True)

    # INFO: 2連続entry, entryなしでのexitを除去
    no_position_index = \
        (candles['position'] == candles['position'].shift(1)) \
        & (candles['entryable_price'].isna() | candles['exitable_price'].isna())
    candles.loc[no_position_index, 'position'] = None


def generate_trend_column(indicators, c_prices):
    sma = indicators['20SMA']
    ema = indicators['10EMA']
    method_trend_checker = np.frompyfunc(identify_trend_type, 3, 1)

    trend = method_trend_checker(c_prices, sma, ema)
    return trend


def generate_stoc_allows_column(indicators, sr_trend):
    ''' stocがtrendに沿う値を取っているか判定する列を返却 '''
    stod = indicators['stoD_3']
    stosd = indicators['stoSD_3']
    column_generator = np.frompyfunc(stoc_allows_entry, 3, 1)
    return column_generator(stod, stosd, sr_trend)


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#                         Single row Processor
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def identify_trend_type(c_price, sma, ema):
    '''
    Identify whether the trend type is 'bull', 'bear' or None

    Parameters
    ----------
    c_price : float
        current close price
    sma     : float
    ema     : float

    Returns
    -------
    string or None
    '''
    if np.any(np.isnan([sma, ema, c_price])):
        return None
    elif sma < ema < c_price:  # and parabo < c_price:
        return 'bull'
    elif sma > ema > c_price:  # and parabo > c_price:
        return 'bear'
    else:
        return None


def detect_thrust(trend, previous_high, high, previous_low, low):
    if trend == 'bull' and not np.isnan(previous_high) and previous_high < high:
        return 'long'
    elif trend == 'bear' and not np.isnan(previous_low) and previous_low > low:
        return 'short'
    else:
        return None


def stoc_allows_entry(stod, stosd, trend):
    if trend == 'bull' and (stod > stosd or stod > 80):
        return True
    elif trend == 'bear' and (stod < stosd or stod < 20):
        return True

    return False


def new_stoploss_price(position_type, previous_low, previous_high, old_stoploss, stoploss_buf, static_spread):
    if position_type == 'long':
        new_stoploss = previous_low - stoploss_buf
        return round(max(new_stoploss, old_stoploss), 3)
    elif position_type == 'short':
        new_stoploss = previous_high + stoploss_buf + static_spread
        return round(min(new_stoploss, old_stoploss), 3)


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#                          Old trade rules
#                   These rules are now unused ....
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def sma_run_along_trend(self, index, trend):
    sma = self._indicators['20SMA']
    if trend == 'bull' and sma[index - 1] < sma[index]:
        return True
    elif trend == 'bear' and sma[index - 1] > sma[index]:
        return True

    if self._operation == 'live':
        print('[Trader] Trend: {}, 20SMA: {} -> {}'.format(trend, sma[index - 1], sma[index]))
        self._log_skip_reason('c. 20SMA not run along trend')
    return False


def over_2_sigma(self, index, price):
    if self._indicators['sigma*2_band'][index] < price \
            or self._indicators['sigma*-2_band'][index] > price:
        if self._operation == 'live':
            self._log_skip_reason(
                'c. {}: price is over 2sigma'.format(FXBase.get_candles().time[index])
            )
        return True

    return False
