import math
import numpy as np
import pandas as pd
import pytest

import models.tools.statistics_module as stat


def test___calc_profit():
    dummy_position_hist_dicts = {
        'position': [
            'long', 'sell_exit', 'sell_exit', 'short', 'buy_exit', 'buy_exit',
            'long', 'sell_exit', 'sell_exit', 'short', 'buy_exit', 'buy_exit'
        ],
        'entry_price': [
            120.027, None, 122.123, 121.981, None, 121.278,
            112.038, None, 111.058, 112.036, None, 112.278
        ],
        'exitable_price': [
            None, 120.195, 122.141, None, 121.534, 120.962,
            None, 111.941, 111.019, None, 112.362, 112.962
        ]
    }
    expected_result = [
        0.0, 0.168, 0.018, 0.0, 0.447, 0.316,
        0.0, -0.097, -0.039, 0.0, -0.326, -0.684 
    ]

    positions_df = pd.DataFrame.from_dict(dummy_position_hist_dicts)
    result = stat.__calc_profit(positions_df)['profit'].values
    for diff, expected_diff in zip(result, expected_result):
        assert math.isclose(diff, expected_diff)


def test___calc_profit_extra_pattern():
    ''' 継続ポジションexit時に即座終了ポジションがあった場合 '''
    dummy_position_hist_dicts = {
        'position': [
            'long', 'sell_exit', 'short', 'buy_exit',
            'long', 'sell_exit', 'short', 'buy_exit'
        ],
        'entry_price': [
            120.027, 120.112, 121.981, 121.634,
            112.038, 112.041, 112.036, 112.332
        ],
        'exitable_price': [
            None, 120.195, None, 121.534,
            None, 111.941, None, 112.362
        ]
    }
    expected_result = [
        0.0, 0.251, 0.0, 0.547,
        0.0, -0.197, 0.0, -0.356
    ]

    positions_df = pd.DataFrame.from_dict(dummy_position_hist_dicts)
    result = stat.__calc_profit(positions_df)['profit'].values
    for diff, expected_diff in zip(result, expected_result):
        assert math.isclose(diff, expected_diff)
