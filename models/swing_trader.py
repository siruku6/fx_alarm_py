from typing import List, Union

import numpy as np
import pandas as pd

from models.trader import Trader
import models.trade_rules.base as base_rules
import models.trade_rules.wait_close as wait_close


class SwingTrader(Trader):
    ''' トレードルールに基づいてOandaへの発注を行うclass '''
    def __init__(self, operation='backtest', days=None):
        super(SwingTrader, self).__init__(operation=operation, days=days)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Public
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def backtest(self, candles):
        ''' スイングトレードのentry pointを検出 '''
        # INFO: 繰り返しデモする場合に前回のpositionが残っているので、リセットする いらなくない？
        self._initialize_position_variables()

        self.__generate_entry_column(candles=candles)
        sliding_result = self.__slide_prices_to_really_possible(candles=candles)
        candles.to_csv('./tmp/csvs/full_data_dump.csv')

        result = 'no position' if sliding_result['result'] == 'no position' else '[Trader] 売買判定終了'
        return {'result': result, 'candles': candles}

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Private
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def _backtest_wait_close(self, candles):
        ''' swingでH4 close直後のみにentryする場合のentry pointを検出 '''
        candles['thrust'] = wait_close.generate_thrust_column(candles)
        self.__generate_entry_column_for_wait_close(candles)
        sliding_result = self.__slide_prices_to_really_possible(candles=candles)
        candles.to_csv('./tmp/csvs/wait_close_data_dump.csv')

        result = 'no position' if sliding_result['result'] == 'no position' else '[Trader] 売買判定終了'
        return {'result': result, 'candles': candles}

    def __generate_entry_column(self, candles):
        print('[Trader] judging entryable or not ...')
        self.__judge_entryable(candles)
        base_rules.set_entryable_prices(candles, self.config.static_spread)

        entry_direction = candles.entryable.fillna(method='ffill')
        long_direction_index = entry_direction == 'long'
        short_direction_index = entry_direction == 'short'

        self.__set_stoploss_prices(
            candles,
            long_indexes=long_direction_index,
            short_indexes=short_direction_index
        )
        base_rules.commit_positions(
            candles,
            long_indexes=long_direction_index,
            short_indexes=short_direction_index,
            spread=self.config.static_spread
        )

    def __judge_entryable(self, candles):
        ''' 各足において entry 可能かどうかを判定し、 candles dataframe に設定 '''
        satisfy_preconditions = np.all(candles[self.config.get_entry_rules('entry_filters')], axis=1)
        candles.loc[satisfy_preconditions, 'entryable'] = candles[satisfy_preconditions]['thrust']
        candles.loc[satisfy_preconditions, 'position'] = candles[satisfy_preconditions]['thrust'].copy()

    def __generate_entry_column_for_wait_close(self, candles: pd.DataFrame):
        print('[Trader] judging entryable or not ...')
        entryable = np.all(candles[self.config.get_entry_rules('entry_filters')], axis=1)
        candles.loc[entryable, 'entryable'] = candles[entryable]['thrust']
        base_rules.set_entryable_prices(candles, self.config.static_spread)

        entry_direction = candles.entryable.fillna(method='ffill')
        long_direction_index = entry_direction == 'long'
        short_direction_index = entry_direction == 'short'

        candles_with_stoploss: pd.DataFrame = self.__set_stoploss_prices(
            candles,
            long_indexes=long_direction_index,
            short_indexes=short_direction_index
        )
        base_rules.commit_positions(
            candles_with_stoploss,
            long_indexes=long_direction_index,
            short_indexes=short_direction_index,
            spread=self.config.static_spread
        )

    def __set_stoploss_prices(
        self, candles: pd.DataFrame,
        long_indexes: Union[List[bool], np.ndarray],
        short_indexes: Union[List[bool], np.ndarray]
    ) -> pd.DataFrame:
        ''' trail した場合の stoploss 価格を candles dataframe に設定 '''
        # INFO: long-stoploss
        long_stoploss_prices: pd.Series = candles.shift(1)[long_indexes]['low'] - self.config.stoploss_buffer_pips
        candles.loc[long_indexes, 'possible_stoploss'] = long_stoploss_prices

        # INFO: short-stoploss
        short_stoploss_prices: pd.Series = candles.shift(1)[short_indexes]['high'] \
            + self.config.stoploss_buffer_pips \
            + self.config.static_spread
        candles.loc[short_indexes, 'possible_stoploss'] = short_stoploss_prices
        return candles

    def __slide_prices_to_really_possible(self, candles):
        print('[Trader] start sliding ...')

        position_index = candles.position.isin(['long', 'short']) \
            | (candles.position.isin(['sell_exit', 'buy_exit']) & ~candles.entryable_price.isna())
        position_rows = candles[position_index][[
            'time', 'entryable_price', 'position'
        ]].to_dict('records')
        if position_rows == []:
            print('[Trader] no positions ...')
            return {'result': 'no position'}

        # position_rows = self.__slide_prices_in_dicts(time_series=candles['time'], position_rows=position_rows)
        slided_positions = pd.DataFrame.from_dict(position_rows)

        candles.loc[position_index, 'entry_price'] = slided_positions['entryable_price'].to_numpy(copy=True)
        candles.loc[position_index, 'time'] = slided_positions['time'].astype(str).to_numpy(copy=True)

        print('[Trader] finished sliding !')
        return {'result': 'success'}

    # def __slide_prices_in_dicts(self, time_series, position_rows):
    #     if self.m10_candles is None:
    #         self.m10_candles = self.__load_m10_candles(time_series)

    #     m10_candles = self.m10_candles
    #     m10_candles['time'] = m10_candles.index
    #     spread = self.config.static_spread

    #     len_of_rows = len(position_rows)
    #     for i, row in enumerate(position_rows):
    #         print('[Trader] sliding price .. {}/{}'.format(i + 1, len_of_rows))
    #         start = row['time']
    #         end = self.__add_candle_duration(start[:19])
    #         candles_in_granularity = m10_candles.loc[start:end, :].to_dict('records')

    #         if row['position'] in ['long', 'sell_exit']:
    #             for m10_candle in candles_in_granularity:
    #                 if row['entryable_price'] < m10_candle['high'] + spread:
    #                     row['price'] = m10_candle['high'] + spread
    #                     row['time'] = m10_candle['time']
    #                     break
    #         elif row['position'] in ['short', 'buy_exit']:
    #             for m10_candle in candles_in_granularity:
    #                 if row['entryable_price'] > m10_candle['low']:
    #                     row['price'] = m10_candle['low']
    #                     row['time'] = m10_candle['time']
    #                     break
    #         if 'price' not in row:
    #             row['price'] = row['entryable_price']
    #     return position_rows

    # def __load_m10_candles(self, time_series):
    #     first_time = converter.str_to_datetime(time_series.iat[0][:19])
    #     last_time = converter.str_to_datetime(time_series.iat[-1][:19])
    #     # INFO: 実は、candlesのlastrow分のm10candlesがない
    #     return self._client.load_or_query_candles(first_time, last_time, granularity='M10')[['high', 'low']]

    # def __add_candle_duration(self, start_string):
    #     start_time = converter.str_to_datetime(start_string)
    #     candle_duration = converter.granularity_to_timedelta(self.config.get_entry_rules('granularity'))

    #     a_minute = datetime.timedelta(minutes=1)
    #     result = (start_time + candle_duration - a_minute).strftime(Trader.TIME_STRING_FMT)
    #     return result
