import unittest
import numpy as np
import pandas as pd
# from unittest.mock import patch
import models.trade_rules.scalping as scalping


class TestScalping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print('\n[Scalping] setup')

    @classmethod
    def tearDownClass(cls):
        print('\n[Scalping] tearDown')

    def test_generate_up_repulsion_column(self):
        test_df = pd.DataFrame.from_dict(
            {
                'emaNone': [None, 101.8, 100.0, None],
                'touch_ema': [None, 101.5, 98.0, 100.0],
                'repulsion': ['bull', 102.0, 100.0, 101.0],
                'current': ['bull', 102.1, 100.5, 101.5]
            },
            columns=['trend', 'high', 'low', 'ema'],
            orient='index'
        )
        repulsion_series = scalping.generate_repulsion_column(candles=test_df, ema=test_df.ema)

        self.assertEqual(repulsion_series[0], None)
        self.assertEqual(repulsion_series[1], None)
        # self.assertEqual(repulsion_series[2], None)  # repulsion_exist 試験中のため、コメントアウト
        self.assertEqual(repulsion_series[3], 'long')

    def test_generate_down_repulsion_column(self):
        test_df = pd.DataFrame.from_dict(
            {
                'emaNone': [None, 101.5, 101.2, None],
                'touch_ema': [None, 101.6, 101.4, 102.0],
                'repulsion': ['bear', 101.3, 101.1, 101.5],
                'current': ['bear', 101.0, 101.1, 101.3]
            },
            columns=['trend', 'high', 'low', 'ema'],
            orient='index'
        )
        repulsion_series = scalping.generate_repulsion_column(candles=test_df, ema=test_df.ema)
        # import pdb; pdb.set_trace()

        self.assertEqual(repulsion_series[0], None)
        self.assertEqual(repulsion_series[1], None)
        self.assertEqual(repulsion_series[2], None)
        self.assertEqual(repulsion_series[3], 'short')

    def test_is_exitable_by_stoc_cross(self):
        test_dicts = [
            {'position_type': 'long', 'stod': 40, 'stosd': 90, 'exitable': True},
            {'position_type': 'long', 'stod': 70, 'stosd': 80, 'exitable': True},
            {'position_type': 'long', 'stod': 80, 'stosd': 70, 'exitable': False},
            {'position_type': 'short', 'stod': 90, 'stosd': 40, 'exitable': True},
            {'position_type': 'short', 'stod': 80, 'stosd': 70, 'exitable': True},
            {'position_type': 'short', 'stod': 70, 'stosd': 80, 'exitable': False}
        ]
        for row in test_dicts:
            is_exitable = scalping.is_exitable_by_stoc_cross(
                position_type=row['position_type'],
                stod=row['stod'],
                stosd=row['stosd']
            )
            self.assertEqual(is_exitable, row['exitable'])

    def test_is_exitable_by_bollinger(self):
        test_dicts = [
            {'spot_price': 125.5, 'plus_2sigma': 130, 'minus_2sigma': 120, 'exitable': False},
            {'spot_price': 130.5, 'plus_2sigma': 130, 'minus_2sigma': 120, 'exitable': True},
            {'spot_price': 119.5, 'plus_2sigma': 130, 'minus_2sigma': 120, 'exitable': True}
        ]
        for row in test_dicts:
            is_exitable = scalping.is_exitable_by_bollinger(
                row['spot_price'], row['plus_2sigma'], row['minus_2sigma']
            )
            self.assertEqual(is_exitable, row['exitable'])


def test___decide_exit_price():
    # - - - - - - - - - - - - - - - - - - - -
    #             long entry
    # - - - - - - - - - - - - - - - - - - - -
    # 上昇中
    entry_direction = 'long'
    one_frame = {
        'open': 100.0, 'high': 130.0, 'low': 90.0, 'close': 120.0,
        'possible_stoploss': 80, 'band_+2σ': 140, 'band_-2σ': 85, 'stoD_3': 60, 'stoSD_3': 50
    }
    exit_price = scalping.__decide_exit_price(entry_direction, one_frame)
    assert exit_price is None

    # # 下降中
    # one_frame = {
    #     'open': 100.0, 'high': 130.0, 'low': 90.0, 'close': 120.0,
    #     'possible_stoploss': 80, 'band_+2σ': 140, 'band_-2σ': 85, 'stoD_3': 60, 'stoSD_3': 50
    # }
    # exit_price = scalping.__decide_exit_price(entry_direction, one_frame)
    # assert exit_price is None

    # - - - - - - - - - - - - - - - - - - - -
    #             short entry
    # - - - - - - - - - - - - - - - - - - - -
    # 下降中
    entry_direction = 'short'
    one_frame = {
        'open': 100.0, 'high': 110.0, 'low': 80.0, 'close': 90.0,
        'possible_stoploss': 120, 'band_+2σ': 130, 'band_-2σ': 70, 'stoD_3': 40, 'stoSD_3': 50
    }
    exit_price = scalping.__decide_exit_price(entry_direction, one_frame)
    assert exit_price is None

def test_new_stoploss_price():
    case_dicts = [
        {'position_type': 'long', 'current_sup': 120.0, 'current_regist': 140.0, 'old_stoploss': np.nan},
        {'position_type': 'long', 'current_sup': 120.0, 'current_regist': 140.0, 'old_stoploss': 110.0},
        {'position_type': 'long', 'current_sup': 120.0, 'current_regist': 140.0, 'old_stoploss': 130.0},
        {'position_type': 'short', 'current_sup': 120.0, 'current_regist': 140.0, 'old_stoploss': np.nan},
        {'position_type': 'short', 'current_sup': 120.0, 'current_regist': 140.0, 'old_stoploss': 150.0},
        {'position_type': 'short', 'current_sup': 120.0, 'current_regist': 140.0, 'old_stoploss': 130.0}
    ]
    results = [
        case_dicts[0]['current_sup'],
        case_dicts[1]['current_sup'],
        np.nan,
        case_dicts[3]['current_regist'],
        case_dicts[4]['current_regist'],
        np.nan
    ]
    for case_dict, result in zip(case_dicts, results):
        stoploss = scalping.new_stoploss_price(**case_dict)
        assert stoploss == result or stoploss is result


if __name__ == '__main__':
    unittest.main()
