# import datetime
import numpy as np
import pandas as pd
from models.oanda_py_client import FXBase
from models.trader import Trader
import models.trade_rules.scalping as scalping
import models.tools.statistics_module as statistics


class AlphaTrader(Trader):
    ''' トレードルールに基づいてOandaへの発注を行うclass '''
    def __init__(self, operation='backtest', days=None):
        super(AlphaTrader, self).__init__(operation=operation, days=days)

    #
    # Public
    #
    def auto_verify_trading_rule(self, rule='scalping'):
        ''' tradeルールを自動検証 '''
        self._reset_drawer()

        candles = FXBase.get_candles().copy()
        self._prepare_trade_signs(candles)
        result = self.__backtest_scalping(candles)

        print('{} ... (auto_verify_trading_rule)'.format(result['result']))
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

        self._drive_drawing_charts(df_positions=df_positions)
        return df_positions


    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Private
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def __backtest_scalping(self, candles):
        ''' スキャルピングのentry pointを検出 '''
        candles['thrust'] = scalping.generate_repulsion_column(candles, ema=self._indicators['10EMA'])
        entryable = np.all(candles[self.get_entry_rules('entry_filter')], axis=1)
        candles.loc[entryable, 'entryable'] = candles[entryable].thrust

        self.__generate_entry_column(candles)

        candles.to_csv('./tmp/csvs/scalping_data_dump.csv')
        return {'result': '[Trader] 売買判定終了', 'candles': candles}

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
            candles[['high', 'low', 'close', 'time', 'entryable', 'entryable_price']],  # , 'possible_stoploss'
            self._indicators[['band_+2σ', 'band_-2σ', 'stoD_3', 'stoSD_3', 'support', 'regist']],
            left_index=True, right_index=True
        )
        commit_factors_df = self._merge_long_stoc(base_df)

        commited_df = scalping.commit_positions_by_loop(factor_dicts=commit_factors_df.to_dict('records'))
        candles.loc[:, 'position'] = commited_df['position']
        candles.loc[:, 'exitable_price'] = commited_df['exitable_price']
        candles.loc[:, 'exit_reason'] = commited_df['exit_reason']
        candles.loc[:, 'entry_price'] = candles['entryable_price']
        candles.loc[:, 'possible_stoploss'] = commited_df['possible_stoploss']
