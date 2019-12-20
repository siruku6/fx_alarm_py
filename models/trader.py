import datetime
import math
import os
import numpy as np
import pandas as pd
from models.oanda_py_client import FXBase, OandaPyClient
from models.analyzer import Analyzer
from models.drawer import FigureDrawer
from models.mathematics import range_2nd_decimal
import models.interface as i_face
import models.statistics_module as statistics

class Trader():
    MAX_ROWS_COUNT = 200
    TIME_STRING_FMT = '%Y-%m-%d %H:%M:%S'

    def __init__(self, operation='verification'):
        if operation in ['verification']:
            inst = OandaPyClient.select_instrument()
            self.__static_options = {}
            self.__static_options['be_drawn'] = i_face.ask_true_or_false(msg='[Trader] 画像描画する？ [1]:Yes, [2]:No : ')
            self.__drawer = None
            self.__instrument = inst['name']
            self.__static_spread = inst['spread']
        else:
            self.__instrument = os.environ.get('INSTRUMENT') or 'USD_JPY'
            self.__static_spread = 0.0

        self._operation = operation
        self._client = OandaPyClient(instrument=self.get_instrument())
        self.__columns = ['sequence', 'price', 'stoploss', 'type', 'time', 'profit']
        self.__granularity = os.environ.get('GRANULARITY') or 'M5'
        self._position = None

        if operation in ['verification']:
            self._stoploss_buffer_pips = i_face.select_stoploss_digit() * 5
            self.__request_custom_candles()
        elif operation == 'live':
            result = self._client.request_is_tradeable()
            self.tradeable = result['tradeable']
            if not self.tradeable and operation != 'unittest':
                self._log_skip_reason('1. market is not open')
                return
            self._stoploss_buffer_pips = round(float(os.environ.get('STOPLOSS_BUFFER') or 0.05), 5)
            self._client.specify_count_and_load_candles(count=70, granularity=self.__granularity, set_candles=True)
        else:
            return

        self._client.request_current_price()
        self.__ana = Analyzer()
        result = self.__ana.calc_indicators()
        if 'error' in result:
            self._log_skip_reason(result['error'])
            return
        elif operation != 'live':
            print(result['success'])

        self._indicators = self.__ana.get_indicators()
        self.__initialize_position_variables()

    def __initialize_position_variables(self):
        self._set_position({'type': 'none'})
        self.__hist_positions = {'long': [], 'short': []}

    #
    # public
    #
    def get_instrument(self):
        return self.__instrument

    def auto_verify_trading_rule(self, accurize=True, rule='swing'):
        ''' tradeルールを自動検証 '''
        if self.__static_options['be_drawn']:
            self.__drawer = FigureDrawer()

        if rule == 'swing':
            result = self.__backtest_swing()
            print(result['success'])

            df_positions = result['result'].loc[:, ['time', 'position', 'entry_price', 'exitable_price']]
            statistics.aggregate_backtest_result(
                df_positions=df_positions,
                granularity=self.__granularity,
                stoploss_buffer=self._stoploss_buffer_pips,
                spread=self.__static_spread
            )
            df_positions = self.__wrangle_result_for_graph(result['result'][
                ['time', 'position', 'entry_price', 'possible_stoploss', 'exitable_price']
            ].copy())
            self.__draw_chart_vectorized_ver(df_positions)
            return df_positions
        elif rule == 'scalping':
            print(self.__backtest_scalping()['success'])

    def verify_varios_stoploss(self, accurize=True):
        ''' StopLossの設定値を自動でスライドさせて損益を検証 '''
        verification_dataframes_array = []
        stoploss_digit = i_face.select_stoploss_digit()
        stoploss_buffer_list = range_2nd_decimal(stoploss_digit, stoploss_digit * 20, stoploss_digit * 2)

        for stoploss_buf in stoploss_buffer_list:
            print('[Trader] stoploss buffer: {}pipsで検証開始...'.format(stoploss_buf))
            self._stoploss_buffer_pips = stoploss_buf
            df_positions = self.auto_verify_trading_rule(accurize=accurize)
            verification_dataframes_array.append(df_positions)

        result = pd.concat(
            verification_dataframes_array,
            axis=1, keys=stoploss_buffer_list,
            names=['SL_buffer']
        )
        result.to_csv('./tmp/csvs/sl_verify_{inst}.csv'.format(inst=self.get_instrument()))

    #
    # Methods for judging Entry or Close
    #
    def _set_position(self, position_dict):
        self._position = position_dict

    def _sma_run_along_trend(self, index, trend):
        sma = self._indicators['20SMA']
        if trend == 'bull' and sma[index - 1] < sma[index]:
            return True
        elif trend == 'bear' and sma[index - 1] > sma[index]:
            return True

        if self._operation == 'live':
            print('[Trader] Trend: {}, 20SMA: {} -> {}'.format(trend, sma[index - 1], sma[index]))
            self._log_skip_reason('c. 20SMA not run along trend')
        return False

    def _over_2_sigma(self, index, price):
        if self._indicators['band_+2σ'][index] < price or \
           self._indicators['band_-2σ'][index] > price:
            if self._operation == 'live':
                self._log_skip_reason(
                    'c. {}: price is over 2sigma'.format(FXBase.get_candles().time[index])
                )
            return True

        return False

    def _expand_moving_average_gap(self, index, trend):
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

    def __generate_trend_column(self, c_prices):
        sma = self._indicators['20SMA']
        ema = self._indicators['10EMA']
        parabo = self._indicators['SAR']
        method_trend_checker = np.frompyfunc(self.__make_sure_of_trend, 4, 1)

        trend = method_trend_checker(c_prices, sma, ema, parabo)
        bull = np.where(trend == 'bull', True, False)
        bear = np.where(trend == 'bear', True, False)
        return trend, bull, bear

    def __make_sure_of_trend(self, c_price, sma, ema, parabo):
        if sma < ema < c_price and parabo < c_price:
            return 'bull'
        elif sma > ema > c_price and parabo > c_price:
            return 'bear'
        else:
            return None

    def __generate_thrust_column(self, candles):
        # INFO: if high == the max of recent-10-candles: True is set !
        sr_highest_in_10candles = (candles.high == candles.high.rolling(window=10).max())
        sr_lowest_in_10candles = (candles.low == candles.low.rolling(window=10).min())
        sr_up_thrust = np.all(
            pd.DataFrame({'highest': sr_highest_in_10candles, 'bull': candles.bull}),
            axis=1
        )
        sr_down_thrust = np.all(
            pd.DataFrame({'lowest': sr_lowest_in_10candles, 'bear': candles.bear}),
            axis=1
        )
        method_thrust_checker = np.frompyfunc(self._detect_thrust2, 2, 1)
        result = method_thrust_checker(sr_up_thrust, sr_down_thrust)
        return result

        # INFO: shift(1)との比較のみでthrustを判定する場合
        # method_thrust_checker = np.frompyfunc(self._detect_thrust, 5, 1)
        # result = method_thrust_checker(
        #     candles.trend,
        #     candles.high.shift(1), candles.high,
        #     candles.low.shift(1), candles.low
        # )
        # return result

    def _detect_thrust(self, trend, previous_high, high, previous_low, low):
        if trend == 'bull' and not np.isnan(previous_high) and previous_high < high:
            return 'long'
        elif trend == 'bear' and not np.isnan(previous_low) and previous_low > low:
            return 'short'
        else:
            return None

    def _detect_thrust2(self, up_thrust, down_thrust):
        if up_thrust:
            return 'long'
        elif down_thrust:
            return 'short'
        else:
            return None

    def __generate_ema_allows_column(self, candles):
        ema60 = self._indicators['60EMA']
        ema60_allows_bull = np.all(np.array([candles.bull, ema60 < candles.close]), axis=0)
        ema60_allows_bear = np.all(np.array([candles.bear, ema60 > candles.close]), axis=0)
        return np.any(np.array([ema60_allows_bull, ema60_allows_bear]), axis=0)

    def __generate_in_the_band_column(self, price_series):
        ''' 2-sigma-band内にレートが収まっていることを判定するcolumnを生成 '''
        df_over_band_detection = pd.DataFrame({
            'under_positive_band': self._indicators['band_+2σ'] > price_series,
            'above_negative_band': self._indicators['band_-2σ'] < price_series
        })
        return np.all(df_over_band_detection, axis=1)

    def __generate_band_expansion_column(self, df_bands, shift_size=3):
        ''' band が拡張していれば True を格納して numpy配列 を生成 '''
        bands_gap = df_bands['band_+2σ'] - df_bands['band_-2σ']
        return bands_gap.shift(shift_size) < bands_gap

    def __generate_getting_steeper_column(self, df_trend):
        ''' 移動平均が勢いづいているか否かを判定 '''
        gap_of_ma = self._indicators['10EMA'] - self._indicators['20SMA']
        result = gap_of_ma.shift(1) < gap_of_ma

        # INFO: 上昇方向に勢いづいている
        is_long_steeper = np.all(
            pd.DataFrame({'bull': df_trend.bull, 'inclination': result}),
            axis=1
        )
        # INFO: 下降方向に勢いづいている
        is_short_steeper = np.all(
            pd.DataFrame({'bear': df_trend.bear, 'inclination': np.where(result, False, True)}),
            axis=1
        )

        # どちらかにでも勢いがついていれば True
        return np.any(
            pd.DataFrame({'l_steeper': is_long_steeper, 'sh_steeper': is_short_steeper}),
            axis=1
        )

    def __generate_following_trend_column(self, df_trend):
        ''' 移動平均線がtrendに沿う方向に動いているか判定する列を返却 '''
        df_sma = self._indicators['20SMA'].copy()
        df_tmp = df_trend.copy()
        df_tmp['sma_up'] = df_sma.shift(1) < df_sma
        df_tmp['sma_down'] = df_sma.shift(1) > df_sma

        tmp_df = pd.DataFrame({
            'both_up': np.all(df_tmp[['bull', 'sma_up']], axis=1),
            'both_down': np.all(df_tmp[['bear', 'sma_down']], axis=1)
        })
        return np.any(tmp_df, axis=1)

    def _stoc_allows_entry(self, stod, stosd, trend):
        if trend == 'bull' and (stod > stosd or stod > 80):
            return True
        elif trend == 'bear' and (stod < stosd or stod < 20):
            return True

        return False

    def __generate_stoc_allows_column(self, sr_trend):
        ''' stocがtrendに沿う値を取っているか判定する列を返却 '''
        stod = self._indicators['stoD:3']
        stosd = self._indicators['stoSD:3']
        column_generator = np.frompyfunc(self._stoc_allows_entry, 3, 1)
        return column_generator(stod, stosd, sr_trend)

    def _check_trend(self, index, c_price):
        '''
        ルールに基づいてトレンドの有無を判定
        '''
        sma = self._indicators['20SMA'][index]
        ema = self._indicators['10EMA'][index]
        parabo = self._indicators['SAR'][index]
        if sma < ema < c_price and parabo < c_price:
            trend = 'bull'
        elif sma > ema > c_price and parabo > c_price:
            trend = 'bear'
        else:
            trend = None
            if self._operation == 'live':
                print('[Trader] 20SMA: {}, 10EMA: {}, close: {}'.format(sma, ema, c_price))
                self._log_skip_reason('2. There isn`t the trend')
        return trend

    def _stochastic_allow_trade(self, index, trend):
        ''' stocがtrendと一致した動きをしていれば true を返す '''
        stod = self._indicators['stoD:3'][index]
        stosd = self._indicators['stoSD:3'][index]
        result = False

        if trend == 'bull' and (stod > stosd or stod > 80):
            result = True
        elif trend == 'bear' and (stod < stosd or stod < 20):
            result = True

        if result is False and self._operation == 'live':
            print('[Trader] stoD: {}, stoSD: {}'.format(stod, stosd))
            self._log_skip_reason('c. stochastic denies trade')
        return result

    def _find_thrust(self, index, candles, trend):
        '''
        thrust発生の有無と方向を判定して返却する
        '''
        if trend == 'bull' and candles[:index + 1].tail(10).high.idxmax() == index:
            direction = 'long'
        elif trend == 'bear' and candles[:index + 1].tail(10).low.idxmin() == index:
            direction = 'short'
        else:
            direction = None
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
        # if trend == 'bull' and candles_h[index] > candles_h[index - 1]:
        #     direction = 'long'
        # elif trend == 'bear' and candles_l[index] < candles_l[index - 1]:
        #     direction = 'short'
        # else:
        #     direction = None
        #     if self._operation == 'live':
        #         print('[Trader] Trend: {}, high-1: {}, high: {}, low-1: {}, low: {}'.format(
        #             trend, candles_h[index - 1], candles_h[index], candles_l[index - 1], candles_l[index]
        #         ))
        #         self._log_skip_reason('3. There isn`t thrust')
        return direction

    def __generate_entry_column(self, candles):
        print('[Trader] judging entryable or not ...')
        self.__judge_entryable(candles)
        self.__set_entryable_prices(candles)

        entry_direction = candles.entryable.fillna(method='ffill')
        long_direction_index = entry_direction == 'long'
        short_direction_index = entry_direction == 'short'

        self.__set_stoploss_prices(
            candles,
            long_indexes=long_direction_index,
            short_indexes=short_direction_index
        )
        self.__commit_positions(
            candles,
            long_indexes=long_direction_index,
            short_indexes=short_direction_index
        )

    def __judge_entryable(self, candles):
        ''' 各足において entry 可能かどうかを判定し、 candles dataframe に設定 '''
        satisfy_preconditions = np.all(
            candles[['in_the_band', 'ma_gap_expanding', 'sma_follow_trend', 'stoc_allows', 'ema60_allows', 'band_expansion']],
            axis=1
        )
        candles.loc[satisfy_preconditions, 'entryable'] = candles[satisfy_preconditions].thrust
        candles.loc[satisfy_preconditions, 'position'] = candles[satisfy_preconditions].thrust.copy()

    def __set_entryable_prices(self, candles):
        ''' entry した場合の price を candles dataframe に設定 '''
        # INFO: long-entry
        long_index = candles.entryable == 'long'
        long_entry_prices = pd.DataFrame({
            'previous_high': candles.shift(1)[long_index].high,
            'current_open': candles[long_index].open
        }).max(axis=1) + self.__static_spread
        candles.loc[long_index, 'entryable_price'] = long_entry_prices

        # INFO: short-entry
        short_index = candles.entryable == 'short'
        short_entry_prices = pd.DataFrame({
            'previous_low': candles.shift(1)[short_index].low,
            'current_open': candles[short_index].open
        }).min(axis=1)
        candles.loc[short_index, 'entryable_price'] = short_entry_prices

    def __set_stoploss_prices(self, candles, long_indexes, short_indexes):
        ''' trail した場合の stoploss 価格を candles dataframe に設定 '''
        # INFO: long-stoploss
        long_stoploss_prices = candles.shift(1)[long_indexes].low - self._stoploss_buffer_pips
        candles.loc[long_indexes, 'possible_stoploss'] = long_stoploss_prices

        # INFO: short-stoploss
        short_stoploss_prices = candles.shift(1)[short_indexes].high \
                              + self._stoploss_buffer_pips \
                              + self.__static_spread
        candles.loc[short_indexes, 'possible_stoploss'] = short_stoploss_prices

    def __commit_positions(self, candles, long_indexes, short_indexes):
        ''' set exit-timing, price '''
        long_exits = np.all(np.array([
            long_indexes, candles.low < candles.possible_stoploss
        ]), axis=0)
        candles.loc[long_exits, 'position'] = 'sell_exit'
        candles.loc[long_exits, 'exitable_price'] = candles[long_exits].possible_stoploss

        short_exits = np.all(np.array([
            short_indexes, candles.high + self.__static_spread > candles.possible_stoploss
        ]), axis=0)
        candles.loc[short_exits, 'position'] = 'buy_exit'
        candles.loc[short_exits, 'exitable_price'] = candles[short_exits].possible_stoploss

        # INFO: position column の整理
        candles.position.fillna(method='ffill', inplace=True)
        position_ser = candles.position
        candles.loc[:, 'position'] = np.where(position_ser == position_ser.shift(1), None, position_ser)

        # INFO: entry したその足で exit した足があった場合、この処理が必須
        short_life_entries = np.all(np.vstack(
            (candles.entryable_price.notna(), candles.exitable_price.notna())
        ).transpose(), axis=1)
        candles.loc[short_life_entries, 'position'] = candles.entryable

    def _judge_settle_position(self, index, c_price, candles):
        parabolic = self._indicators['SAR']
        position_type = self._position['type']
        stoploss_price = self._position['stoploss']

        if position_type == 'long':
            possible_stoploss = candles.low[index - 1] - self._stoploss_buffer_pips
            # if self._operation == 'live':
            print('[Trader] position: {}, possible_SL: {}, stoploss: {}, (SL) possible < current: {}'.format(
                position_type,
                possible_stoploss,
                stoploss_price,
                possible_stoploss < stoploss_price
            ))

            # INFO: trailing
            if possible_stoploss > stoploss_price:  # and candles.high[index - 20:index].max() < candles.high[index]:
                stoploss_price = possible_stoploss
                self._trail_stoploss(
                    new_stop=stoploss_price, time=candles.time[index]
                )
            # # INFO: 本番ではstoplossで決済されるので不要
            # if self._operation != 'live' and stoploss_price > candles.low[index]:
            #     self._settle_position(
            #         index=index, price=stoploss_price, time=candles.time[index]
            #     )
            elif parabolic[index] > c_price:
                exit_price = self.__ana.calc_next_parabolic(parabolic[index - 1], candles.low[index - 1])
                self._settle_position(
                    index=index, price=exit_price, time=candles.time[index]
                )
        elif position_type == 'short':
            possible_stoploss = candles.high[index - 1] + self._stoploss_buffer_pips + self.__static_spread
            # if self._operation == 'live':
            print('[Trader] position: {}, possible_SL: {}, stoploss: {}, (SL) possible < current: {}'.format(
                position_type,
                possible_stoploss,
                stoploss_price,
                possible_stoploss < stoploss_price
            ))

            # INFO: trailing
            if possible_stoploss < stoploss_price:  # and candles.low[index - 20:index].min() > candles.low[index]:
                stoploss_price = possible_stoploss
                self._trail_stoploss(
                    new_stop=stoploss_price, time=candles.time[index]
                )
            # # INFO: 本番ではstoplossで決済されるので不要
            # if self._operation != 'live' and stoploss_price < candles.high[index] + self.__static_spread:
            #     self._settle_position(
            #         index=index, price=stoploss_price, time=candles.time[index]
            #     )
            elif parabolic[index] < c_price + self.__static_spread:
                exit_price = self.__ana.calc_next_parabolic(parabolic[index - 1], candles.low[index - 1])
                self._settle_position(
                    index=index, price=exit_price, time=candles.time[index]
                )

    #
    # private
    #

    def __request_custom_candles(self):
        # Custom request
        days = i_face.ask_number(msg='何日分のデータを取得する？(半角数字): ', limit=365)

        while True:
            print('取得スパンは？(ex: M5): ', end='')
            self.__granularity = str(input())
            if self.__granularity[0] in 'MH' and self.__granularity[1:].isdecimal():
                break
            elif self.__granularity[0] in 'DW':
                break
            else:
                print('Invalid granularity !\n')

        result = self._client.load_long_chart(days=days, granularity=self.__granularity)
        if 'error' in result:
            print(result['error'])
            exit()
        FXBase.set_candles(result['candles'])

    def __backtest_swing(self):
        ''' スイングトレードのentry pointを検出 '''
        # INFO: 繰り返しデモする場合に前回のpositionが残っているので、リセットする
        self.__initialize_position_variables()

        candles = FXBase.get_candles().copy()
        self.__prepare_trade_signs(candles)
        self.__slide_prices_to_really_possible(candles=candles)
        return {'success': '[Trader] 売買判定終了', 'result': candles}

    def __slide_prices_to_really_possible(self, candles):
        print('[Trader] start sliding ...')
        first_time = self.__str_to_datetime(candles.iloc[0, 4][:19])
        last_time = self.__str_to_datetime(candles.iloc[-1, 4][:19])
        # INFO: 実は、candlesのlastrow分のm10candlesがない
        m10_candles = self._client.load_or_query_candles(first_time, last_time, granularity='M10')[['high', 'low']]
        m10_candles['time'] = m10_candles.index
        spread = self.__static_spread

        position_index = candles.position.isin(['long', 'short'])
        position_rows = candles[position_index][[
            'time', 'entryable_price', 'position'
        ]].to_dict('records')
        len_of_rows = len(position_rows)
        for i, row in enumerate(position_rows):
            print('[Trader] sliding price .. {}/{}'.format(i + 1, len_of_rows))
            start = row['time']
            end = self.__add_candle_duration(start[:19])
            candles_in_granularity = m10_candles.loc[start:end, :].to_dict('records')

            if row['position'] == 'long':
                for m10_candle in candles_in_granularity:
                    if row['entryable_price'] < m10_candle['high'] + spread:
                        row['price'] = m10_candle['high'] + spread
                        row['time'] = m10_candle['time']
                        break
                # INFO: 今のところ必要なさそう
                # if not 'price' in row:
                #     row['price'] = row['entryable_price']
            elif row['position'] == 'short':
                for m10_candle in candles_in_granularity:
                    if row['entryable_price'] > m10_candle['low']:
                        row['price'] = m10_candle['low']
                        row['time'] = m10_candle['time']
                        break

        slided_positions = pd.DataFrame.from_dict(position_rows)
        # TODO: price 列がないときにエラーになる（なぜかprice列がないことがある...candlesが異様に短いときに発生した）
        candles.loc[position_index, 'entry_price'] = slided_positions.price.to_numpy(copy=True)
        candles.loc[position_index, 'time'] = slided_positions.time.astype(str).to_numpy(copy=True)

        print('[Trader] finished sliding !')

    def __backtest_scalping(self):
        ''' スキャルピングのentry pointを検出 '''
        self.__initialize_position_variables()

        candles = FXBase.get_candles().copy()
        self.__prepare_trade_signs(candles)
        close_candles = candles.close.values.tolist()
        return {'success': candles}

    def __prepare_trade_signs(self, candles):
        print('[Trader] preparing base-data for judging ...')

        indicators = self._indicators
        candles['trend'], candles['bull'], candles['bear'] \
            = self.__generate_trend_column(c_prices=candles.close)
        candles['thrust'] = self.__generate_thrust_column(candles=candles)
        candles['ema60_allows'] = self.__generate_ema_allows_column(candles=candles)
        candles['in_the_band'] = self.__generate_in_the_band_column(price_series=candles.open)
        candles['band_expansion'] =  self.__generate_band_expansion_column(
            df_bands=indicators[['band_+2σ', 'band_-2σ']]
        )
        candles['ma_gap_expanding'] = self.__generate_getting_steeper_column(df_trend=candles[['bull', 'bear']])
        candles['sma_follow_trend'] = self.__generate_following_trend_column(df_trend=candles[['bull', 'bear']])
        candles['stoc_allows'] = self.__generate_stoc_allows_column(sr_trend=candles['trend'])
        self.__generate_entry_column(candles=candles)
        candles.to_csv('./tmp/csvs/full_data_dump.csv')

    def __draw_chart_vectorized_ver(self, df_positions):
        drwr = self.__drawer
        if drwr is None: return

        filename_postfix = datetime.datetime.strftime(datetime.datetime.now(), '%Y%m%d_%H%M%S')
        df_len = len(df_positions)
        dfs_indicator = self.__split_df_by_200rows(self._indicators)
        dfs_position = self.__split_df_by_200sequences(df_positions, df_len)

        df_segments_count = len(dfs_indicator)
        for i in range(0, df_segments_count):
            # indicators
            drwr.draw_indicators(d_frame=dfs_indicator[i])

            # positions
            long_entry_df = dfs_position[i][dfs_position[i].position == 'long']
            close_df = dfs_position[i][
                (dfs_position[i].position.isin(['long', 'short', 'sell_exit', 'buy_exit'])) \
                & (~dfs_position[i].exitable_price.isna())
            ].drop('price', axis=1).rename(columns={'exitable_price': 'price'})
            short_entry_df = dfs_position[i][dfs_position[i].position == 'short']
            trail_df = dfs_position[i][dfs_position[i].position != '-']

            drwr.draw_positions_df(positions_df=long_entry_df, plot_type=drwr.PLOT_TYPE['long'])
            drwr.draw_positions_df(positions_df=short_entry_df, plot_type=drwr.PLOT_TYPE['short'])
            drwr.draw_positions_df(positions_df=close_df, plot_type=drwr.PLOT_TYPE['exit'])
            # drwr.draw_positions_df(positions_df=short_close_df, plot_type=drwr.PLOT_TYPE['exit'], nolabel='_nolegend_')
            drwr.draw_positions_df(positions_df=trail_df, plot_type=drwr.PLOT_TYPE['trail'])

            drwr.draw_vertical_lines(
                indexes=np.concatenate(
                    [long_entry_df.sequence.values, short_entry_df.sequence.values]
                ),
                vmin=dfs_indicator[i]['band_-2σ'].min(skipna=True),
                vmax=dfs_indicator[i]['band_+2σ'].max(skipna=True)
            )

            # candles
            start = df_len - Trader.MAX_ROWS_COUNT * (i + 1)
            if start < 0: start = 0
            end = df_len - Trader.MAX_ROWS_COUNT * i
            sr_time = drwr.draw_candles(start, end)['time']

            result = drwr.create_png(
                instrument='sample', # self.get_instrument(),
                granularity=self.__granularity,
                sr_time=sr_time, num=i
            )

            drwr.close_all()
            if df_segments_count != i + 1:
                drwr.init_figure()
            if 'success' in result:
                print('{msg} / {count}'.format(msg=result['success'], count=df_segments_count))

    def __wrangle_result_for_graph(self, result):
        positions_df = result.rename(columns={'entry_price': 'price', 'possible_stoploss': 'stoploss'})
        positions_df['sequence'] = positions_df.index
        # INFO: exit直後のrowで、かつposition列が空
        positions_df.loc[
            ((positions_df.shift(1).position.isin(['sell_exit', 'buy_exit'])) \
            | ((positions_df.shift(1).position.isin(['long', 'short'])) \
            & (~positions_df.shift(1).exitable_price.isna()))) \
            & (positions_df.position.isna()), 'position'
        ] = '-'
        # INFO: entry直後のrowで、かつexit-rowではない
        positions_df.loc[
            (positions_df.shift(1).position.isin(['long', 'short'])) \
            & (positions_df.shift(1).exitable_price.isna()) \
            & (~positions_df.position.isin(['sell_exit', 'buy_exit'])),'position'
        ] = '|'
        positions_df.position.fillna(method='ffill', inplace=True)

        return positions_df

    # def _create_position(self, index, direction, candles):
    #     '''
    #     ルールに基づいてポジションをとる(検証用)
    #     '''
    #     entry_price, stoploss = self.__decide_entry_price(
    #         direction=direction,
    #         previous_high=candles.high[index - 1],
    #         previous_low=candles.low[index - 1],
    #         current_open=candles.open[index],
    #         current_60ema=self._indicators['60EMA'][index]
    #     )
    #     self._set_position({
    #         'sequence': index, 'price': entry_price, 'stoploss': stoploss,
    #         'type': direction, 'time': candles.time[index]
    #     })
    #     self.__hist_positions[direction].append(self._position.copy())

    def __decide_entry_price(self, direction, previous_high, previous_low, current_open, current_60ema):
        custom_rule_on = os.environ.get('CUSTOM_RULE') == 'on'
        if direction == 'long':
            if custom_rule_on:
                entry_price = max(previous_high, current_open + self.__static_spread, current_60ema)
            else:
                entry_price = max(previous_high, current_open + self.__static_spread)
            stoploss = previous_low - self._stoploss_buffer_pips
        elif direction == 'short':
            if custom_rule_on:
                entry_price = min(previous_low, current_open, current_60ema)
            else:
                entry_price = min(previous_low, current_open)
            stoploss = previous_high + self._stoploss_buffer_pips + self.__static_spread
        return entry_price, stoploss

    def _trail_stoploss(self, new_stop, time):
        direction = self._position['type']
        self._position['stoploss'] = new_stop
        position_after_trailing = self._position.copy()
        position_after_trailing['type'] = 'trail'
        position_after_trailing['time'] = time
        self.__hist_positions[direction].append(position_after_trailing)

    def _settle_position(self, index, price, time):
        '''
        ポジション解消の履歴を残す

        Parameters
        ----------
        index : int
            ポジションを解消するタイミングを表す
        price : float
            ポジション解消時の価格
        time : string
            ポジションを解消する日（時）

        Returns
        -------
        None
        '''
        direction = self._position['type']
        self._set_position({'type': 'none'})
        self.__hist_positions[direction].append({
            'sequence': index, 'price': price,
            'stoploss': 0.0, 'type': 'close', 'time': time
        })

    def _log_skip_reason(self, reason):
        print('[Trader] skip: {}'.format(reason))
        print('[Trader] -------- end --------')

    def __add_candle_duration(self, start_string):
        start_time = self.__str_to_datetime(start_string)
        granularity = self.__granularity
        time_unit = granularity[0]
        if time_unit == 'M':
            candle_duration = datetime.timedelta(minutes=int(granularity[1:]))
        elif time_unit == 'H':
            candle_duration = datetime.timedelta(hours=int(granularity[1:]))
        elif time_unit == 'D':
            candle_duration = datetime.timedelta(days=1)

        a_minute = datetime.timedelta(minutes=1)
        result = (start_time + candle_duration - a_minute).strftime(Trader.TIME_STRING_FMT)
        return result

    def __str_to_datetime(self, time_string):
        result_dt = datetime.datetime.strptime(time_string, Trader.TIME_STRING_FMT)
        return result_dt

    def __split_df_by_200rows(self, d_frame):
        dfs = []
        df_len = len(d_frame)
        loop = 0

        while Trader.MAX_ROWS_COUNT * loop < df_len:
            end = df_len - Trader.MAX_ROWS_COUNT * loop
            loop += 1
            start = df_len - Trader.MAX_ROWS_COUNT * loop
            start = start if start > 0 else 0
            dfs.append(d_frame[start:end].reset_index(drop=True))
        return dfs

    def __split_df_by_200sequences(self, d_frame, df_len):
        dfs = []
        loop = 0

        while Trader.MAX_ROWS_COUNT * loop < df_len:
            end = df_len - Trader.MAX_ROWS_COUNT * loop
            loop += 1
            start = df_len - Trader.MAX_ROWS_COUNT * loop
            start = start if start > 0 else 0
            df_target = d_frame[(start <= d_frame.sequence) & (d_frame.sequence < end)].copy()
            # 描画は sequence に基づいて行われるので、ずらしておく
            df_target['sequence'] = df_target.sequence - start
            dfs.append(df_target)
        return dfs


class RealTrader(Trader):
    ''' トレードルールに基づいてOandaへの発注を行うclass '''
    def __init__(self, operation='verification'):
        super(RealTrader, self).__init__(operation=operation)

    #
    # Public
    #
    def apply_trading_rule(self):
        self.__play_swing_trade()

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

    def _settle_position(self, index, price, time):
        '''
        ポジションをcloseする

        Parameters
        ----------
        index : int
        price : float
        time : string
            全て不要

        Returns
        -------
        None
        '''
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
            trend = self._check_trend(index=last_index, c_price=close_price)
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
            self._judge_settle_position(last_index, close_price, candles)

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
