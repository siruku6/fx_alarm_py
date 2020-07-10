import numpy as np
import pandas as pd


def set_entryable_prices(candles, spread):
    ''' entry した場合の price を candles dataframe に設定 '''
    # INFO: long-entry
    long_index = candles.entryable == 'long'
    long_entry_prices = pd.DataFrame({
        'previous_high': candles.shift(1)[long_index].high,
        'current_open': candles[long_index].open
    }).max(axis=1) + spread
    candles.loc[long_index, 'entryable_price'] = long_entry_prices

    # INFO: short-entry
    short_index = candles.entryable == 'short'
    short_entry_prices = pd.DataFrame({
        'previous_low': candles.shift(1)[short_index].low,
        'current_open': candles[short_index].open
    }).min(axis=1)
    candles.loc[short_index, 'entryable_price'] = short_entry_prices


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


def detect_thrust2(up_thrust, down_thrust):
    if up_thrust:
        return 'long'
    elif down_thrust:
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
    if self._indicators['band_+2σ'][index] < price or \
    self._indicators['band_-2σ'][index] > price:
        if self._operation == 'live':
            self._log_skip_reason(
                'c. {}: price is over 2sigma'.format(FXBase.get_candles().time[index])
            )
        return True

    return False

def expand_moving_average_gap(self, index, trend):
    sma = self._indicators['20SMA']
    ema = self._indicators['10EMA']

    previous_gap = ema[index - 1] - sma[index - 1]
    current_gap = ema[index] - sma[index]

    if trend == 'bull':
        ma_gap_is_expanding = previous_gap < current_gap
    elif trend == 'bear':
        ma_gap_is_expanding = previous_gap > current_gap

    if not ma_gap_is_expanding and self._operation == 'live':
        self._log_skip_reason(
            'c. {}: MA_gap is shrinking,\n  10EMA: {} -> {},\n  20SMA: {} -> {}'.format(
                FXBase.get_candles().time[index],
                ema[index - 1], ema[index],
                sma[index - 1], sma[index]
            )
        )
    return ma_gap_is_expanding

def find_thrust(self, index, candles, trend):
    '''
    thrust発生の有無と方向を判定して返却する
    '''
    direction = None
    if trend == 'bull' and candles[:index + 1].tail(10).high.idxmax() == index:
        direction = 'long'
    elif trend == 'bear' and candles[:index + 1].tail(10).low.idxmin() == index:
        direction = 'short'

    if direction is not None:
        return direction

    if self._operation == 'live':
        print('[Trader] Trend: {}, high-1: {}, high: {}, low-1: {}, low: {}'.format(
            trend,
            candles.high[index - 1], candles.high[index],
            candles.low[index - 1], candles.low[index]
        ))
        self._log_skip_reason('3. There isn`t thrust')

    # INFO: shift(1)との比較だけでthrust判定したい場合はこちら
    # candles_h = candles.high
    # candles_l = candles.low
    # direction = rules.detect_thrust(
    #     trend,
    #     previous_high=candles_h[index - 1], high=candles_h[index],
    #     previous_low=candles_l[index - 1], low=candles_l[index]
    # )

    # if direction = None and self._operation == 'live':
    #     print('[Trader] Trend: {}, high-1: {}, high: {}, low-1: {}, low: {}'.format(
    #         trend, candles_h[index - 1], candles_h[index], candles_l[index - 1], candles_l[index]
    #     ))
    #     self._log_skip_reason('3. There isn`t thrust')
    # return direction
