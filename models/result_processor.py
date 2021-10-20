from models.trader_config import TraderConfig
from typing import Dict, List, Optional, Union
import numpy as np
import pandas as pd

from models.candle_storage import FXBase
from models.drawer import FigureDrawer
import models.tools.interface as i_face
import models.tools.statistics_module as statistics


class ResultProcessor:
    MAX_ROWS_COUNT: int = 200

    def __init__(self, operation: str, config: TraderConfig) -> None:
        self._config: TraderConfig = config
        self._drawer: FigureDrawer = None
        if operation in ('backtest', 'forward_test'):
            self.__set_drawing_option()

    def __set_drawing_option(self):
        self.__static_options = {}
        self.__static_options['figure_option'] = i_face.ask_number(
            msg='[Trader] 画像描画する？ [1]: No, [2]: Yes, [3]: with_P/L ', limit=3
        )
        self._drawer = None

    def reset_drawer(self):
        if self.__static_options['figure_option'] > 1:
            self._drawer = FigureDrawer(
                rows_num=self.__static_options['figure_option'], instrument=self._config.get_instrument()
            )

    def run(self, rule: str, result: Dict[str, Union[str, pd.DataFrame]], indicators: pd.DataFrame) -> pd.DataFrame:
        df_positions: pd.DataFrame = self._preprocess_backtest_result(rule, result)
        self._drive_drawing_charts(df_positions=df_positions, indicators=indicators)

        return df_positions

    def _preprocess_backtest_result(
        self, rule: str, result: Dict[str, Union[str, pd.DataFrame]]
    ) -> pd.DataFrame:
        positions_columns: List[str] = ['time', 'position', 'entry_price', 'exitable_price']
        if result['result'] == 'no position':
            return pd.DataFrame([], columns=positions_columns)

        pl_gross_df: pd.DataFrame = statistics.aggregate_backtest_result(
            rule=rule,
            df_positions=result['candles'].loc[:, positions_columns],
            config=self._config
        )
        df_positions: pd.DataFrame = self._wrangle_result_for_graph(
            result['candles'][
                ['time', 'position', 'entry_price', 'possible_stoploss', 'exitable_price']
            ].copy()
        )
        df_positions: pd.DataFrame = pd.merge(df_positions, pl_gross_df, on='time', how='left')
        df_positions['gross'].fillna(method='ffill', inplace=True)

        return df_positions

    def _drive_drawing_charts(self, df_positions: pd.DataFrame, indicators: pd.DataFrame):
        if self._drawer is None: return

        df_len: int = len(df_positions)
        dfs_indicator: List[pd.DataFrame] = self.__split_df_by_200rows(indicators)
        dfs_position: List[pd.DataFrame] = self.__split_df_by_200sequences(df_positions, df_len)

        df_segments_count: int = len(dfs_indicator)
        for segment_index in range(0, df_segments_count):
            self.__draw_one_chart(
                self._drawer, df_segments_count, df_len, segment_index,
                indicators=dfs_indicator[segment_index], positions_df=dfs_position[segment_index]
            )

    def __draw_one_chart(
        self, drwr: FigureDrawer, df_segments_count: int, df_len: int, df_index: int,
        indicators: pd.DataFrame, positions_df: pd.DataFrame
    ):
        def query_entry_rows(position_df: pd.DataFrame, position_type: str, exit_type: str) -> pd.DataFrame:
            entry_rows: pd.DataFrame = position_df[
                position_df.position.isin([position_type, exit_type]) & (~position_df.price.isna())
            ][['sequence', 'price']]
            return entry_rows

        start: int = df_len - ResultProcessor.MAX_ROWS_COUNT * (df_index + 1)
        if start < 0:
            start = 0
        end: int = df_len - ResultProcessor.MAX_ROWS_COUNT * df_index
        target_candles: pd.DataFrame = FXBase.get_candles(start=start, end=end)
        sr_time: pd.Series = drwr.draw_candles(target_candles)['time']

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
            granularity=self._config.get_entry_rules('granularity'),
            sr_time=sr_time, num=df_index, filename='test'
        )

        drwr.close_all()
        if df_index + 1 != df_segments_count:
            drwr.init_figure(rows_num=self.__static_options['figure_option'])
        if 'success' in result:
            print('{msg} / {count}'.format(msg=result['success'], count=df_segments_count))

    def _wrangle_result_for_graph(self, result: pd.DataFrame) -> pd.DataFrame:
        positions_df: pd.DataFrame = result.rename(columns={'entry_price': 'price', 'possible_stoploss': 'stoploss'})
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

    def __split_df_by_200rows(self, d_frame: pd.DataFrame) -> List[pd.DataFrame]:
        dfs: List[Optional[pd.DataFrame]] = []
        df_len: str = len(d_frame)
        loop: int = 0

        while ResultProcessor.MAX_ROWS_COUNT * loop < df_len:
            end = df_len - ResultProcessor.MAX_ROWS_COUNT * loop
            loop += 1
            start = df_len - ResultProcessor.MAX_ROWS_COUNT * loop
            start = start if start > 0 else 0
            dfs.append(d_frame[start:end].reset_index(drop=True))
        return dfs

    def __split_df_by_200sequences(self, d_frame: pd.DataFrame, df_len: int) -> List[pd.DataFrame]:
        dfs: List[Optional[pd.DataFrame]] = []
        loop: int = 0

        while ResultProcessor.MAX_ROWS_COUNT * loop < df_len:
            end = df_len - ResultProcessor.MAX_ROWS_COUNT * loop
            loop += 1
            start = df_len - ResultProcessor.MAX_ROWS_COUNT * loop
            start = start if start > 0 else 0
            df_target = d_frame[(start <= d_frame.sequence) & (d_frame.sequence < end)].copy()
            # 描画は sequence に基づいて行われるので、ずらしておく
            df_target['sequence'] = df_target.sequence - start
            dfs.append(df_target)
        return dfs
