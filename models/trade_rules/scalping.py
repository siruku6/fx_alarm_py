import numpy as np
import pandas as pd


# - - - - - - - - - - - - - - - - - - - - - - - -
#                Driver of logics
# - - - - - - - - - - - - - - - - - - - - - - - -
def generate_repulsion_column(candles, ema):
    method_thrust_checker = np.frompyfunc(repulsion_exist, 6, 1)
    result = method_thrust_checker(
        candles.trend, ema,
        candles.high.shift(2), candles.high.shift(1),
        candles.low.shift(2), candles.low.shift(1)
    )
    return result


def set_entryable_prices(candles, spread):
    ''' entry した場合の price を candles dataframe に設定 '''
    long_index = candles.entryable == 'long'
    short_index = candles.entryable == 'short'
    candles.loc[long_index, 'entryable_price'] = candles[long_index].open + spread
    candles.loc[short_index, 'entryable_price'] = candles[short_index].open


def commit_positions_by_loop(factor_dicts):
    # last_object = factor_dicts[-1]
    loop_objects = factor_dicts[:-1]  # コピー変数: loop_objects への変更は factor_dicts にも及ぶ
    last_index = len(loop_objects)
    entry_direction = factor_dicts[0]['entryable']

    for index, one_frame in enumerate(loop_objects):
        # entry 中でなければ continue
        if entry_direction == 'long':
            edge_price = one_frame['high']
            exit_type = 'sell_exit'
        elif entry_direction == 'short':
            edge_price = one_frame['low']
            exit_type = 'buy_exit'
        else:
            factor_dicts[index + 1]['position'] = entry_direction = factor_dicts[index + 1]['entryable']
            continue

        # exit する理由がなければ continue
        if entry_direction == 'long' and one_frame['low'] < one_frame['possible_stoploss']:
            one_frame['exitable_price'] = one_frame['possible_stoploss']
        elif entry_direction == 'short' and one_frame['high'] > one_frame['possible_stoploss']:
            # TODO: one_frame['high'] + spread > one_frame['possible_stoploss'] # spread の考慮
            one_frame['exitable_price'] = one_frame['possible_stoploss']
        elif is_exitable_by_bollinger(
                edge_price, one_frame['band_+2σ'], one_frame['band_-2σ'],
                trend=None, stod=None, stosd=None
            ):
            if entry_direction == 'long':
                one_frame['exitable_price'] = one_frame['band_+2σ']
            else:
                one_frame['exitable_price'] = one_frame['band_-2σ']
        else:
            continue

        # exit した場合のみここに到達する
        one_frame['position'] = exit_type
        factor_dicts[index + 1]['position'] = entry_direction = factor_dicts[index + 1]['entryable']

    return pd.DataFrame.from_dict(factor_dicts)[['position', 'exitable_price']]


def set_stoploss_prices(types, indicators):
    method_stoploss_generator = np.frompyfunc(new_stoploss_price, 4, 1)
    return method_stoploss_generator(
        types,
        indicators.support,
        indicators.regist,
        np.full(len(types), np.nan)
    )


# - - - - - - - - - - - - - - - - - - - - - - - -
#                  Trade Logics
# - - - - - - - - - - - - - - - - - - - - - - - -
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


def new_stoploss_price(position_type, current_sup, current_regist, old_stoploss):
    if position_type == 'long':
        if np.isnan(old_stoploss) or old_stoploss < current_sup:
            return current_sup
    elif position_type == 'short':
        if np.isnan(old_stoploss) or old_stoploss > current_regist:
            return current_regist

    return np.nan


def detect_exitable_by_bollinger(is_long, is_short, high, low, plus2sigma, minus2sigma):
    if low < minus2sigma: exit_price = minus2sigma
    elif plus2sigma < high: exit_price = plus2sigma
    else: return np.nan, np.nan

    if is_long: exitable = 'sell_exit'
    elif is_short: exitable = 'buy_exit'
    else: return np.nan, np.nan

    return exitable, exit_price


def is_exitable_by_bollinger(spot_price, plus_2sigma, minus_2sigma, trend=None, stod=None, stosd=None):
    bollinger_is_touched = spot_price < minus_2sigma or plus_2sigma < spot_price
    stoc_crossed = ((trend == 'xxxxxxxxxxx') and (stod < stosd)) \
                 or ((trend == 'xxxxxxxxxxx') and (stod > stosd))

    if bollinger_is_touched:
        return True
    else:
        return False
