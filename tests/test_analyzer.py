import pytest
import numpy as np
import pandas as pd
from models.analyzer import Analyzer
from tests.fixtures.d1_stoc_dummy import d1_stoc_dummy


@pytest.fixture(scope='module', autouse=True)
def analyzer_client():
    analyzer_client = Analyzer()

    print('created!')
    yield(analyzer_client)
    print('closed!')


def test_1(analyzer_client):
    d1_stoc_df = pd.DataFrame.from_dict(d1_stoc_dummy)
    candles = d1_stoc_df[['open', 'high', 'low', 'close']]
    analyzer_client.calc_indicators(candles, d1_candles=candles, stoc_only=True)
    result = analyzer_client.get_d1_stoc()

    assert np.all(result['stoD_over_stoSD'] == d1_stoc_df['stoD_over_stoSD'])
