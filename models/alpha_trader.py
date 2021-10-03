from typing import Dict, Union
import pandas as pd

from models.trader import Trader
import models.trade_rules.scalping as scalping


class AlphaTrader(Trader):
    ''' トレードルールに基づいてOandaへの発注を行うclass '''
    def __init__(self, operation='backtest', days=None):
        super(AlphaTrader, self).__init__(operation=operation, days=days)

    #
    # Public
    #
    def backtest(self, candles) -> Dict[str, Union[str, pd.DataFrame]]:
        ''' backtest scalping trade '''
        candles['thrust'] = self._generate_thrust_column(candles)
        self._mark_entryable_rows(candles)  # This needs 'thrust'
        self.__set_entriable_price(candles)
        self.__generate_entry_column(candles)

        candles.to_csv('./tmp/csvs/scalping_data_dump.csv')
        return {'result': '[Trader] Finsihed a series of backtest!', 'candles': candles}

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Private
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def _generate_thrust_column(self, candles: pd.DataFrame, _: pd.Series = None) -> pd.Series:
        return scalping.generate_repulsion_column(candles, ema=self._indicators['10EMA'])

    def __set_entriable_price(self, candles: pd.DataFrame) -> None:
        candles['entryable_price'] = scalping.generate_entryable_prices(
            candles[['open', 'entryable']], self.config.static_spread
        )

    def __generate_entry_column(self, candles: pd.DataFrame) -> pd.DataFrame:
        # INFO: 1. 厳し目のstoploss設定: commit_positions_by_loop で is_exitable_by_bollinger を使うときはコチラが良い
        # entry_direction = candles.entryable.fillna(method='ffill')
        # long_direction_index = entry_direction == 'long'
        # short_direction_index = entry_direction == 'short'
        # self.__set_stoploss_prices(
        #     candles,
        #     long_indexes=long_direction_index,
        #     short_indexes=short_direction_index
        # )
        # INFO: 2. 緩いstoploss設定: exitable_by_stoccross 用
        #   廃止 -> scalping.__decide_exit_price 内で計算している

        # INFO: Entry / Exit のタイミングを確定
        base_df = pd.merge(
            candles[['open', 'high', 'low', 'close', 'time', 'entryable', 'entryable_price', 'stoD_over_stoSD']],
            self._indicators[['sigma*2_band', 'sigma*-2_band', 'stoD_3', 'stoSD_3', 'support', 'regist']],
            left_index=True, right_index=True
        )
        commited_df = scalping.commit_positions_by_loop(factor_dicts=base_df.to_dict('records'))
        # OPTIMIZE: We may be able to  merge two dataframes by the way written in following article.
        #   https://ymt-lab.com/post/2020/python-pandas-insert-columns/
        # like this (but this doesn't work anyway)
        # return pd.concat([candles, commited_df], axis=1) \
        #          .rename(columns={'entryable_price': 'entry_price'})
        candles.loc[:, 'entry_price'] = commited_df['entryable_price']
        candles.loc[:, 'position'] = commited_df['position']
        candles.loc[:, 'exitable_price'] = commited_df['exitable_price']
        candles.loc[:, 'exit_reason'] = commited_df['exit_reason']
        candles.loc[:, 'possible_stoploss'] = commited_df['possible_stoploss']
