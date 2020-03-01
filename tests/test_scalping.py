import numpy as np
import pandas as pd
import unittest
from unittest.mock import patch
import models.trade_rules.scalping as scalping

class TestScalping(unittest.TestCase):
    DummyPlus2sigma = 116
    DummyMinus2sigma = 113

    def test_exits_by_bollinger(self):
        # test-data
        df = pd.DataFrame.from_dict(
            {
                'long_over_the_band': [True, False, 116.5, 114.5, TestScalping.DummyPlus2sigma, TestScalping.DummyMinus2sigma, 'sell_exit', TestScalping.DummyPlus2sigma],
                'long_below_the_band': [True, False, 115.5, 112.5, TestScalping.DummyPlus2sigma, TestScalping.DummyMinus2sigma, 'sell_exit', TestScalping.DummyMinus2sigma],
                'short_over_the_band': [False, True, 116.5, 114.5, TestScalping.DummyPlus2sigma, TestScalping.DummyMinus2sigma, 'buy_exit', TestScalping.DummyPlus2sigma],
                'short_below_the_band': [False, True, 115.5, 112.5, TestScalping.DummyPlus2sigma, TestScalping.DummyMinus2sigma, 'buy_exit', TestScalping.DummyMinus2sigma],
            },
            columns=[
                'is_long', 'is_short', 'high', 'low', 'plus2sigma', 'minus2sigma',
                'correct_exitable', 'correct_exitable_price'
            ],
            orient='index'
        )
        exitable, exitable_price = scalping.exits_by_bollinger(
            candles=df[['high', 'low']],
            long_indexes=df.is_long, short_indexes=df.is_short,
            plus2sigma=df.plus2sigma, minus2sigma=df.minus2sigma
        )
        df['exitable'] = exitable
        df['exitable_price'] = exitable_price

        for index, row in df.iterrows():
            self.assertEqual(row['exitable'], row['correct_exitable'], index)
            self.assertEqual(row['exitable_price'], row['correct_exitable_price'], index)

    def test_no_exits_by_bollinger(self):
        # test-data
        df = pd.DataFrame.from_dict(
            {
                'long_in_the_band': [True, False, 115.5, 114.5, TestScalping.DummyPlus2sigma, TestScalping.DummyMinus2sigma, np.nan, np.nan],
                'short_in_the_band': [False, True, 115.5, 114.5, TestScalping.DummyPlus2sigma, TestScalping.DummyMinus2sigma, np.nan, np.nan],
                'no_in_the_band': [False, False, 115.5, 114.5, TestScalping.DummyPlus2sigma, TestScalping.DummyMinus2sigma, np.nan, np.nan],
                'no_over_the_band': [False, False, 116.5, 114.5, TestScalping.DummyPlus2sigma, TestScalping.DummyMinus2sigma, np.nan, np.nan],
                'no_below_the_band': [False, False, 115.5, 112.5, TestScalping.DummyPlus2sigma, TestScalping.DummyMinus2sigma, np.nan, np.nan],
            },
            columns=[
                'is_long', 'is_short', 'high', 'low', 'plus2sigma', 'minus2sigma',
                'correct_exitable', 'correct_exitable_price'
            ],
            orient='index'
        )
        exitable, exitable_price = scalping.exits_by_bollinger(
            candles=df[['high', 'low']],
            long_indexes=df.is_long, short_indexes=df.is_short,
            plus2sigma=df.plus2sigma, minus2sigma=df.minus2sigma
        )
        df['exitable'] = exitable
        df['exitable_price'] = exitable_price

        for index, row in df.iterrows():
            self.assertTrue(np.isnan(row['exitable']), index)
            self.assertTrue(np.isnan(row['exitable_price']), index)

if __name__ == '__main__':
    unittest.main()
