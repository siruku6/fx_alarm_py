import math

import numpy as np
import pandas as pd

import src.trade_rules.scalping as scalping


def test_generate_up_repulsion_column():
    test_df = pd.DataFrame.from_dict(
        {
            "emaNone": [None, 101.8, 100.0, None],
            "touch_ema": [None, 101.5, 98.0, 100.0],
            "repulsion": ["bull", 102.0, 100.0, 101.0],
            "current": ["bull", 102.1, 100.5, 101.5],
        },
        columns=["trend", "high", "low", "ema"],
        orient="index",
    )
    repulsion_series = scalping.generate_repulsion_column(candles=test_df, ema=test_df.ema)

    assert repulsion_series[0] is None
    assert repulsion_series[1] is None
    # assert repulsion_series[2] is None  # repulsion_exist 試験中のため、コメントアウト
    assert repulsion_series[3] == "long"


def test_generate_down_repulsion_column():
    test_df = pd.DataFrame.from_dict(
        {
            "emaNone": [None, 101.5, 101.2, None],
            "touch_ema": [None, 101.6, 101.4, 102.0],
            "repulsion": ["bear", 101.3, 101.1, 101.5],
            "current": ["bear", 101.0, 101.1, 101.3],
        },
        columns=["trend", "high", "low", "ema"],
        orient="index",
    )
    repulsion_series = scalping.generate_repulsion_column(candles=test_df, ema=test_df.ema)

    assert repulsion_series[0] is None
    assert repulsion_series[1] is None
    assert repulsion_series[2] is None
    assert repulsion_series[3] == "short"


def test_generate_entryable_prices():
    test_candles = pd.DataFrame.from_dict(
        {
            "entryable": [None, np.nan, "long", "long", "short", "short"],
            "open": [100.0, 100.0, 101.0, 102.0, 99.0, 98.0],
        }
    )
    result: np.ndarray = scalping.generate_entryable_prices(test_candles, spread=0.5)
    expected_entryable_prices = [np.nan, np.nan, 101.5, 102.5, 99.0, 98.0]

    for price, expected_price in zip(result, expected_entryable_prices):
        if math.isnan(price):
            assert math.isnan(expected_price)
        else:
            assert math.isclose(price, expected_price)
