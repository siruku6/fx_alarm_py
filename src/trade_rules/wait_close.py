import numpy as np


def thrusting_exist(trend, two_before_high, previous_high, two_before_low, previous_low):
    if trend == "bull" and two_before_high < previous_high:
        return "long"
    elif trend == "bear" and two_before_low > previous_low:
        return "short"
    return None


def generate_thrust_column(candles):
    method_thrust_checker = np.frompyfunc(thrusting_exist, 5, 1)
    result = method_thrust_checker(
        candles.trend,
        candles.high.shift(2),
        candles.high.shift(1),
        candles.low.shift(2),
        candles.low.shift(1),
    )
    return result


# def the_previous_satisfy_rules(preconditions):
#     ''' 各足において entry 可能かどうかを判定し、 candles dataframe に設定 '''
#     satisfy_preconditions = np.all(preconditions, axis=1)
#     return satisfy_preconditions

#     # TODO: この position はいらないっぽい scalping swing では確認済み。 wait_close でも不要であれば消す
#     # candles.loc[satisfy_preconditions, 'position'] = candles[satisfy_preconditions]['thrust'].copy()
