from unittest.mock import patch
import pytest

import numpy as np
import pandas as pd
from models.analyzer import Analyzer


@pytest.fixture(name='analyzer', scope='module', autouse=True)
def fixture_analyzer():
    yield Analyzer()


def test_fail_calc_indicators(analyzer):
    no_candles = pd.DataFrame([])

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        with patch('builtins.print') as mock:
            analyzer.calc_indicators(no_candles)
    mock.assert_called_once_with('[ERROR] Analyzer: 分析対象データがありません')
    assert pytest_wrapped_e.type == SystemExit


def test_get_long_indicators(analyzer, d1_stoc_dummy):
    d1_stoc_df = pd.DataFrame.from_dict(d1_stoc_dummy)
    candles = d1_stoc_df[['open', 'high', 'low', 'close']].copy()
    candles.loc[:, 'time'] = pd.date_range(end='2020-05-07', periods=100)
    # candles.set_index('time', inplace=True)
    analyzer.calc_indicators(candles, long_span_candles=candles, stoc_only=True)
    result = analyzer.get_long_indicators()

    assert np.all(result['stoD_over_stoSD'] == d1_stoc_df['stoD_over_stoSD'])
