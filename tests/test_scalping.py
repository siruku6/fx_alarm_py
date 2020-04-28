import unittest
import numpy as np
import pandas as pd
# from unittest.mock import patch
import models.trade_rules.scalping as scalping

class TestScalping(unittest.TestCase):
    DummyPlus2sigma = 116
    DummyMinus2sigma = 113

    # def test_exits_by_bollinger(self):
    #     # test-data
    #     test_df = pd.DataFrame.from_dict(
    #         {
    #             'long_over_the_band': [True, False, 116.5, 114.5, TestScalping.DummyPlus2sigma, TestScalping.DummyMinus2sigma, 'sell_exit', TestScalping.DummyPlus2sigma],
    #             'long_below_the_band': [True, False, 115.5, 112.5, TestScalping.DummyPlus2sigma, TestScalping.DummyMinus2sigma, 'sell_exit', TestScalping.DummyMinus2sigma],
    #             'short_over_the_band': [False, True, 116.5, 114.5, TestScalping.DummyPlus2sigma, TestScalping.DummyMinus2sigma, 'buy_exit', TestScalping.DummyPlus2sigma],
    #             'short_below_the_band': [False, True, 115.5, 112.5, TestScalping.DummyPlus2sigma, TestScalping.DummyMinus2sigma, 'buy_exit', TestScalping.DummyMinus2sigma],
    #         },
    #         columns=[
    #             'is_long', 'is_short', 'high', 'low', 'plus2sigma', 'minus2sigma',
    #             'correct_exitable', 'correct_exitable_price'
    #         ],
    #         orient='index'
    #     )
    #     exitable, exitable_price = scalping.exits_by_bollinger(
    #         candles=test_df[['high', 'low']],
    #         long_indexes=test_df.is_long, short_indexes=test_df.is_short,
    #         plus2sigma=test_df.plus2sigma, minus2sigma=test_df.minus2sigma
    #     )
    #     test_df['exitable'] = exitable
    #     test_df['exitable_price'] = exitable_price

    #     for index, row in test_df.iterrows():
    #         self.assertEqual(row['exitable'], row['correct_exitable'], index)
    #         self.assertEqual(row['exitable_price'], row['correct_exitable_price'], index)

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
