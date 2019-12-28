import numpy as np


def generate_repulsion_column(candles, ema):
    method_thrust_checker = np.frompyfunc(repulsion_exist, 6, 1)
    result = method_thrust_checker(
        candles.trend, ema,
        candles.high.shift(2), candles.high.shift(1),
        candles.low.shift(2), candles.low.shift(1)
    )
    return result


def repulsion_exist(trend, ema, two_before_high, previous_high, two_before_low, previous_low):
    if trend == 'bull' \
        and two_before_high < previous_high \
        and ema < previous_high \
        and (two_before_low < ema or previous_low < ema):
        return 'long'
    elif trend == 'bear' \
        and two_before_low > previous_low \
        and previous_low < ema \
        and (ema < two_before_low or ema < previous_low):
        return 'short'
    return None


def the_previous_satisfy_rules(candles):
    ''' 各足において entry 可能かどうかを判定し、 candles dataframe に設定 '''
    satisfy_preconditions = np.all(
        candles.shift(1)[['in_the_band', 'stoc_allows']],
        axis=1
    )
    candles.loc[satisfy_preconditions, 'entryable'] = candles[satisfy_preconditions].thrust
    candles.loc[satisfy_preconditions, 'position'] = candles[satisfy_preconditions].thrust.copy()


def commit_positions(candles, plus2sigma, minus2sigma, long_indexes, short_indexes, spread):
    ''' set exit-timing, price '''
    # bollinger_band に達したことによる exit
    long_exits_by_plus_band = long_indexes & (plus2sigma < candles.high)
    candles.loc[long_exits_by_plus_band, 'position'] = 'sell_exit'
    candles.loc[long_exits_by_plus_band, 'exitable_price'] = plus2sigma[long_exits_by_plus_band]

    long_exits_by_minus_band = long_indexes & (candles.low < minus2sigma)
    candles.loc[long_exits_by_minus_band, 'position'] = 'sell_exit'
    candles.loc[long_exits_by_minus_band, 'exitable_price'] = minus2sigma[long_exits_by_minus_band]

    short_exits_by_plus_band = short_indexes & (plus2sigma < candles.high)
    candles.loc[short_exits_by_plus_band, 'position'] = 'buy_exit'
    candles.loc[short_exits_by_plus_band, 'exitable_price'] = plus2sigma[short_exits_by_plus_band]

    short_exits_by_minus_band = short_indexes & (candles.low < minus2sigma)
    candles.loc[short_exits_by_minus_band, 'position'] = 'buy_exit'
    candles.loc[short_exits_by_minus_band, 'exitable_price'] = minus2sigma[short_exits_by_minus_band]

    # stoplossによるexit
    long_exits_by_sl = long_indexes & (candles.low < candles.possible_stoploss)
    candles.loc[long_exits_by_sl, 'position'] = 'sell_exit'
    candles.loc[long_exits_by_sl, 'exitable_price'] = candles[long_exits_by_sl].possible_stoploss

    short_exits_by_sl = short_indexes & (candles.high + spread > candles.possible_stoploss)
    candles.loc[short_exits_by_sl, 'position'] = 'buy_exit'
    candles.loc[short_exits_by_sl, 'exitable_price'] = candles[short_exits_by_sl].possible_stoploss

    # INFO: position column の整理
    import pdb; pdb.set_trace()
    candles.position.fillna(method='ffill', inplace=True)
    # candles.loc[candles.position == candles.position.shift(1), 'position'] = None

    # INFO: entry したその足で exit した足があった場合、この処理が必須
    short_life_entries = candles.entryable_price.notna() & candles.exitable_price.notna()
    candles.loc[short_life_entries, 'position'] = candles.entryable
