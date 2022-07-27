import math

import numpy as np
import pandas as pd

import src.tools.statistics_module as stat

# import pytest


def test___calc_profit():
    dummy_position_hist_dicts = {
        "position": [
            "long",
            "sell_exit",
            "sell_exit",
            "short",
            "buy_exit",
            "buy_exit",
            "long",
            "sell_exit",
            "sell_exit",
            "short",
            "buy_exit",
            "buy_exit",
        ],
        "entry_price": [
            120.027,
            None,
            122.123,
            121.981,
            None,
            121.278,
            112.038,
            None,
            111.058,
            112.036,
            None,
            112.278,
        ],
        "exitable_price": [
            None,
            120.195,
            122.141,
            None,
            121.534,
            120.962,
            None,
            111.941,
            111.019,
            None,
            112.362,
            112.962,
        ],
    }
    expected_result = [
        0.0,
        0.168,
        0.018,
        0.0,
        0.447,
        0.316,
        0.0,
        -0.097,
        -0.039,
        0.0,
        -0.326,
        -0.684,
    ]

    positions_df = pd.DataFrame.from_dict(dummy_position_hist_dicts)
    result = stat.__calc_profit(positions_df)["profit"].values
    for diff, expected_diff in zip(result, expected_result):
        assert math.isclose(diff, expected_diff)


def test___calc_profit_with_soon_exits():
    """即座終了ポジションが最初と最後にある場合"""
    dummy_position_hist_dicts = {
        "position": ("buy_exit", "long", "sell_exit", "sell_exit"),
        "entry_price": (120.027, 114.340, None, 112.038),
        "exitable_price": (119.941, None, 114.932, 111.958),
    }
    expected_result = (0.086, 0.0, 0.592, -0.080)

    positions_df = pd.DataFrame.from_dict(dummy_position_hist_dicts)
    result = stat.__calc_profit(positions_df)["profit"].values
    for diff, expected_diff in zip(result, expected_result):
        assert math.isclose(diff, expected_diff)


def test___calc_profit_combination():
    """継続ポジションexit時に即座終了ポジションがあった場合"""
    dummy_position_hist_dicts = {
        "position": [
            "long",
            "sell_exit",
            "short",
            "buy_exit",
            "long",
            "sell_exit",
            "short",
            "buy_exit",
        ],
        "entry_price": [120.027, 120.112, 121.981, 121.634, 112.038, 112.041, 112.036, 112.332],
        "exitable_price": [None, 120.195, None, 121.534, None, 111.941, None, 112.362],
    }
    expected_result = [0.0, 0.251, 0.0, 0.547, 0.0, -0.197, 0.0, -0.356]

    positions_df = pd.DataFrame.from_dict(dummy_position_hist_dicts)
    result = stat.__calc_profit(positions_df)["profit"].values
    for diff, expected_diff in zip(result, expected_result):
        assert math.isclose(diff, expected_diff)


def test___hist_index_of():
    positions = pd.DataFrame(
        {
            "position": ["long", "sell_exit", "short", "buy_exit", "long", "short"],
            "entry_price": [123.456, 234.567, 345.678, 456.789, None, np.nan],
        }
    )

    # index of long position
    long_index = stat.__hist_index_of(positions, sign="long|sell_exit")
    expected_result = pd.Series([True, True, False, False, False, False])
    pd.testing.assert_series_equal(long_index, expected_result)

    # index of short position
    short_index = stat.__hist_index_of(positions, sign="short|buy_exit")
    expected_result = pd.Series([False, False, True, True, False, False])
    pd.testing.assert_series_equal(short_index, expected_result)
