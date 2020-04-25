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
    loop_objects = factor_dicts[:-1]  # コピー変数: loop_objects への変更は factor_dicts にも及ぶ
    entry_direction = factor_dicts[0]['entryable']  # 'long', 'short' or nan

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
        # elif is_exitable_by_bollinger(
        #         edge_price, one_frame['band_+2σ'], one_frame['band_-2σ'],
        #         direction=entry_direction, stod=one_frame['stoD:3'], stosd=one_frame['stoSD:3']
        #     ):
        #     if entry_direction == 'long':
        #         one_frame['exitable_price'] = one_frame['band_+2σ']
        #     else:
        #         one_frame['exitable_price'] = one_frame['band_-2σ']
        elif is_exitable_by_stoc_cross(
                edge_price, one_frame['band_+2σ'], one_frame['band_-2σ'],
                direction=entry_direction, stod=one_frame['stoD:3'], stosd=one_frame['stoSD:3']
            ):
            one_frame['exitable_price'] = one_frame['close']
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
    if trend == 'bull':
        rising = two_before_high < previous_high
        over_ema = ema < previous_high
        under_ema_before = two_before_low < ema or previous_low < ema
        if rising and over_ema and under_ema_before:
            return 'long'
    elif trend == 'bear':
        falling = two_before_low > previous_low
        under_ema = previous_low < ema
        over_ema_before = ema < two_before_high or ema < previous_high
        if falling and under_ema and over_ema_before:
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


def is_exitable_by_stoc_cross(spot_price, plus_2sigma, minus_2sigma, direction=None, stod=None, stosd=None):
    stoc_crossed = ((direction == 'long') and (stod < stosd)) \
                 or ((direction == 'short') and (stod > stosd))

    if stoc_crossed:
        return True
    else:
        return False


def is_exitable_by_bollinger(spot_price, plus_2sigma, minus_2sigma, direction=None, stod=None, stosd=None):
    bollinger_is_touched = spot_price < minus_2sigma or plus_2sigma < spot_price

    if bollinger_is_touched:
        return True
    else:
        return False
