from unittest.mock import patch
from typing import Dict, Union

import numpy as np
import pandas as pd
import pytest

from models.trader import ResultProcessor


@pytest.fixture(name='result_processor', scope='function')
def fixture_trader_instance(config) -> ResultProcessor:
    _result_processor: ResultProcessor = ResultProcessor(operation='unittest', config=config)
    yield _result_processor


class TestPreprocessBacktestResult():

    @pytest.fixture(name='dummy_positions', scope='module')
    def fixture_dummy_positions(self):
        return pd.DataFrame({
            'time': pd.date_range(start='2019/09/03', periods=12, freq='1H')
                      .astype(str),
            'position': (
                'buy_exit', None, 'long', None, None, 'sell_exit',
                'short', None, None, 'buy_exit', None, 'long',
            ),
            'entry_price': (
                10.01, None, 10.03, None, None, None,
                11.02, None, None, None, None, 10.05,
            ),
            'possible_stoploss': (
                9.01, 9.11, 9.31, 9.81, 10.81, 11.01,
                9.01, 9.11, 9.31, 9.81, 10.81, 11.01,
            ),
            'exitable_price': (
                9.91, None, None, None, None, 11.13,
                None, None, None, 10.02, None, None,
            )
        })

    def test_without_position(self, result_processor: ResultProcessor):
        result: pd.DataFrame = result_processor._preprocess_backtest_result(
            rule='', result={'result': 'no position'}
        )

        pd.testing.assert_frame_equal(
            result, pd.DataFrame([], columns=['time', 'position', 'entry_price', 'exitable_price'])
        )

    def test_with_positions(self, result_processor: ResultProcessor, dummy_positions: pd.DataFrame):
        expected_gross_df: pd.DataFrame = pd.DataFrame({
            'time': pd.date_range(start='2019/09/03', periods=12, freq='1H')
                      .astype(str),
            'profit': (0.1, np.nan, 0.0, np.nan, np.nan, 1.1, 0.0, np.nan, np.nan, 1.0, np.nan, 0.0),
            'gross': (0.1, 0.1, 0.1, 0.1, 0.1, 1.2, 1.2, 1.2, 1.2, 2.2, 2.2, 2.2)
        })
        expected: pd.DataFrame = \
            pd.merge(dummy_positions, expected_gross_df, on='time', how='left') \
              .rename(columns={'entry_price': 'price', 'possible_stoploss': 'stoploss'}) \
              .assign(position=[
                  'buy_exit', '-', 'long', '|', '|', 'sell_exit',
                  'short', '|', '|', 'buy_exit', '-', 'long'
              ])

        backtest_result: Dict[str, Union[str, pd.DataFrame]] = {'result': '', 'candles': dummy_positions}

        with patch(
            'models.tools.statistics_module.__append_performance_result_to_csv',
            return_value=None
        ):
            result: pd.DataFrame = \
                result_processor._preprocess_backtest_result('scalping', backtest_result)

        pd.testing.assert_frame_equal(result.drop(['sequence'], axis=1), expected)
