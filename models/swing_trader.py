from typing import Dict, List, Union

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
    def backtest(self, candles: pd.DataFrame) -> Dict[str, Union[str, pd.DataFrame]]:
        ''' backtest swing trade '''
        result_msg: str = self.__backtest_common_flow(candles)
        return {'result': result_msg, 'candles': candles}

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Private
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def _backtest_wait_close(self, candles: pd.DataFrame) -> Dict[str, Union[str, pd.DataFrame]]:
        '''
        (the difference from 'backtest' above)
        entry is gonna be done just after the close of each candle is determined
        '''
        candles['thrust'] = wait_close.generate_thrust_column(candles)

        result_msg: str = self.__backtest_common_flow(candles)
        return {'result': result_msg, 'candles': candles}

    def __backtest_common_flow(self, candles: pd.DataFrame) -> str:
        candles.loc[:, 'entryable_price'] = base_rules.generate_entryable_prices(candles, self.config.static_spread)
        self.__generate_entry_column(candles=candles)
        sliding_result = self.__slide_to_reasonable_prices(candles=candles)

        candles.to_csv('./tmp/csvs/full_data_dump.csv')
        result_msg: str = self.__result_message(sliding_result['result'])
        return result_msg

    def _generate_entryable_price(self, candles: pd.DataFrame) -> np.ndarray:
        return base_rules.generate_entryable_prices(
            candles[['open', 'high', 'low', 'entryable']], self.config.static_spread
        )

    def __generate_entry_column(self, candles: pd.DataFrame) -> None:
        print('[Trader] judging entryable or not ...')

        entry_direction: pd.Series = candles['entryable'].fillna(method='ffill')
        long_direction_index: pd.Series = entry_direction == 'long'
        short_direction_index: pd.Series = entry_direction == 'short'

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

    # OPTIMIZE: probably this method has many unnecessary processings!
    def __slide_to_reasonable_prices(self, candles):
        print('[Trader] start sliding ...')

        position_index = candles.position.isin(['long', 'short']) \
            | (candles.position.isin(['sell_exit', 'buy_exit']) & ~candles.entryable_price.isna())
        position_rows = candles[position_index][[
            'time', 'entryable_price', 'position'
        ]].to_dict('records')
        if position_rows == []:
            print('[Trader] no positions ...')
            return {'result': 'no position'}

        df_with_positions = pd.DataFrame.from_dict(position_rows)

        candles.loc[position_index, 'entry_price'] = df_with_positions['entryable_price'].to_numpy(copy=True)
        candles.loc[position_index, 'time'] = df_with_positions['time'].astype(str).to_numpy(copy=True)

        print('[Trader] finished sliding !')
        return {'result': 'success'}

    def __result_message(self, result: str) -> str:
        if result == 'no position':
            return 'no position'

        return '[Trader] 1 series of trading is FINISHED!'
