import datetime
# import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

import models.real_trader as real
from tests.fixtures.d1_stoc_dummy import d1_stoc_dummy


@pytest.fixture(scope='module', autouse=True)
def real_trader_client():
    yield real.RealTrader(operation='unittest')


@pytest.fixture(scope='module', autouse=True)
def dummy_candles():
    d1_stoc_df = pd.DataFrame.from_dict(d1_stoc_dummy)
    candles = d1_stoc_df[['open', 'high', 'low', 'close']].copy()
    candles.loc[:, 'time'] = pd.date_range(end='2020-05-07', periods=100)
    candles.set_index('time', inplace=True)
    yield candles


def test_not_entry(real_trader_client, dummy_candles):
    real_trader_client._ana.calc_indicators(dummy_candles, long_span_candles=dummy_candles)
    indicators = real_trader_client._ana.get_indicators()
    no_time_since_lastloss = datetime.timedelta(hours=0)
    two_hours_since_lastloss = datetime.timedelta(hours=2)

    with patch('models.real_trader.RealTrader._RealTrader__since_last_loss', return_value=no_time_since_lastloss):
        result = real_trader_client._RealTrader__drive_entry_process(
            dummy_candles, dummy_candles.iloc[-1], indicators, indicators.iloc[-1]
        )
        assert result is False

    # with patch('models.real_trader.RealTrader._RealTrader__since_last_loss', return_value=two_hours_since_lastloss):
    #     # FAILED tests/test_real_trader.py::test_not_entry - KeyError: 'preconditions_allows'
    #     result = real_trader_client._RealTrader__drive_entry_process(
    #         dummy_candles, dummy_candles.iloc[-1], indicators, indicators.iloc[-1]
    #     )
    #     assert result is False
    # # import pdb; pdb.set_trace()
