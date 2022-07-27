from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from src.analyzer import Analyzer


@pytest.fixture(name="analyzer", scope="module", autouse=True)
def fixture_analyzer():
    yield Analyzer()


def test_fail_calc_indicators(analyzer):
    no_candles = pd.DataFrame([])

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        with patch("builtins.print") as mock:
            analyzer.calc_indicators(no_candles)
    mock.assert_called_once_with("[ERROR] Analyzer: 分析対象データがありません")
    assert pytest_wrapped_e.type == SystemExit


def test_calced_indicators_columns(analyzer, past_usd_candles):
    d1_stoc_df = pd.DataFrame.from_dict(past_usd_candles)

    analyzer.calc_indicators(d1_stoc_df)
    result = analyzer.get_indicators()

    expected = ["time"] + list(Analyzer.INDICATOR_NAMES)
    assert result.columns.intersection(expected).all()


def test_get_long_indicators(analyzer, d1_stoc_dummy):
    d1_stoc_df = pd.DataFrame.from_dict(d1_stoc_dummy)
    candles = d1_stoc_df[["open", "high", "low", "close"]].copy()
    candles.loc[:, "time"] = pd.date_range(end="2020-05-07", periods=100)
    # candles.set_index('time', inplace=True)
    analyzer.calc_indicators(candles, long_span_candles=candles, stoc_only=True)
    result = analyzer.get_long_indicators()

    assert np.all(result["stoD_over_stoSD"] == d1_stoc_df["stoD_over_stoSD"])


examples_for_parabo_touched = (
    # INFO: touched
    (True, 123.456, 100.000, 123.000, True),
    (False, 123.456, 135.790, 100.000, True),
    # INFO: not touched
    (True, 123.456, 100.000, 123.457, False),
    (False, 123.456, 123.455, 100.000, False),
)


@pytest.mark.parametrize(
    "bull, current_parabo, current_h, current_l, expected", examples_for_parabo_touched
)
def test___parabolic_is_touched(bull, current_parabo, current_h, current_l, expected, analyzer):
    result = analyzer._Analyzer__parabolic_is_touched(bull, current_parabo, current_h, current_l)
    assert result == expected
