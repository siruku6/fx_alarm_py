import numpy as np
import pandas as pd

from models.candle_storage import FXBase
from models.trader import Trader
import models.trade_rules.scalping as scalping


class AlphaTrader(Trader):
    ''' トレードルールに基づいてOandaへの発注を行うclass '''
    def __init__(self, operation='backtest', days=None):
        super(AlphaTrader, self).__init__(operation=operation, days=days)

    #
    # Public
    #
    def backtest(self, candles):
        ''' スキャルピングのentry pointを検出 '''
        candles['thrust'] = scalping.generate_repulsion_column(candles, ema=self._indicators['10EMA'])
        entryable = np.all(candles[self.get_entry_rules('entry_filter')], axis=1)
        candles.loc[entryable, 'entryable'] = candles[entryable]['thrust']

        candles = self._merge_long_indicators(candles)
        self.__generate_entry_column(candles)
        # HACK: 長期足 indicators をcandlesに保持させるための実装
        FXBase.set_candles(candles)
        candles.to_csv('./tmp/csvs/scalping_data_dump.csv')
        return {'result': '[Trader] 売買判定終了', 'candles': candles}

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Private
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def __generate_entry_column(self, candles):
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
        # INFO: 2. 緩いstoploss設定: exitable_by_stoccross 用
        #   廃止 -> scalping.__decide_exit_price 内で計算している

        # INFO: Entry / Exit のタイミングを確定
        base_df = pd.merge(
            candles[['open', 'high', 'low', 'close', 'time', 'entryable', 'entryable_price', 'stoD_over_stoSD']],
            self._indicators[['sigma*2_band', 'sigma*-2_band', 'stoD_3', 'stoSD_3', 'support', 'regist']],
            left_index=True, right_index=True
        )
        commited_df = scalping.commit_positions_by_loop(factor_dicts=base_df.to_dict('records'))
        candles.loc[:, 'position'] = commited_df['position']
        candles.loc[:, 'exitable_price'] = commited_df['exitable_price']
        candles.loc[:, 'exit_reason'] = commited_df['exit_reason']
        candles.loc[:, 'entry_price'] = commited_df['entryable_price']
        candles.loc[:, 'possible_stoploss'] = commited_df['possible_stoploss']
