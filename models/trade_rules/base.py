import numpy as np


def detect_trend_type(c_price, sma, ema, parabo):
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
    position_ser = candles.position
    candles.loc[position_ser == position_ser.shift(1), 'position'] = None

    # INFO: entry したその足で exit した足があった場合、この処理が必須
    short_life_entries = candles.entryable_price.notna() & candles.exitable_price.notna()
    candles.loc[short_life_entries, 'position'] = candles.entryable
