import numpy as np


def identify_trend_type(c_price, sma, ema, parabo):
    '''
    Identify whether the trend type is 'bull', 'bear' or None

    Parameters
    ----------
    c_price : float
        current close price
    sma     : float
    ema     : float
    parabo  : float

    Returns
    -------
    string or None
    '''
    if sma < ema < c_price and parabo < c_price:
        return 'bull'
    elif sma > ema > c_price and parabo > c_price:
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


def commit_positions(candles, long_indexes, short_indexes, spread):
    ''' set exit-timing, price '''
    long_exits = long_indexes & (candles.low < candles.possible_stoploss)
    candles.loc[long_exits, 'position'] = 'sell_exit'
    candles.loc[long_exits, 'exitable_price'] = candles[long_exits].possible_stoploss

    short_exits = short_indexes & (candles.high + spread > candles.possible_stoploss)
    candles.loc[short_exits, 'position'] = 'buy_exit'
    candles.loc[short_exits, 'exitable_price'] = candles[short_exits].possible_stoploss

    # INFO: position column の整理
    candles.position.fillna(method='ffill', inplace=True)
    # INFO: 2連続entry, entryなしでのexitを除去
    no_position_index = (candles.position == candles.position.shift(1)) \
                        & (candles.entryable_price.isna() | candles.exitable_price.isna())
    candles.loc[no_position_index, 'position'] = None
