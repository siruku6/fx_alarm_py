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
                'emaNone':      [None,   101.0, 100.0],
                'fall':         [None,   101.5,  98.0],
                'up_repulsion': ['bull', 102.0, 100.0]
            },
            columns=['trend', 'high', 'low'],
            orient='index'
        )
        ema = np.array([None, 100.0, 101.0])
        repulsion_series = scalping.generate_repulsion_column(candles=test_df, ema=ema)

        self.assertEqual(repulsion_series[0], None)
        self.assertEqual(repulsion_series[1], None)
        self.assertEqual(repulsion_series[2], 'long')

    def test_generate_down_repulsion_column(self):
        test_df = pd.DataFrame.from_dict(
            {
                'emaNone':        [None,   101.0, 101.2],
                'rise':           [None,   101.6, 101.1],
                'down_repulsion': ['bear', 100.0,  99.0]
            },
            columns=['trend', 'high', 'low'],
            orient='index'
        )
        ema = np.array([None, 102.0, 101.5])
        repulsion_series = scalping.generate_repulsion_column(candles=test_df, ema=ema)
        # import pdb; pdb.set_trace()

        self.assertEqual(repulsion_series[0], None)
        self.assertEqual(repulsion_series[1], None)
        self.assertEqual(repulsion_series[2], 'short')

    def test_is_exitable_by_stoc_cross(self):
        test_dicts = [
            {'direction': 'long', 'stod': 40, 'stosd': 90, 'exitable': True},
            {'direction': 'long', 'stod': 70, 'stosd': 80, 'exitable': True},
            {'direction': 'long', 'stod': 80, 'stosd': 70, 'exitable': False},
            {'direction': 'short', 'stod': 90, 'stosd': 40, 'exitable': True},
            {'direction': 'short', 'stod': 80, 'stosd': 70, 'exitable': True},
            {'direction': 'short', 'stod': 70, 'stosd': 80, 'exitable': False}
        ]
        for row in test_dicts:
            is_exitable = scalping.is_exitable_by_stoc_cross(
                direction=row['direction'],
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


if __name__ == '__main__':
    unittest.main()
