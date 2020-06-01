import pytest
import numpy as np
import pandas as pd
from models.analyzer import Analyzer
from tests.fixtures.d1_stoc_dummy import d1_stoc_dummy


@pytest.fixture(scope='module', autouse=True)
def analyzer_client():
    yield Analyzer()


def test_get_long_stoc(analyzer_client):
    d1_stoc_df = pd.DataFrame.from_dict(d1_stoc_dummy)
    candles = d1_stoc_df[['open', 'high', 'low', 'close']].copy()
    candles.loc[:, 'time'] = pd.date_range(end='2020-05-07', periods=100)
    candles.set_index('time', inplace=True)
    analyzer_client.calc_indicators(candles, long_span_candles=candles, stoc_only=True)
    result = analyzer_client.get_long_stoc()

    assert np.all(result['stoD_over_stoSD'] == d1_stoc_df['stoD_over_stoSD'])
