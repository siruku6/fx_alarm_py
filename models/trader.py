import datetime
import os
import numpy as np
import pandas as pd
from models.oanda_py_client import FXBase, OandaPyClient
from models.analyzer import Analyzer
from models.drawer import FigureDrawer
from models.mathematics import range_2nd_decimal
import models.trade_rules.base as rules
import models.trade_rules.wait_close as wait_close
import models.trade_rules.scalping as scalping
import models.interface as i_face
import models.statistics_module as statistics

# pd.set_option('display.max_rows', 400)


class Trader():
    MAX_ROWS_COUNT = 200
    TIME_STRING_FMT = '%Y-%m-%d %H:%M:%S'

    def __init__(self, operation='verification'):
        if operation in ['verification']:
            result = OandaPyClient.select_instrument()
            self._instrument = result[0]
            self._static_spread = result[1]['spread']
            self.__set_drawing_option()

        self._operation = operation
        self._client = OandaPyClient(instrument=self.get_instrument())
        self._entry_rules = {
            'granularity': os.environ.get('GRANULARITY') or 'M5',
            'entry_filter': []
        }
        # TODO: 暫定でこれを使うことを推奨(コメントアウトすればdefault設定に戻る)
        self.set_entry_filter(['in_the_band', 'stoc_allows', 'band_expansion'])  # かなりhigh performance
        self._position = None

        if operation in ['verification']:
            self._stoploss_buffer_pips = i_face.select_stoploss_digit() * 5
            self.__request_custom_candles()

            time_series = FXBase.get_candles().time
            first_time = self.__str_to_datetime(time_series.iat[0][:19])
            last_time = self.__str_to_datetime(time_series.iat[-1][:19])
            # INFO: 実は、candlesのlastrow分のm10candlesがない
            self.__m10_candles = self._client.load_or_query_candles(first_time, last_time, granularity='M10')[['high', 'low']]
        elif operation in ['live', 'forward_test']:
            result = self._client.request_is_tradeable()
            self.tradeable = result['tradeable']
            if not self.tradeable and operation != 'unittest' and operation == 'live':
                return
            self._stoploss_buffer_pips = round(float(os.environ.get('STOPLOSS_BUFFER') or 0.05), 5)
            self._client.specify_count_and_load_candles(count=70, granularity=self.get_granularity(), set_candles=True)
        else:
            return

        self._client.request_current_price()
        self._ana = Analyzer()
        result = self._ana.calc_indicators(candles=FXBase.get_candles())
        if 'error' in result:
            self._log_skip_reason(result['error'])
            return
        elif operation != 'live':
            print(result['success'])

        self._indicators = self._ana.get_indicators()
        self.__initialize_position_variables()

    def __set_drawing_option(self):
        self.__static_options = {}
        self.__static_options['figure_option'] = i_face.ask_number(
            msg='[Trader] 画像描画する？ [1]: No, [2]: Yes, [3]: with_P/L ', limit=3
        )
        self.__drawer = None

    def __initialize_position_variables(self):
        self._set_position({'type': 'none'})
        self.__hist_positions = {'long': [], 'short': []}

    #
    # getter & setter
    #
    def set_entry_filter(self, entry_filter):
        self._entry_rules['entry_filter'] = entry_filter

    def get_instrument(self):
        return self._instrument

    def get_granularity(self):
        return self._entry_rules['granularity']

    def get_entry_filter(self):
        return self._entry_rules['entry_filter']

    #
    # public
    #
    # TODO: 作成中の処理
    def verify_various_entry_filters(self, rule):
        ''' entry_filterの全パターンを検証する '''
        filters = [[]]
        filter_elements = statistics.FILTER_ELEMENTS
        for elem in filter_elements:
            tmp_filters = filters.copy()
            for tmp_filter in tmp_filters:
                filter_copy = tmp_filter.copy()
                filter_copy.append(elem)
                filters.append(filter_copy)

        filters.sort()
        for _filter in filters:
            print('[Trader] ** Now trying filter -> {} **', _filter)
            self.set_entry_filter(_filter)
            self.verify_various_stoploss(rule=rule)

    def verify_various_stoploss(self, rule):
        ''' StopLossの設定値を自動でスライドさせて損益を検証 '''
        verification_dataframes_array = []
        stoploss_digit = i_face.select_stoploss_digit()
        stoploss_buffer_list = range_2nd_decimal(stoploss_digit, stoploss_digit * 20, stoploss_digit * 2)

        for stoploss_buf in stoploss_buffer_list:
            print('[Trader] stoploss buffer: {}pipsで検証開始...'.format(stoploss_buf))
            self._stoploss_buffer_pips = stoploss_buf
            df_positions = self.auto_verify_trading_rule(rule=rule)
            verification_dataframes_array.append(df_positions)

        result = pd.concat(
            verification_dataframes_array,
            axis=1, keys=stoploss_buffer_list,
            names=['SL_buffer']
        )
        result.to_csv('./tmp/csvs/sl_verify_{inst}.csv'.format(inst=self.get_instrument()))

    def auto_verify_trading_rule(self, rule='swing'):
        ''' tradeルールを自動検証 '''
        if self.__static_options['figure_option'] > 1:
            self.__drawer = FigureDrawer(rows_num=self.__static_options['figure_option'])

        candles = FXBase.get_candles().copy()
        self._prepare_trade_signs(candles)
        if rule == 'swing':
            if self.get_entry_filter() == []:
                self.set_entry_filter(statistics.FILTER_ELEMENTS)
            result = self.__backtest_swing(candles)
        elif rule == 'wait_close':
            if self.get_entry_filter() == []:
                self.set_entry_filter(['in_the_band'])
            result = self.__backtest_wait_close(candles)
        elif rule == 'scalping':
            if self.get_entry_filter() == []:
                self.set_entry_filter(['in_the_band'])
            result = self.__backtest_scalping(candles)
        else:
            print('Rule {} is not exist ...'.format(rule))
            exit()

        print('{} ... (auto_verify_trading_rule)'.format(result['result']))
        positions_columns = ['time', 'position', 'entry_price', 'exitable_price']
        if result['result'] == 'no position':
            return pd.DataFrame([], columns=positions_columns)

        df_positions = result['candles'].loc[:, positions_columns]
        pl_gross_df = statistics.aggregate_backtest_result(
            rule=rule,
            df_positions=df_positions,
            granularity=self.get_granularity(),
            stoploss_buffer=self._stoploss_buffer_pips,
            spread=self._static_spread,
            entry_filter=self.get_entry_filter()
        )
        df_positions = self.__wrangle_result_for_graph(result['candles'][
            ['time', 'position', 'entry_price', 'possible_stoploss', 'exitable_price']
        ].copy())
        df_positions = pd.merge(df_positions, pl_gross_df, on='time', how='left')
        df_positions['gross'].fillna(method='ffill', inplace=True)

        self.__draw_chart_vectorized_ver(df_positions=df_positions)
        return df_positions

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
        method_trend_checker = np.frompyfunc(rules.identify_trend_type, 4, 1)

        trend = method_trend_checker(c_prices, sma, ema, parabo)
        bull = np.where(trend == 'bull', True, False)
        bear = np.where(trend == 'bear', True, False)
        return trend, bull, bear

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
        # method_thrust_checker = np.frompyfunc(rules.detect_thrust, 5, 1)
        # result = method_thrust_checker(
        #     candles.trend,
        #     candles.high.shift(1), candles.high,
        #     candles.low.shift(1), candles.low
        # )
        # return result

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

    def __generate_stoc_allows_column(self, sr_trend):
        ''' stocがtrendに沿う値を取っているか判定する列を返却 '''
        stod = self._indicators['stoD_3']
        stosd = self._indicators['stoSD_3']
        column_generator = np.frompyfunc(rules.stoc_allows_entry, 3, 1)
        return column_generator(stod, stosd, sr_trend)

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
        return direction

    #
    # private
    #

    def __request_custom_candles(self):
        # Custom request
        days = i_face.ask_number(msg='何日分のデータを取得する？(半角数字): ', limit=365)

        while True:
            print('取得スパンは？(ex: M5): ', end='')
            granularity = str(input())
            self._entry_rules['granularity'] = granularity
            if granularity[0] in 'MH' and granularity[1:].isdecimal():
                break
            elif granularity[0] in 'DW':
                break
            else:
                print('Invalid granularity !\n')

        result = self._client.load_long_chart(days=days, granularity=granularity)
        if 'error' in result:
            print(result['error'])
            exit()
        FXBase.set_candles(result['candles'])

    def __backtest_swing(self, candles):
        ''' スイングトレードのentry pointを検出 '''
        # INFO: 繰り返しデモする場合に前回のpositionが残っているので、リセットする いらなくない？
        self.__initialize_position_variables()

        self.__generate_entry_column(candles=candles)
        sliding_result = self.__slide_prices_to_really_possible(candles=candles)
        candles.to_csv('./tmp/csvs/full_data_dump.csv')

        result = 'no position' if sliding_result['result'] == 'no position' else '[Trader] 売買判定終了'
        return {'result': result, 'candles': candles}

    def __backtest_wait_close(self, candles):
        ''' swingでH4 close直後のみにentryする場合のentry pointを検出 '''
        candles['thrust'] = wait_close.generate_thrust_column(candles)
        self.__generate_entry_column_for_wait_close(candles)
        sliding_result = self.__slide_prices_to_really_possible(candles=candles)
        candles.to_csv('./tmp/csvs/wait_close_data_dump.csv')

        result = 'no position' if sliding_result['result'] == 'no position' else '[Trader] 売買判定終了'
        return {'result': result, 'candles': candles}

    def __backtest_scalping(self, candles):
        ''' スキャルピングのentry pointを検出 '''
        candles['thrust'] = scalping.generate_repulsion_column(candles, ema=self._indicators['10EMA'])
        entryable = np.all(candles[self.get_entry_filter()], axis=1)
        candles.loc[entryable, 'entryable'] = candles[entryable].thrust

        self.__generate_entry_column_for_scalping(candles)

        candles.to_csv('./tmp/csvs/scalping_data_dump.csv')
        return {'result': '[Trader] 売買判定終了', 'candles': candles}

    def _prepare_trade_signs(self, candles):
        print('[Trader] preparing base-data for judging ...')

        if self._operation in ['live', 'forward_test']:
            comparison_prices_with_bands = candles.close
        else:
            comparison_prices_with_bands = candles.open

        indicators = self._indicators
        candles['trend'], candles['bull'], candles['bear'] \
            = self.__generate_trend_column(c_prices=candles.close)
        candles['thrust'] = self.__generate_thrust_column(candles=candles)
        candles['ema60_allows'] = self.__generate_ema_allows_column(candles=candles)
        candles['in_the_band'] = self.__generate_in_the_band_column(price_series=comparison_prices_with_bands)
        candles['band_expansion'] = self.__generate_band_expansion_column(
            df_bands=indicators[['band_+2σ', 'band_-2σ']]
        )
        candles['ma_gap_expanding'] = self.__generate_getting_steeper_column(df_trend=candles[['bull', 'bear']])
        candles['sma_follow_trend'] = self.__generate_following_trend_column(df_trend=candles[['bull', 'bear']])
        candles['stoc_allows'] = self.__generate_stoc_allows_column(sr_trend=candles['trend'])

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
        rules.commit_positions(
            candles,
            long_indexes=long_direction_index,
            short_indexes=short_direction_index,
            spread=self._static_spread
        )

    def __generate_entry_column_for_wait_close(self, candles):
        print('[Trader] judging entryable or not ...')
        entryable = np.all(candles[self.get_entry_filter()], axis=1)
        candles.loc[entryable, 'entryable'] = candles[entryable].thrust
        self.__set_entryable_prices(candles)

        entry_direction = candles.entryable.fillna(method='ffill')
        long_direction_index = entry_direction == 'long'
        short_direction_index = entry_direction == 'short'

        self.__set_stoploss_prices(
            candles,
            long_indexes=long_direction_index,
            short_indexes=short_direction_index
        )
        rules.commit_positions(
            candles,
            long_indexes=long_direction_index,
            short_indexes=short_direction_index,
            spread=self._static_spread
        )

    def __generate_entry_column_for_scalping(self, candles):
        print('[Trader] judging entryable or not ...')
        scalping.set_entryable_prices(candles, self._static_spread)

        # INFO: 1. 厳し目のstoploss設定: commit_positions_by_loop で is_exitable_by_bollinger を使うときはコチラが良い
        # entry_direction = candles.entryable.fillna(method='ffill')
        # long_direction_index = entry_direction == 'long'
        # short_direction_index = entry_direction == 'short'
        # self.__set_stoploss_prices(
        #     candles,
        #     long_indexes=long_direction_index,
        #     short_indexes=short_direction_index
        # )
        # INFO: 2. 緩いstoploss設定: is_exitable_by_stoc_cross 用
        candles.loc[:, 'possible_stoploss'] = scalping.set_stoploss_prices(
            candles.thrust.fillna(method='ffill'), self._indicators
        )

        # INFO: Entry / Exit のタイミングを確定
        # import pdb; pdb.set_trace()
        commit_factors_df = pd.merge(
            candles[['high', 'low', 'close', 'time', 'entryable', 'entryable_price', 'possible_stoploss']],
            self._indicators[['band_+2σ', 'band_-2σ', 'stoD_3', 'stoSD_3']],
            left_index=True, right_index=True
        )
        commited_df = scalping.commit_positions_by_loop(factor_dicts=commit_factors_df.to_dict('records'))
        candles.loc[:, 'position'] = commited_df['position']
        candles.loc[:, 'exitable_price'] = commited_df['exitable_price']
        candles.loc[:, 'entry_price'] = candles['entryable_price']

    def __judge_entryable(self, candles):
        ''' 各足において entry 可能かどうかを判定し、 candles dataframe に設定 '''
        satisfy_preconditions = np.all(candles[self.get_entry_filter()], axis=1)
        candles.loc[satisfy_preconditions, 'entryable'] = candles[satisfy_preconditions].thrust
        candles.loc[satisfy_preconditions, 'position'] = candles[satisfy_preconditions].thrust.copy()

    def __set_entryable_prices(self, candles):
        ''' entry した場合の price を candles dataframe に設定 '''
        # INFO: long-entry
        long_index = candles.entryable == 'long'
        long_entry_prices = pd.DataFrame({
            'previous_high': candles.shift(1)[long_index].high,
            'current_open': candles[long_index].open
        }).max(axis=1) + self._static_spread
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
            + self._static_spread
        candles.loc[short_indexes, 'possible_stoploss'] = short_stoploss_prices

    def __slide_prices_to_really_possible(self, candles):
        print('[Trader] start sliding ...')
        m10_candles = self.__m10_candles
        m10_candles['time'] = m10_candles.index
        spread = self._static_spread

        position_index = candles.position.isin(['long', 'short']) \
            | (candles.position.isin(['sell_exit', 'buy_exit']) & ~candles.entryable_price.isna())
        position_rows = candles[position_index][[
            'time', 'entryable_price', 'position'
        ]].to_dict('records')
        if position_rows == []:
            print('[Trader] no positions ...')
            return {'result': 'no position'}

        len_of_rows = len(position_rows)
        for i, row in enumerate(position_rows):
            print('[Trader] sliding price .. {}/{}'.format(i + 1, len_of_rows))
            start = row['time']
            end = self.__add_candle_duration(start[:19])
            candles_in_granularity = m10_candles.loc[start:end, :].to_dict('records')

            if row['position'] in ['long', 'sell_exit']:
                for m10_candle in candles_in_granularity:
                    if row['entryable_price'] < m10_candle['high'] + spread:
                        row['price'] = m10_candle['high'] + spread
                        row['time'] = m10_candle['time']
                        break
            elif row['position'] in ['short', 'buy_exit']:
                for m10_candle in candles_in_granularity:
                    if row['entryable_price'] > m10_candle['low']:
                        row['price'] = m10_candle['low']
                        row['time'] = m10_candle['time']
                        break
            if 'price' not in row:
                row['price'] = row['entryable_price']

        slided_positions = pd.DataFrame.from_dict(position_rows)
        candles.loc[position_index, 'entry_price'] = slided_positions.price.to_numpy(copy=True)
        candles.loc[position_index, 'time'] = slided_positions.time.astype(str).to_numpy(copy=True)

        print('[Trader] finished sliding !')
        return {'result': 'success'}

    def __draw_chart_vectorized_ver(self, df_positions):
        drwr = self.__drawer
        if drwr is None: return

        df_len = len(df_positions)
        dfs_indicator = self.__split_df_by_200rows(self._indicators)
        dfs_position = self.__split_df_by_200sequences(df_positions, df_len)

        df_segments_count = len(dfs_indicator)
        for i in range(0, df_segments_count):
            # indicators
            drwr.draw_indicators(d_frame=dfs_indicator[i])

            # positions
            # INFO: exitable_price などの列が残っていると、後 draw_positions_df の dropna で行が消される
            long_entry_df = dfs_position[i][
                dfs_position[i].position.isin(['long', 'sell_exit']) & (~dfs_position[i].price.isna())
            ][['sequence', 'price']]
            short_entry_df = dfs_position[i][
                dfs_position[i].position.isin(['short', 'buy_exit']) & (~dfs_position[i].price.isna())
            ][['sequence', 'price']]
            close_df = dfs_position[i][dfs_position[i].position.isin(['sell_exit', 'buy_exit'])] \
                .drop('price', axis=1) \
                .rename(columns={'exitable_price': 'price'})
            trail_df = dfs_position[i][dfs_position[i].position != '-'][['sequence', 'stoploss']] \
                .rename(columns={'stoploss': 'price'})

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

            # profit(pl) / gross
            if self.__static_options['figure_option'] > 2:
                drwr.draw_df_on_plt(dfs_position[i][['gross']], drwr.PLOT_TYPE['bar'], color='orange', plt_id=3)
                drwr.draw_df_on_plt(dfs_position[i][['profit']], drwr.PLOT_TYPE['bar'], color='yellow', plt_id=3)

            result = drwr.create_png(
                instrument=self.get_instrument(),
                granularity=self.get_granularity(),
                sr_time=sr_time, num=i
            )

            drwr.close_all()
            if df_segments_count != i + 1:
                drwr.init_figure(rows_num=self.__static_options['figure_option'])
            if 'success' in result:
                print('{msg} / {count}'.format(msg=result['success'], count=df_segments_count))

    def __wrangle_result_for_graph(self, result):
        positions_df = result.rename(columns={'entry_price': 'price', 'possible_stoploss': 'stoploss'})
        positions_df['sequence'] = positions_df.index
        # INFO: exit直後のrowで、かつposition列が空
        positions_df.loc[
            ((positions_df.shift(1).position.isin(['sell_exit', 'buy_exit']))
             | ((positions_df.shift(1).position.isin(['long', 'short']))
                & (~positions_df.shift(1).exitable_price.isna())))
            & (positions_df.position.isna()), 'position'
        ] = '-'
        # INFO: entry直後のrowで、かつexit-rowではない
        positions_df.loc[
            (positions_df.shift(1).position.isin(['long', 'short']))
            & (positions_df.shift(1).exitable_price.isna())
            & (~positions_df.position.isin(['sell_exit', 'buy_exit'])), 'position'
        ] = '|'
        positions_df.position.fillna(method='ffill', inplace=True)

        return positions_df

    def _log_skip_reason(self, reason):
        print('[Trader] skip: {}'.format(reason))

    def __add_candle_duration(self, start_string):
        start_time = self.__str_to_datetime(start_string)
        granularity = self.get_granularity()
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
