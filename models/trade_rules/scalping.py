import numpy as np


# INFO: backtest用の処理
def generate_repulsion_column(candles, ema):
    method_thrust_checker = np.frompyfunc(repulsion_exist, 6, 1)
    result = method_thrust_checker(
        candles.trend, ema,
        candles.high.shift(2), candles.high.shift(1),
        candles.low.shift(2), candles.low.shift(1)
    )
    return result


def repulsion_exist(trend, ema, two_before_high, previous_high, two_before_low, previous_low):
    ''' 1, 2本前の足から見て、trend方向にcrossしていればentry可のsignを出す '''
    if trend == 'bull' \
        and two_before_high < previous_high \
        and ema < previous_high \
        and (two_before_low < ema or previous_low < ema):
        return 'long'
    elif trend == 'bear' \
        and two_before_low > previous_low \
        and previous_low < ema \
        and (ema < two_before_high or ema < previous_high):
        return 'short'
    return None


# INFO: backtest用の処理
# TODO: 使って無くない？ 2020/02/03
# def the_previous_satisfy_rules(candles):
#     ''' 各足において entry 可能かどうかを判定し、 candles dataframe に設定 '''
#     satisfy_preconditions = np.all(
#         candles.shift(1)[['in_the_band', 'stoc_allows']],
#         axis=1
#     )
#     candles.loc[satisfy_preconditions, 'entryable'] = candles[satisfy_preconditions].thrust
#     candles.loc[satisfy_preconditions, 'position'] = candles[satisfy_preconditions].thrust.copy()


# INFO: backtest用の処理
def set_entryable_prices(candles, spread):
    ''' entry した場合の price を candles dataframe に設定 '''
    long_index = candles.entryable == 'long'
    short_index = candles.entryable == 'short'
    candles.loc[long_index, 'entryable_price'] = candles[long_index].open + spread
    candles.loc[short_index, 'entryable_price'] = candles[short_index].open


def new_stoploss_price(position_type, current_sup, current_regist, old_stoploss):
    if position_type == 'long':
        if np.isnan(old_stoploss) or old_stoploss < current_sup:
            return current_sup
    elif position_type == 'short':
        if np.isnan(old_stoploss) or old_stoploss > current_regist:
            return current_regist

    return np.nan


# INFO: backtest用の処理
def commit_positions(candles, plus2sigma, minus2sigma, long_indexes, short_indexes, spread):
    ''' set exit-timing, price '''
    # TODO: long ポジションが残ったま short entry するバグが残っている stoploss_ver2 で発覚
    # bollinger_band に達したことによる exit
    long_exits_by_plus_band = long_indexes & (plus2sigma < candles.high)
    candles.loc[long_exits_by_plus_band, 'exitable'] = 'sell_exit'
    candles.loc[long_exits_by_plus_band, 'exitable_price'] = plus2sigma[long_exits_by_plus_band]

    long_exits_by_minus_band = long_indexes & (candles.low < minus2sigma)
    candles.loc[long_exits_by_minus_band, 'exitable'] = 'sell_exit'
    candles.loc[long_exits_by_minus_band, 'exitable_price'] = minus2sigma[long_exits_by_minus_band]

    short_exits_by_plus_band = short_indexes & (plus2sigma < candles.high)
    candles.loc[short_exits_by_plus_band, 'exitable'] = 'buy_exit'
    candles.loc[short_exits_by_plus_band, 'exitable_price'] = plus2sigma[short_exits_by_plus_band]

    short_exits_by_minus_band = short_indexes & (candles.low < minus2sigma)
    candles.loc[short_exits_by_minus_band, 'exitable'] = 'buy_exit'
    candles.loc[short_exits_by_minus_band, 'exitable_price'] = minus2sigma[short_exits_by_minus_band]

    # stoplossによるexit
    long_exits_by_sl = long_indexes & (candles.low < candles.possible_stoploss)
    candles.loc[long_exits_by_sl, 'exitable'] = 'sell_exit'
    candles.loc[long_exits_by_sl, 'exitable_price'] = candles[long_exits_by_sl].possible_stoploss

    short_exits_by_sl = short_indexes & (candles.high + spread > candles.possible_stoploss)
    candles.loc[short_exits_by_sl, 'exitable'] = 'buy_exit'
    candles.loc[short_exits_by_sl, 'exitable_price'] = candles[short_exits_by_sl].possible_stoploss

    # INFO: exitable column から position を確定
    candles['position'] = candles.exitable.fillna(method='ffill')
    # INFO: 2連続entry, entryなしでのexitを除去
    no_position_index = (candles.position == candles.position.shift(1)) \
                        & (candles.entryable_price.isna() | candles.exitable_price.isna())
    candles.loc[no_position_index, 'position'] = None
    candles['entry_price'] = candles.entryable_price


def position_is_exitable(close, last_plus_2sigma, last_minus_2sigma):
    if close < last_minus_2sigma or last_plus_2sigma < close:
        return True
    else:
        return False


def set_stoploss_prices(types, indicators):
    method_stoploss_generator = np.frompyfunc(new_stoploss_price, 4, 1)
    return method_stoploss_generator(
        types,
        indicators.support,
        indicators.regist,
        np.full(len(types), np.nan)
    )
