import datetime
import os
from models.oanda_py_client import FXBase
from models.trader import Trader
import models.trade_rules.base as rules
import models.trade_rules.scalping as scalping

class RealTrader(Trader):
    ''' トレードルールに基づいてOandaへの発注を行うclass '''
    def __init__(self, operation='verification'):
        print('[Trader] -------- start --------')
        self._instrument = os.environ.get('INSTRUMENT') or 'USD_JPY'
        self._static_spread = 0.0
        super(RealTrader, self).__init__(operation=operation)

    #
    # Public
    #
    def apply_trading_rule(self):
        # self.__play_swing_trade()
        self.__play_scalping_trade()

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
            stoploss = candles.low[index - 1] - self._stoploss_buffer_pips
        elif direction == 'short':
            sign = '-'
            stoploss = candles.high[index - 1] + self._stoploss_buffer_pips + self._static_spread
        self._client.request_market_ordering(posi_nega_sign=sign, stoploss_price=stoploss)

    def _trail_stoploss(self, new_stop):
        '''
        ポジションのstoploss-priceを強気方向へ修正する
        Parameters
        ----------
        new_stop : float
            新しいstoploss-price

        Returns
        -------
        None
        '''
        # INFO: trail先の価格を既に突破していたら自動でcloseしてくれた OandaAPI は優秀
        result = self._client.request_trailing_stoploss(stoploss_price=new_stop)
        print('[Trader] Trailing-result: {}'.format(result))

    def __settle_position(self, reason=''):
        ''' ポジションをcloseする '''
        from pprint import pprint
        pprint(self._client.request_closing_position(reason))

    #
    # Private
    #
    def __play_swing_trade(self):
        ''' 現在のレートにおいて、スイングトレードルールでトレード '''
        last_index = len(self._indicators) - 1
        candles = FXBase.get_candles()
        close_price = candles.close.iat[-1]
        last_time = candles.time.iat[-1]
        indicators = self._indicators

        self._set_position(self.__load_position())
        if self._position['type'] == 'none':
            trend = self.__detect_latest_trend(index=last_index, c_price=close_price, time=last_time)
            if trend is None:
                return
            elif os.environ.get('CUSTOM_RULE') == 'on':
                bands_gap = indicators['band_+2σ'] - indicators['band_-2σ']
                if not self._sma_run_along_trend(last_index, trend):
                    return
                elif bands_gap[last_index - 3] > bands_gap[last_index]:
                    print('[Trader] c. band is shrinking...')
                    return
                elif self._over_2_sigma(last_index, price=close_price):
                    return
                elif not self._expand_moving_average_gap(last_index, trend):
                    return
                elif not self._stochastic_allow_trade(last_index, trend):
                    return

            direction = self._find_thrust(last_index, candles, trend)
            if direction is None:
                return

            self._create_position(last_index, direction)
        else:
            self._judge_settle_position(last_index, close_price, candles)

        return None

    def _judge_settle_position(self, index, c_price, candles):
        parabolic = self._indicators['SAR']
        position_type = self._position['type']
        stoploss_price = self._position['stoploss']
        possible_stoploss = None

        if position_type == 'long':
            possible_stoploss = candles.low[index - 1] - self._stoploss_buffer_pips
            if possible_stoploss > stoploss_price:
                stoploss_price = possible_stoploss
                self._trail_stoploss(new_stop=possible_stoploss)
            elif parabolic[index] > c_price:
                self.__settle_position()

        elif position_type == 'short':
            possible_stoploss = candles.high[index - 1] + self._stoploss_buffer_pips + self._static_spread
            if possible_stoploss < stoploss_price:
                stoploss_price = possible_stoploss
                self._trail_stoploss(new_stop=possible_stoploss)
            elif parabolic[index] < c_price + self._static_spread:
                self.__settle_position()

        print('[Trader] position: {}, possible_SL: {}, stoploss: {}'.format(
            position_type, possible_stoploss, stoploss_price
        ))

    # TODO: 実装はいったん終わり、検証中
    def __play_scalping_trade(self):
        ''' 現在のレートにおいて、scalpingルールでトレード '''
        last_index = len(self._indicators) - 1
        candles = FXBase.get_candles()
        close_price = candles.close.iat[-1]
        last_time = candles.time.iat[-1]
        indicators = self._indicators

        self._set_position(self.__load_position())
        if self._position['type'] == 'none':
            if self.__since_last_loss() < datetime.timedelta(hours=1):
                print('[Trader] skip: An hour has not passed since last loss.')
                return
            trend = self.__detect_latest_trend(index=last_index, c_price=close_price, time=last_time)
            if trend is None:
                return
            if self._over_2_sigma(last_index, price=close_price):
                return

            direction = scalping.repulsion_exist(
                trend=trend, ema=indicators['10EMA'].values[-1],
                two_before_high=candles.high.values[-3], previous_high=candles.high.values[-2],
                two_before_low=candles.low.values[-3], previous_low=candles.low.values[-2]
            )
            if direction is None:
                print('[Trader] repulsion is not exist Time: {}, 10EMA: {}'.format(
                    last_time, indicators['10EMA'].values[-1]
                ))
                return

            self._create_position(last_index, direction)
        else:
            # INFO: stoploss設定が緩い
            # new_stop = scalping.new_stoploss_price(
            #     position_type=self._position['type'], old_stoploss=self._position['stoploss'],
            #     current_sup=indicators.at[last_index, 'support'], current_regist=indicators.at[last_index, 'regist']
            # )

            # INFO: 厳しいstoploss設定
            new_stop = rules.new_stoploss_price(
                position_type=self._position['type'],
                previous_low=candles.at[last_index - 1, 'low'],
                previous_high=candles.at[last_index - 1, 'high'],
                old_stoploss=self._position['stoploss'],
                stoploss_buf=self._stoploss_buffer_pips,
                static_spread=self._static_spread
            )
            if new_stop != self._position['stoploss']:
                self._trail_stoploss(new_stop=new_stop)

            plus_2sigma = indicators.at[last_index, 'band_+2σ']
            minus_2sigma = indicators.at[last_index, 'band_-2σ']
            if scalping.is_exitable_by_bollinger(close_price, plus_2sigma, minus_2sigma):
                self.__settle_position(reason='C is over the bands. +2s: {}, C: {}, -2s:{}'.format(
                    plus_2sigma, close_price, minus_2sigma
                ))

        print('[Trader] position: {}, possible_SL: {}, stoploss: {}'.format(
            self._position['type'], new_stop if 'new_stop' in locals() else '-', self._position.get('stoploss', None)
        ))

        return None

    def __load_position(self):
        pos = {'type': 'none'}
        open_trades = self._client.request_open_trades()
        if open_trades == []:
            return pos

        # Open position の情報抽出
        target = open_trades[0]
        pos['price'] = float(target['price'])
        pos['openTime'] = target['openTime']
        if target['currentUnits'][0] == '-':
            pos['type'] = 'short'
        else:
            pos['type'] = 'long'
        if 'stopLossOrder' not in target:
            return pos

        pos['stoploss'] = float(target['stopLossOrder']['price'])
        return pos

    def __since_last_loss(self):
        hist_df = self._client.request_transactions(100)
        time_series = hist_df[hist_df.pl < 0]['time']
        if time_series.empty: return datetime.timedelta(hours=99)

        last_loss_time = time_series.iat[-1]
        last_loss_datetime = datetime.datetime.strptime(last_loss_time.replace('T', ' ')[:16], '%Y-%m-%d %H:%M')
        time_since_loss = datetime.datetime.utcnow() - last_loss_datetime
        return time_since_loss

    #
    #  apply each rules
    #
    def __detect_latest_trend(self, index, c_price, time):
        '''
        ルールに基づいてトレンドの有無を判定
        '''
        sma = self._indicators['20SMA'][index]
        ema = self._indicators['10EMA'][index]
        parabo = self._indicators['SAR'][index]
        trend = rules.identify_trend_type(c_price, sma, ema, parabo)

        if trend is None:
            print('[Trader] Time: {}, 20SMA: {}, 10EMA: {}, close: {}'.format(
                time, round(sma, 3), round(ema, 3), c_price
            ))
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
