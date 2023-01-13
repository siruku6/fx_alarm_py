import numpy as np
import pandas as pd
import pytest

import src.trade_rules.base as base


@pytest.fixture(name="spread", scope="module")
def fixture_spread() -> float:
    return 0.005


class TestSetEntryablePrices:
    @pytest.fixture(name="dummy_candles", scope="module")
    def fixture_dummy_candles(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "open": [101.000, 101.000, 124.000, 101.000, 99.999],
                "high": [123.456, 123.456, 123.456, 123.456, 123.456],
                "low": [100.000, 100.000, 100.000, 100.000, 100.000],
                "entryable": [None, "long", "long", "short", "short"],
            }
        )

    def test_basic(self, dummy_candles: pd.DataFrame, spread: float):
        candles: pd.DataFrame = dummy_candles.copy()
        result: np.ndarray = base.generate_entryable_prices(candles, spread=spread)
        expected: np.ndarray = np.array([np.nan, 123.461, 124.005, 100.000, 99.999])
        np.testing.assert_array_equal(result, expected)


def test_generate_trend_column():
    sample_data = pd.DataFrame.from_dict(
        {
            "no": [123, 123.2, 123.1, None],
            "long": [123.3, 123.2, 123.1, "bull"],
            "short": [122.7, 123.8, 123.9, "bear"],
        },
        columns=["close", "10EMA", "20SMA", "trend"],
        orient="index",
    ).astype({"close": "float32", "10EMA": "float32", "20SMA": "float32", "trend": "object"})

    trend = base.generate_trend_column(sample_data, sample_data["close"])
    pd.testing.assert_series_equal(trend, sample_data["trend"], check_names=False)


def test_generate_stoc_allows_column():
    indicators = pd.DataFrame.from_dict(
        {
            "no_trend": [None, 20, 30, False],
            "long_no_entry": ["bull", 20, 30, False],
            "long_entry": ["bull", 50, 30, True],
            "long_high_entry": ["bull", 85, 90, True],
            "short_no_entry": ["bear", 85, 30, False],
            "short_entry": ["bear", 70, 80, True],
            "short_high_entry": ["bear", 15, 5, True],
        },
        columns=["trend", "stoD_3", "stoSD_3", "expected_result"],
        orient="index",
    ).astype({"trend": str, "stoD_3": "float32", "stoSD_3": "float32", "expected_result": "object"})

    result = base.generate_stoc_allows_column(indicators, indicators["trend"])
    assert np.all(result == indicators["expected_result"])
