from typing import Dict, List, Union

import numpy as np
import pandas as pd

from models.trader import Trader
import models.trade_rules.base as base_rules
import models.trade_rules.stoploss as stoploss_strategy
# import models.trade_rules.wait_close as wait_close


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
        shifted_candles: pd.DataFrame = self.__shift_trade_signs(candles)
        # candles['thrust'] = wait_close.generate_thrust_column(candles)

        result_msg: str = self.__backtest_common_flow(shifted_candles)
        return {'result': result_msg, 'candles': shifted_candles}

    # OPTIMIZE: This is not good rule...but at least working
    def __shift_trade_signs(self, candles: pd.DataFrame) -> pd.DataFrame:
        shift_target: List[str] = ['thrust', 'entryable'] + self.config.get_entry_rules('entry_filters')

        df_shifted_target: pd.DataFrame = candles[shift_target].shift(1)
        candles_without_shift_target: pd.DataFrame = candles.drop(shift_target, axis=1)
        shifted_candles: pd.DataFrame = pd.concat(
            [candles_without_shift_target, df_shifted_target], axis=1
        )
        return shifted_candles

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
        candles_with_stoploss: pd.DataFrame = self.__set_stoploss_prices(candles, entry_direction)
        base_rules.commit_positions(
            candles_with_stoploss,
            long_indexes=(entry_direction == 'long'),
            short_indexes=(entry_direction == 'short'),
            spread=self.config.static_spread
        )

    def __set_stoploss_prices(self, candles: pd.DataFrame, entry_direction: pd.Series) -> pd.DataFrame:
        candles.loc[:, 'possible_stoploss'] = stoploss_strategy.previous_candle_otherside(
            candles, entry_direction, self.config
        )
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
