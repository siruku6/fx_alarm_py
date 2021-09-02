import os
import numpy as np
import pandas as pd
import typing as t
from models.candle_storage import FXBase
from models.client_manager import ClientManager
from models.analyzer import Analyzer
from models.drawer import FigureDrawer
from models.tools.mathematics import range_2nd_decimal
import models.trade_rules.base as base_rules
import models.tools.interface as i_face
import models.tools.statistics_module as statistics

# pd.set_option('display.max_rows', 400)


class Trader():
    MAX_ROWS_COUNT = 200
    TIME_STRING_FMT = '%Y-%m-%d %H:%M:%S'

    def __init__(self, operation: str = 'backtest', days: t.Optional[int] = None):
        '''
        Parameters
        ----------
        operation : str
            'backtest', 'forward_test' or 'live'

        Returns
        -------
        None
        '''
        need_request: bool = False if operation == 'unittest' else True
        if operation in ('backtest', 'forward_test'):
            selected_inst: t.List[str, float] = ClientManager.select_instrument()
            self._instrument: str = selected_inst[0]
            self._static_spread: float = selected_inst[1]['spread']
            self.__set_drawing_option()
            self._stoploss_buffer_pips: float = i_face.select_stoploss_digit() * 5
            need_request: bool = i_face.ask_true_or_false(
                msg='[Trader] Which do you use ?  [1]: current_candles, [2]: static_candles :'
            )
            days: int = i_face.ask_number(msg='何日分のデータを取得する？(半角数字): ', limit=365)
        self.__init_common_params(operation, days=days)
        self.__m10_candles: t.Optional[pd.DataFrame] = None
        result: t.Dict[str, str] = self.__prepare_candles(operation, need_request, days).get('info')

        if result is not None:
            print(result)
            return

        self.__prepare_long_span_candles(days=days, need_request=need_request)
        self._ana.calc_indicators(FXBase.get_candles(), long_span_candles=FXBase.get_long_span_candles())
        self._indicators = self._ana.get_indicators()
        self._initialize_position_variables()

    def __set_drawing_option(self):
        self.__static_options = {}
        self.__static_options['figure_option'] = i_face.ask_number(
            msg='[Trader] 画像描画する？ [1]: No, [2]: Yes, [3]: with_P/L ', limit=3
        )
        self._drawer = None

    def __init_common_params(self, operation: str, days: int):
        self._operation: str = operation
        self._ana: Analyzer = Analyzer()
        self._client: ClientManager = ClientManager(
            instrument=self.get_instrument(), test=operation in ('backtest', 'forward_test')
        )
        self._entry_rules = {
            'days': days,
            'granularity': os.environ.get('GRANULARITY') or 'M5',
            # default-filter: かなりhigh performance
            'entry_filter': ['in_the_band', 'stoc_allows', 'band_expansion']
        }
        self._drawer = None
        self._position = None

    def __prepare_candles(self, operation: str, need_request: bool = True, days: int = None) -> t.Dict[str, str]:
        if need_request is False:
            candles = pd.read_csv('tests/fixtures/sample_candles.csv')
        elif operation in ('backtest', 'forward_test'):
            self._entry_rules['granularity'] = i_face.ask_granularity()
            candles = self._client.load_long_chart(
                days=self.get_entry_rules('days'), granularity=self.get_entry_rules('granularity')
            )['candles']
        elif operation == 'live':
            self.tradeable = self._client.call_oanda('is_tradeable')['tradeable']
            if not self.tradeable:
                return {'info': 'exit at once'}

            candles = self._client.load_specify_length_candles(
                length=70, granularity=self.get_entry_rules('granularity')
            )['candles']
        else:
            return {'info': 'exit at once'}

        FXBase.set_candles(candles)
        if need_request is False: return {}

        latest_candle = self._client.call_oanda('current_price')
        self.__update_latest_candle(latest_candle)

        return {}

    def __update_latest_candle(self, latest_candle) -> None:
        '''
        最新の値がgranurarity毎のpriceの上下限を抜いていたら、抜けた値で上書き
        '''
        candle_dict = FXBase.get_candles().iloc[-1].to_dict()
        FXBase.replace_latest_price('close', latest_candle['close'])
        if candle_dict['high'] < latest_candle['high']:
            FXBase.replace_latest_price('high', latest_candle['high'])
        if candle_dict['low'] > latest_candle['low']:
            FXBase.replace_latest_price('low', latest_candle['low'])
        print('[Client] Last_H4: {}, Current_M1: {}'.format(candle_dict, latest_candle))
        print('[Client] New_H4: {}'.format(FXBase.get_candles().iloc[-1].to_dict()))

    def _initialize_position_variables(self) -> None:
        self._set_position({'type': 'none'})
        self.__hist_positions = {'long': [], 'short': []}

    # - - - - - - - - - - - - - - - - - - - - - - - -
    #                getter & setter
    # - - - - - - - - - - - - - - - - - - - - - - - -
    def get_instrument(self):
        return self._instrument

    def get_entry_rules(self, rule_property):
        return self._entry_rules[rule_property]

    def set_entry_rules(self, rule_property, value):
        self._entry_rules[rule_property] = value

    @property
    def m10_candles(self) -> pd.DataFrame:
        return self.__m10_candles

    @m10_candles.setter
    def m10_candles(self, arg: pd.DataFrame) -> None:
        self.__m10_candles: pd.DataFrame = arg

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
            self.set_entry_rules('entry_filter', value=_filter)
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
        self._reset_drawer()

        candles = FXBase.get_candles().copy()
        self._prepare_trade_signs(candles)
        if self.get_entry_rules('entry_filter') == []:
            self.set_entry_rules('entry_filter', value=statistics.FILTER_ELEMENTS)

        if rule in ('swing', 'scalping'):
            result = self.backtest(candles)
        elif rule == 'wait_close':
            result = self._backtest_wait_close(candles)
        else:
            print('Rule {} is not exist ...'.format(rule))
            exit()

        print('{} ... (auto_verify_trading_rule)'.format(result['result']))

        df_positions = self._preprocess_backtest_result(rule, result)
        self._drive_drawing_charts(df_positions=df_positions)
        return df_positions

    #
    # Methods for judging Entry or Close
    #
    def _set_position(self, position_dict):
        self._position = position_dict

    def _merge_long_indicators(self, candles):
        tmp_df = candles.merge(self._ana.get_long_indicators(), on='time', how='left')
        # tmp_df['long_stoD'].fillna(method='ffill', inplace=True)
        # tmp_df['long_stoSD'].fillna(method='ffill', inplace=True)
        tmp_df['stoD_over_stoSD'].fillna(method='ffill', inplace=True)
        tmp_df['stoD_over_stoSD'].fillna({'stoD_over_stoSD': False}, inplace=True)
        tmp_df.loc[:, 'stoD_over_stoSD'] = tmp_df['stoD_over_stoSD'].astype(bool)

        tmp_df['long_20SMA'].fillna(method='ffill', inplace=True)
        tmp_df['long_10EMA'].fillna(method='ffill', inplace=True)
        long_ma = tmp_df[['long_10EMA', 'long_20SMA']].copy() \
                                                      .rename(columns={'long_10EMA': '10EMA', 'long_20SMA': '20SMA'})
        tmp_df['long_trend'] = base_rules.generate_trend_column(long_ma, candles.close)

        return tmp_df

    def __generate_thrust_column(self, candles, trend):
        # INFO: if high == the max of recent-10-candles: True is set !
        sr_highest_in_10candles = (candles.high == candles.high.rolling(window=10).max())
        sr_lowest_in_10candles = (candles.low == candles.low.rolling(window=10).min())
        sr_up_thrust = np.all(
            pd.DataFrame({'highest': sr_highest_in_10candles, 'bull': trend['bull']}),
            axis=1
        )
        sr_down_thrust = np.all(
            pd.DataFrame({'lowest': sr_lowest_in_10candles, 'bear': trend['bear']}),
            axis=1
        )
        method_thrust_checker = np.frompyfunc(base_rules.detect_thrust2, 2, 1)
        result = method_thrust_checker(sr_up_thrust, sr_down_thrust)
        return result

        # INFO: shift(1)との比較のみでthrustを判定する場合
        # method_thrust_checker = np.frompyfunc(base_rules.detect_thrust, 5, 1)
        # result = method_thrust_checker(
        #     candles.trend,
        #     candles.high.shift(1), candles.high,
        #     candles.low.shift(1), candles.low
        # )
        # return result

    # 60EMA is necessary?
    def __generate_ema_allows_column(self, candles):
        ema60 = self._indicators['60EMA']
        ema60_allows_bull = np.all(np.array([candles.bull, ema60 < candles.close]), axis=0)
        ema60_allows_bear = np.all(np.array([candles.bear, ema60 > candles.close]), axis=0)
        return np.any(np.array([ema60_allows_bull, ema60_allows_bear]), axis=0)

    def __generate_in_bands_column(self, price_series: pd.Series) -> np.ndarray:
        ''' 2-sigma-band内にレートが収まっていることを判定するcolumnを生成 '''
        df_over_band_detection = pd.DataFrame({
            'under_positive_band': self._indicators['sigma*2_band'] > price_series,
            'above_negative_band': self._indicators['sigma*-2_band'] < price_series
        })
        return np.all(df_over_band_detection, axis=1)

    def __generate_band_expansion_column(self, df_bands, shift_size=3):
        ''' band が拡張していれば True を格納して numpy配列 を生成 '''
        # OPTIMIZE: bandについては、1足前(shift(1))に広がっていることを条件にしてもよさそう
        #   その場合、広がっていることの確定を待つことになるので、条件としては厳しくなる
        bands_gap = (df_bands['sigma*2_band'] - df_bands['sigma*-2_band'])  # .shift(1).fillna(0.0)
        return bands_gap.rolling(window=shift_size).max() == bands_gap
        # return bands_gap.shift(shift_size) < bands_gap

    def __generate_getting_steeper_column(self, df_trend: pd.DataFrame) -> np.ndarray:
        ''' 移動平均が勢いづいているか否かを判定 '''
        gap_of_ma: pd.Series = self._indicators['10EMA'] - self._indicators['20SMA']
        result: pd.Series = gap_of_ma.shift(1) < gap_of_ma

        # INFO: 上昇方向に勢いづいている
        is_long_steeper: pd.Series = df_trend['bull'].fillna(False) & result
        # INFO: 下降方向に勢いづいている
        is_short_steeper: pd.Series = df_trend['bear'].fillna(False) & np.where(result, False, True)

        return np.any([is_long_steeper, is_short_steeper], axis=0)

    def __generate_following_trend_column(self, df_trend):
        ''' 移動平均線がtrendに沿う方向に動いているか判定する列を返却 '''
        df_sma = self._indicators['20SMA'].copy()
        df_tmp = df_trend.copy()
        df_tmp['sma_up'] = df_sma.shift(1) < df_sma
        df_tmp['sma_down'] = df_sma.shift(1) > df_sma

        both_up: np.ndarray = np.all(df_tmp[['bull', 'sma_up']], axis=1)
        both_down: np.ndarray = np.all(df_tmp[['bear', 'sma_down']], axis=1)
        return np.any([both_up, both_down], axis=0)

    #
    # private
    #
    def _reset_drawer(self):
        if self.__static_options['figure_option'] > 1:
            self._drawer = FigureDrawer(
                rows_num=self.__static_options['figure_option'], instrument=self.get_instrument()
            )

    def __prepare_long_span_candles(self, days: int, need_request: bool = True) -> None:
        if not isinstance(days, int):
            return

        result: pd.DataFrame
        if need_request is False:
            result = pd.read_csv('tests/fixtures/sample_candles_h4.csv')
        else:
            result = self._client.load_long_chart(days=days, granularity='D')['candles']

        result['time'] = pd.to_datetime(result['time'])
        result.set_index('time', inplace=True)
        FXBase.set_long_span_candles(result)
        # result.resample('4H').ffill() # upsamplingしようとしたがいらなかった。

    def _prepare_trade_signs(self, candles):
        print('[Trader] preparing base-data for judging ...')

        if self._operation in ['live', 'forward_test']:
            comparison_prices_with_bands = candles.close
        else:
            comparison_prices_with_bands = candles.open

        indicators = self._indicators
        candles['trend'] = base_rules.generate_trend_column(indicators, candles.close)
        trend = pd.DataFrame({
            'bull': np.where(candles['trend'] == 'bull', True, False),
            'bear': np.where(candles['trend'] == 'bear', True, False)
        })
        candles['thrust'] = self.__generate_thrust_column(candles=candles, trend=trend)
        # 60EMA is necessary?
        # candles['ema60_allows'] = self.__generate_ema_allows_column(candles=candles)
        candles['in_the_band'] = self.__generate_in_bands_column(price_series=comparison_prices_with_bands)
        candles['band_expansion'] = self.__generate_band_expansion_column(
            df_bands=indicators[['sigma*2_band', 'sigma*-2_band']]
        )
        candles['ma_gap_expanding'] = self.__generate_getting_steeper_column(df_trend=trend)
        candles['sma_follow_trend'] = self.__generate_following_trend_column(df_trend=trend)
        candles['stoc_allows'] = base_rules.generate_stoc_allows_column(
            indicators, sr_trend=candles['trend']
        )

    def _preprocess_backtest_result(self, rule, result):
        positions_columns = ['time', 'position', 'entry_price', 'exitable_price']
        if result['result'] == 'no position':
            return pd.DataFrame([], columns=positions_columns)

        df_positions = result['candles'].loc[:, positions_columns]
        pl_gross_df = statistics.aggregate_backtest_result(
            rule=rule,
            df_positions=df_positions,
            granularity=self.get_entry_rules('granularity'),
            stoploss_buffer=self._stoploss_buffer_pips,
            spread=self._static_spread,
            entry_filter=self.get_entry_rules('entry_filter')
        )
        df_positions = self._wrangle_result_for_graph(result['candles'][
            ['time', 'position', 'entry_price', 'possible_stoploss', 'exitable_price']
        ].copy())
        df_positions = pd.merge(df_positions, pl_gross_df, on='time', how='left')
        df_positions['gross'].fillna(method='ffill', inplace=True)

        return df_positions

    def _drive_drawing_charts(self, df_positions):
        drwr = self._drawer
        if drwr is None: return

        df_len = len(df_positions)
        dfs_indicator = self.__split_df_by_200rows(self._indicators)
        dfs_position = self.__split_df_by_200sequences(df_positions, df_len)

        df_segments_count = len(dfs_indicator)
        for i in range(0, df_segments_count):
            self.__draw_one_chart(
                drwr, df_segments_count, df_len, i, indicators=dfs_indicator[i], positions_df=dfs_position[i]
            )

    def __draw_one_chart(self, drwr, df_segments_count, df_len, df_index, indicators, positions_df):
        def query_entry_rows(position_df, position_type, exit_type):
            entry_rows = position_df[
                position_df.position.isin([position_type, exit_type]) & (~position_df.price.isna())
            ][['sequence', 'price']]
            return entry_rows

        start = df_len - Trader.MAX_ROWS_COUNT * (df_index + 1)
        if start < 0:
            start = 0
        end = df_len - Trader.MAX_ROWS_COUNT * df_index
        target_candles = FXBase.get_candles(start=start, end=end)
        sr_time = drwr.draw_candles(target_candles)['time']

        # indicators
        drwr.draw_indicators(d_frame=indicators)
        drwr.draw_long_indicators(candles=target_candles, min_point=indicators['sigma*-2_band'].min(skipna=True))

        # positions
        # INFO: exitable_price などの列が残っていると、後 draw_positions_df の dropna で行が消される
        long_entry_df = query_entry_rows(positions_df, position_type='long', exit_type='sell_exit')
        short_entry_df = query_entry_rows(positions_df, position_type='short', exit_type='buy_exit')
        close_df = positions_df[positions_df.position.isin(['sell_exit', 'buy_exit'])] \
            .drop('price', axis=1) \
            .rename(columns={'exitable_price': 'price'})
        trail_df = positions_df[positions_df.position != '-'][['sequence', 'stoploss']] \
            .rename(columns={'stoploss': 'price'})

        drwr.draw_positions_df(positions_df=long_entry_df, plot_type=drwr.PLOT_TYPE['long'])
        drwr.draw_positions_df(positions_df=short_entry_df, plot_type=drwr.PLOT_TYPE['short'])
        drwr.draw_positions_df(positions_df=close_df, plot_type=drwr.PLOT_TYPE['exit'])
        drwr.draw_positions_df(positions_df=trail_df, plot_type=drwr.PLOT_TYPE['trail'])

        drwr.draw_vertical_lines(
            indexes=np.concatenate(
                [long_entry_df.sequence.values, short_entry_df.sequence.values]
            ),
            vmin=indicators['sigma*-2_band'].min(skipna=True),
            vmax=indicators['sigma*2_band'].max(skipna=True)
        )

        # profit(pl) / gross
        if self.__static_options['figure_option'] > 2:
            drwr.draw_df(positions_df[['gross']], names=['gross'])
            drwr.draw_df(positions_df[['profit']], names=['profit'])

        result = drwr.create_png(
            granularity=self.get_entry_rules('granularity'),
            sr_time=sr_time, num=df_index, filename='test'
        )

        drwr.close_all()
        if df_index + 1 != df_segments_count:
            drwr.init_figure(rows_num=self.__static_options['figure_option'])
        if 'success' in result:
            print('{msg} / {count}'.format(msg=result['success'], count=df_segments_count))

    def _wrangle_result_for_graph(self, result):
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
