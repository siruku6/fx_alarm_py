import os
from models.oanda_py_client import FXBase
from models.trader import Trader
import models.trade_rules.base as rules
import models.trade_rules.scalping as scalping

class RealTrader(Trader):
    ''' トレードルールに基づいてOandaへの発注を行うclass '''
    def __init__(self, operation='verification'):
        super(RealTrader, self).__init__(operation=operation)

    #
    # Public
    #
    def apply_trading_rule(self):
        self.__play_swing_trade()
        # self.__play_scalping_trade()

    #
    # Override shared methods
    #
    def _create_position(self, index, direction):
        '''
        ルールに基づいてポジションをとる(Oanda通信有)
        '''
        candles = FXBase.get_candles()
        if direction == 'long':
            sign = ''
            stoploss = candles.low[index - 1]
        elif direction == 'short':
            sign = '-'
            stoploss = candles.high[index - 1] + self._stoploss_buffer_pips
        self._client.request_market_ordering(posi_nega_sign=sign, stoploss_price=stoploss)

    def _trail_stoploss(self, new_stop, time):
        '''
        ポジションのstoploss-priceを強気方向へ修正する
        Parameters
        ----------
        new_stop : float
            新しいstoploss-price
        time : string
            不要

        Returns
        -------
        None
        '''
        result = self._client.request_trailing_stoploss(stoploss_price=new_stop)
        print(result)

    def __settle_position(self):
        ''' ポジションをcloseする '''
        from pprint import pprint
        pprint(self._client.request_closing_position())

    #
    # Private
    #
    def __play_swing_trade(self):
        ''' 現在のレートにおいて、スイングトレードルールでトレード '''
        print('[Trader] -------- start --------')
        last_index = len(self._indicators) - 1
        candles = FXBase.get_candles()
        close_price = candles.close.values[-1]
        indicators = self._indicators

        self._set_position(self.__load_position())
        if self._position['type'] == 'none':
            trend = self.__detect_latest_trend(index=last_index, c_price=close_price)
            if trend is None:
                return

            if os.environ.get('CUSTOM_RULE') == 'on':
                if not self._sma_run_along_trend(last_index, trend):
                    return
                ema60 = indicators['60EMA'][last_index]
                if not (trend == 'bull' and ema60 < close_price \
                        or trend == 'bear' and ema60 > close_price):
                    print('[Trader] c. 60EMA does not allow, c_price: {}, 60EMA: {}, trend: {}'.format(
                        close_price, ema60, trend
                    ))
                    return
                bands_gap = indicators['band_+2σ'] - indicators['band_-2σ']
                if bands_gap[last_index - 3] > bands_gap[last_index]:
                    print('[Trader] c. band is shrinking...')
                    return
                if self._over_2_sigma(last_index, price=close_price):
                    return
                if not self._expand_moving_average_gap(last_index, trend):
                    return
                if not self._stochastic_allow_trade(last_index, trend):
                    return

            direction = self._find_thrust(last_index, candles, trend)
            if direction is None:
                return

            self._create_position(last_index, direction)
        else:
            self._judge_settle_position()

        print('[Trader] -------- end --------')
        return None

    def _judge_settle_position(self, index, c_price, candles):
        parabolic = self._indicators['SAR']
        position_type = self._position['type']
        stoploss_price = self._position['stoploss']
        possible_stoploss = None

        if position_type == 'long':
            possible_stoploss = candles.low[index - 1] - self._stoploss_buffer_pips
            if possible_stoploss > stoploss_price:  # and candles.high[index - 20:index].max() < candles.high[index]:
                stoploss_price = possible_stoploss
                self._trail_stoploss(new_stop=possible_stoploss, time=candles.time[index])
            elif parabolic[index] > c_price:
                # exit_price = self._ana.calc_next_parabolic(parabolic[index - 1], candles.low[index - 1])
                self.__settle_position()

        elif position_type == 'short':
            possible_stoploss = candles.high[index - 1] + self._stoploss_buffer_pips + self._static_spread
            if possible_stoploss < stoploss_price:  # and candles.low[index - 20:index].min() > candles.low[index]:
                stoploss_price = possible_stoploss
                self._trail_stoploss(new_stop=possible_stoploss, time=candles.time[index])
            elif parabolic[index] < c_price + self._static_spread:
                # exit_price = self._ana.calc_next_parabolic(parabolic[index - 1], candles.low[index - 1])
                self.__settle_position()

        print('[Trader] position: {}, possible_SL: {}, stoploss: {}'.format(
            position_type, possible_stoploss, stoploss_price
        ))

    def __play_scalping_trade(self):
        ''' 現在のレートにおいて、scalpingルールでトレード '''
        print('[Trader] -------- start --------')
        last_index = len(self._indicators) - 1
        candles = FXBase.get_candles()
        close_price = candles.close.values[-1]
        indicators = self._indicators

        self._set_position(self.__load_position())
        if self._position['type'] == 'none':
            trend = self.__detect_latest_trend(index=last_index, c_price=close_price)
            if trend is None:
                return
            if self._over_2_sigma(last_index, price=close_price):
                return

            direction = scalping.repulsion_exist(
                trend=trend, ema=indicators['EMA'].values[-1],
                two_before_high=candles.high.values[-3], previous_high=candles.high.values[-2],
                two_before_low=candles.low.values[-3], previous_low=candles.low.values[-2]
            )
            if direction is None:
                print('[Trader] repulsion is not exist')
                return

            self._create_position(last_index, direction)
        else:
            # self._judge_settle_position(last_index, close_price, candles)
            if scalping.position_is_exitable(
                    close_price, indicators['band_+2σ'][last_index], indicators['band_-2σ'][last_index]
                ):
                self.__settle_position()

        # print('[Trader] position: {}, possible_SL: {}, stoploss: {}'.format(
        #     self._position['type'], possible_stoploss, stoploss_price
        # ))

        print('[Trader] -------- end --------')
        return None

    def __load_position(self):
        pos = {'type': 'none'}
        open_trades = self._client.request_open_trades()
        if open_trades == []:
            return pos

        # Open position の情報抽出
        target = open_trades[0]
        pos['price'] = float(target['price'])
        if target['currentUnits'][0] == '-':
            pos['type'] = 'short'
        else:
            pos['type'] = 'long'
        if 'stopLossOrder' not in target:
            return pos

        pos['stoploss'] = float(target['stopLossOrder']['price'])
        return pos

    #
    #  apply each rules
    #
    def __detect_latest_trend(self, index, c_price):
        '''
        ルールに基づいてトレンドの有無を判定
        '''
        sma = self._indicators['20SMA'][index]
        ema = self._indicators['10EMA'][index]
        parabo = self._indicators['SAR'][index]
        trend = rules.detect_trend_type(c_price, sma, ema, parabo)

        if trend is None:
            print('[Trader] 20SMA: {}, 10EMA: {}, close: {}'.format(sma, ema, c_price))
            self._log_skip_reason('2. There isn`t the trend')
        return trend

    def _stochastic_allow_trade(self, index, trend):
        ''' stocがtrendと一致した動きをしていれば true を返す '''
        stod = self._indicators['stoD:3'][index]
        stosd = self._indicators['stoSD:3'][index]

        result = rules.stoc_allows_entry(stod, stosd, trend)
        if result is False:
            print('[Trader] stoD: {}, stoSD: {}'.format(stod, stosd))
            self._log_skip_reason('c. stochastic denies trade')
        return result
