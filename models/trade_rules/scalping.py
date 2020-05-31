import numpy as np
import pandas as pd


# - - - - - - - - - - - - - - - - - - - - - - - -
#                Driver of logics
# - - - - - - - - - - - - - - - - - - - - - - - -
def generate_repulsion_column(candles, ema):
    method_thrust_checker = np.frompyfunc(repulsion_exist, 6, 1)
    result = method_thrust_checker(
        candles.trend, ema.shift(1),
        candles.high.shift(2), candles.high.shift(1),
        candles.low.shift(2), candles.low.shift(1)
    )
    return result


def set_entryable_prices(candles, spread):
    ''' entry した場合の price を candles dataframe に設定 '''
    long_index = candles.entryable == 'long'
    short_index = candles.entryable == 'short'
    candles.loc[long_index, 'entryable_price'] = candles[long_index].open + spread
    # TODO: 実際には open で entry することはなかなかできない
    candles.loc[short_index, 'entryable_price'] = candles[short_index].open


def commit_positions_by_loop(factor_dicts):
    loop_objects = factor_dicts[:-1]  # コピー変数: loop_objects への変更は factor_dicts にも及ぶ
    entry_direction = factor_dicts[0]['entryable']  # 'long', 'short' or nan

    def reset_next_position(index):
        factor_dicts[index + 1]['position'] = entry_direction = factor_dicts[index + 1]['entryable']
        return entry_direction

    for index, one_frame in enumerate(loop_objects):
        # entry 中でなければ continue
        if entry_direction == 'long':
            edge_price = one_frame['high']
            exit_type = 'sell_exit'
        elif entry_direction == 'short':
            edge_price = one_frame['low']
            exit_type = 'buy_exit'
        else:
            entry_direction = reset_next_position(index)
            continue

        exit_price = __decide_exit_price(entry_direction, one_frame, edge_price)
        # exit する理由がなければ continue
        if exit_price is None:
            continue

        # exit した場合のみここに到達する
        one_frame['exitable_price'] = exit_price
        one_frame['position'] = exit_type
        entry_direction = reset_next_position(index)

    return pd.DataFrame.from_dict(factor_dicts)[['position', 'exitable_price']]


def __decide_exit_price(entry_direction, one_frame, edge_price=None):
    def stoploss_in_the_candle(candle):
        return candle['low'] < candle['possible_stoploss'] < candle['high']

    exit_price = None
    if entry_direction == 'long' and stoploss_in_the_candle(one_frame):
        exit_price = one_frame['possible_stoploss']
    elif entry_direction == 'short' and stoploss_in_the_candle(one_frame):
        # TODO: one_frame['high'] + spread > one_frame['possible_stoploss'] # spread の考慮
        exit_price = one_frame['possible_stoploss']
    # elif is_exitable_by_bollinger(edge_price, one_frame['band_+2σ'], one_frame['band_-2σ']):
    #     exit_price = one_frame['band_+2σ'] if entry_direction == 'long' else one_frame['band_-2σ']
    # elif is_exitable_by_stoc_cross(entry_direction, stod=one_frame['stoD_3'], stosd=one_frame['stoSD_3']):
    #     exit_price = one_frame['low'] if entry_direction == 'long' else one_frame['high']
    elif is_exitable_by_d1_stoc_cross(entry_direction, d1_stod_greater=one_frame['stoD_over_stoSD']):
        exit_price = one_frame['low'] if entry_direction == 'long' else one_frame['high']
    return exit_price


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
def repulsion_exist(trend, previous_ema, two_before_high, previous_high, two_before_low, previous_low):
    ''' 1, 2本前の足から見て、trend方向にcrossしていればentry可のsignを出す '''
    # OPTIMIZE: rising, falling は試験的に削除したが、検証が必要
    #   => 他の条件が整っていさえすれば、早いタイミングでエントリーするようになった
    if trend == 'bull':
        # rising = two_before_high < previous_high
        touch_ema = two_before_low < previous_ema or previous_low < previous_ema
        leave_from_ema = previous_ema < previous_high
        # if rising and leave_from_ema and touch_ema:
        if leave_from_ema and touch_ema:
            return 'long'
    elif trend == 'bear':
        # falling = two_before_low > previous_low
        touch_ema = previous_ema < two_before_high or previous_ema < previous_high
        leave_from_ema = previous_ema > previous_low
        # if falling and leave_from_ema and touch_ema:
        if leave_from_ema and touch_ema:
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


def is_exitable_by_bollinger(spot_price, plus_2sigma, minus_2sigma):
    bollinger_is_touched = spot_price < minus_2sigma or plus_2sigma < spot_price

    if bollinger_is_touched:
        return True
    else:
        return False


def is_exitable_by_stoc_cross(position_type, stod, stosd):
    stoc_crossed = ((position_type == 'long') and (stod < stosd)) \
        or ((position_type == 'short') and (stod > stosd))

    if stoc_crossed:
        return True
    else:
        return False


def is_exitable_by_d1_stoc_cross(entry_direction, d1_stod_greater):
    stoc_crossed = ((entry_direction == 'long') and not d1_stod_greater) \
        or ((entry_direction == 'short') and d1_stod_greater)

    if stoc_crossed:
        return True
    else:
        return False
