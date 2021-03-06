import datetime
import os
from pprint import pprint
import numpy as np

from models.candle_storage import FXBase
from models.trader import Trader
# import models.trade_rules.base as rules
import models.trade_rules.scalping as scalping


class RealTrader(Trader):
    ''' トレードルールに基づいてOandaへの発注を行うclass '''
    def __init__(self, operation):
        print('[Trader] -------- start --------')
        self._instrument = os.environ.get('INSTRUMENT') or 'USD_JPY'
        self._static_spread = 0.0
        self._stoploss_buffer_pips = round(float(os.environ.get('STOPLOSS_BUFFER') or 0.05), 5)

        super(RealTrader, self).__init__(operation=operation, days=60)

    #
    # Public
    #
    def apply_trading_rule(self):
        candles = FXBase.get_candles().copy()
        self._prepare_trade_signs(candles)
        candles['preconditions_allows'] = np.all(candles[self.get_entry_rules('entry_filter')], axis=1)
        candles = self._merge_long_indicators(candles)
        # self.__play_swing_trade(candles)
        self.__play_scalping_trade(candles)

    #
    # Override shared methods
    #
    def _create_position(self, previous_candle, direction, last_indicators=None):
        '''
        ルールに基づいてポジションをとる(Oanda通信有)
        '''
        if direction == 'long':
            sign = ''
            stoploss = previous_candle['low'] - self._stoploss_buffer_pips
            if last_indicators is not None:
                stoploss = last_indicators['support']
        elif direction == 'short':
            sign = '-'
            stoploss = self.__stoploss_in_short(previous_high=previous_candle['high'])
            if last_indicators is not None:
                stoploss = last_indicators['regist']

        self._client.order_oanda(method_type='entry', posi_nega_sign=sign, stoploss_price=stoploss)

    def __stoploss_in_short(self, previous_high):
        return previous_high + self._stoploss_buffer_pips + self._static_spread

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
        result = self._client.order_oanda(method_type='trail', stoploss_price=new_stop)
        print('[Trader] Trailing-result: {}'.format(result))

    def __settle_position(self, reason=''):
        ''' ポジションをcloseする '''
        pprint(self._client.order_oanda(method_type='exit', reason=reason))

    #
    # Private
    #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    #                       Swing
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def __play_swing_trade(self, candles):
        ''' 現在のレートにおいて、スイングトレードルールでトレード '''
        last_index = len(self._indicators) - 1
        last_candle = candles.iloc[-1, :]

        self._set_position(self.__load_position())
        if self._position['type'] == 'none':
            entry_rules = [
                'sma_follow_trend', 'band_expansion', 'in_the_band',
                'ma_gap_expanding', 'stoc_allows'
            ]
            self.set_entry_rules('entry_filter', value=entry_rules)
            precondition = np.all(candles[entry_rules], axis=1).iloc[-1]
            if last_candle['trend'] is None or not precondition:
                self.__show_why_not_entry(candles)
                return

            direction = last_candle['thrust']
            if direction is None:
                return

            self._create_position(candles.iloc[-2], direction)
        else:
            self._judge_settle_position(last_index, last_candle.close, candles)

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
            possible_stoploss = self.__stoploss_in_short(previous_high=candles.high[index - 1])
            if possible_stoploss < stoploss_price:
                stoploss_price = possible_stoploss
                self._trail_stoploss(new_stop=possible_stoploss)
            elif parabolic[index] < c_price + self._static_spread:
                self.__settle_position()

        print('[Trader] position: {}, possible_SL: {}, stoploss: {}'.format(
            position_type, possible_stoploss, stoploss_price
        ))

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    #                       Scalping
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def __play_scalping_trade(self, candles):
        ''' 現在のレートにおいて、scalpingルールでトレード '''
        indicators = self._indicators
        last_candle = candles.iloc[-1]
        last_indicators = indicators.iloc[-1]

        self._set_position(self.__load_position())

        if self._position['type'] == 'none':
            self.__drive_entry_process(candles, last_candle, indicators, last_indicators)
        else:
            new_stop = self.__drive_trail_process(candles, last_indicators)
            self.__drive_exit_process(self._position['type'], indicators, last_candle)

        print('[Trader] position: {}, possible_SL: {}, stoploss: {}'.format(
            self._position['type'], new_stop if 'new_stop' in locals() else '-', self._position.get('stoploss', None)
        ))
        return None

    def __drive_entry_process(self, candles, last_candle, indicators, last_indicators):
        if self.__since_last_loss() < datetime.timedelta(hours=1):
            print('[Trader] skip: An hour has not passed since last loss.')
            return False
        elif not candles['preconditions_allows'].iat[-1] or last_candle.trend is None:
            self.__show_why_not_entry(candles)
            return False

        direction = scalping.repulsion_exist(
            trend=last_candle.trend, previous_ema=indicators['10EMA'].iat[-2],
            two_before_high=candles.high.iat[-3], previous_high=candles.high.iat[-2],
            two_before_low=candles.low.iat[-3], previous_low=candles.low.iat[-2]
        )
        if direction is None:
            print('[Trader] repulsion is not exist Time: {}, 10EMA: {}'.format(
                last_candle.time, last_indicators['10EMA']
            ))
            return False
        # INFO: exitサインが出ているときにエントリーさせない場合はコメントインする
        # if self.__drive_exit_process(direction, last_indicators, last_candle, preliminary=True):
        #     return False

        # last_index = len(indicators) - 1
        self._create_position(candles.iloc[-2], direction, last_indicators)
        return direction

    def __drive_trail_process(self, candles, last_indicators):
        # # INFO: 1.厳しいstoploss設定: is_exitable_by_bollinger 用
        # new_stop = rules.new_stoploss_price(
        #     position_type=self._position['type'],
        #     previous_low=candles.at[last_index - 1, 'low'],
        #     previous_high=candles.at[last_index - 1, 'high'],
        #     old_stoploss=self._position.get('stoploss', np.nan),
        #     stoploss_buf=self._stoploss_buffer_pips,
        #     static_spread=self._static_spread
        # )
        # INFO: 2. 緩いstoploss設定: exitable_by_stoccross 用
        new_stop = scalping.new_stoploss_price(
            position_type=self._position['type'], old_stoploss=self._position.get('stoploss', np.nan),
            current_sup=last_indicators['support'], current_regist=last_indicators['regist']
        )
        if new_stop != self._position.get('stoploss', np.nan) and new_stop is not np.nan:
            self._trail_stoploss(new_stop=new_stop)

        return new_stop

    def __drive_exit_process(self, position_type, indicators, last_candle, preliminary=False):
        # plus_2sigma = last_indicators['sigma*2_band']
        # minus_2sigma = last_indicators['sigma*-2_band']
        # if scalping.is_exitable_by_bollinger(last_candle.close, plus_2sigma, minus_2sigma):

        current_indicator = indicators.iloc[-1].copy()
        current_indicator['stoD_over_stoSD'] = last_candle['stoD_over_stoSD']
        previous_indicator = indicators.iloc[-2]

        # stod_over_stosd_on_long = last_candle['stoD_over_stoSD']
        if scalping.drive_exitable_judge_with_stocs(position_type, current_indicator, previous_indicator):
            # if scalping.exitable_by_long_stoccross(position_type, stod_over_stosd_on_long) \
            #         and scalping.exitable_by_stoccross(
            #             position_type, previous_indicator['stoD_3'], previous_indicator['stoSD_3']
            #         ):
            if preliminary: return True

            reason = 'stoc crossed at {} ! position_type: {}'.format(last_candle['time'], position_type)
            self.__settle_position(reason=reason)

    def __load_position(self):
        pos = {'type': 'none'}
        open_trades = self._client.call_oanda('open_trades')
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
        '''
        最も最近の損失からの経過時間を返す

        Parameters
        ----------
        None

        Returns
        -------
        time_since_loss : datetime
        '''
        candle_size = 100
        hist_df = self._client.call_oanda('transactions', count=candle_size)
        time_series = hist_df[hist_df.pl < 0]['time']
        if time_series.empty:
            return datetime.timedelta(hours=99)

        last_loss_time = time_series.iat[-1]
        last_loss_datetime = datetime.datetime.strptime(last_loss_time.replace('T', ' ')[:16], '%Y-%m-%d %H:%M')
        time_since_loss = datetime.datetime.utcnow() - last_loss_datetime
        return time_since_loss

    def __show_why_not_entry(self, conditions_df):
        time = conditions_df.time.values[-1]
        if conditions_df.trend.iat[-1] is None:
            self._log_skip_reason('c. {}: "trend" is None !'.format(time))

        columns = self.get_entry_rules('entry_filter')
        vals = conditions_df[columns].iloc[-1].values
        for reason, val in zip(columns, vals):
            if not val:
                self._log_skip_reason('c. {}: "{}" is not satisfied !'.format(time, reason))
