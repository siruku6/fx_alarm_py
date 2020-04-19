import numpy as np


def thrusting_exist(trend, two_before_high, previous_high, two_before_low, previous_low):
    if trend == 'bull' and two_before_high < previous_high:
        return 'long'
    elif trend == 'bear' and two_before_low > previous_low:
        return 'short'
    return None


def generate_thrust_column(candles):
    method_thrust_checker = np.frompyfunc(thrusting_exist, 5, 1)
    result = method_thrust_checker(
        candles.trend,
        candles.high.shift(2), candles.high.shift(1),
        candles.low.shift(2), candles.low.shift(1)
    )
    return result


def the_previous_satisfy_rules(candles, entry_filter):
    ''' 各足において entry 可能かどうかを判定し、 candles dataframe に設定 '''
    satisfy_preconditions = np.all(
        # candles.shift(1)[['in_the_band', 'ma_gap_expanding', 'sma_follow_trend', 'stoc_allows', 'ema60_allows', 'band_expansion']],
        candles[entry_filter],
        axis=1
    )
    candles.loc[satisfy_preconditions, 'entryable'] = candles[satisfy_preconditions].thrust
    # TODO: この position はいらないっぽい scalping では確認済み。 wait_close でも不要であれば消す
    candles.loc[satisfy_preconditions, 'position'] = candles[satisfy_preconditions].thrust.copy()
    # INFO: sclping rule 用にのみ必要なデータ ではなく、そもそもいらないっぽい
    # candles.loc[:, 'exitable'] = candles.loc[:, 'position'].copy()
