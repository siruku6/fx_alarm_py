# from unittest.mock import patch
import pytest

import numpy as np
import pandas as pd

from models.trade_rules.super_trend import SuperTrend


@pytest.fixture(name='st_instance', scope='module', autouse=True)
def fixture_super_trend():
    yield SuperTrend()


class TestGenerateAverageTrueRange:
    @pytest.fixture(name='dummy_candles', scope='module', autouse=False)
    def fixture_dummy_candles(self) -> pd.DataFrame:
        df_prepend: pd.DataFrame = pd.DataFrame(np.full([10, 3], 100.0), columns=['high', 'low', 'close'])
        dummy: pd.DataFrame = pd.DataFrame(
            {
                'high': [101.0, 101.0, 101.0],
                'low': [90.0, 99.0, 90.0],
                'close': [91.0, 100.0, 95.0],
                'expected_atr': [1.539631, 2.668424, 3.734703]
            }
        )
        return df_prepend.append(dummy)

    def test_default(self, st_instance: SuperTrend, dummy_candles: pd.DataFrame):
        result: pd.Series = st_instance._SuperTrend__generate_average_true_range(dummy_candles)
        expected: pd.Series = dummy_candles['expected_atr']
        pd.testing.assert_series_equal(result[-3:], expected[-3:], check_names=False)


class TestAdjustBandsAndTrend:
    @pytest.fixture(name='dummy_df', scope='module', autouse=False)
    def fixture_dummy_df(self) -> pd.DataFrame:
        """
            row0: is not going to be changed
            row1: The trend changes from down to up
            row2: overwrite lower_band with previous lower_band
            row3: is not going to be changed
            row4: overwrite upper_band with previous upper_band
            row5: The trend changes from down to up
            row6: is not going to be changed
        """
        dummy_df: pd.DataFrame = pd.DataFrame(
            {
                # NOTE: These rows cover all combinations of conditions in the method '__adjust_bands_and_trend'
                'close': [100.5, 101.5, 100.5, 100.5, 99.0, 100.5, 100.5],
                'is_up_trend': np.full(7, False),
                'st_upper_band': [101.0, 101.6, 101.0, 101.0, 101.0, 101.5, 101.0],
                'st_lower_band': [100.0, 100.0, 99.00, 100.1, 98.00, 100.0, 100.0],
                'expected_is_up_trend': [False, True, True, True, False, False, False],
                'expected_upper_band': [101.0, 101.6, 101.0, 101.0, 101.0, 101.0, 101.0],
                'expected_lower_band': [100.0, 100.0, 100.0, 100.1, 98.00, 100.0, 100.0],
            }
        )
        return dummy_df

    def test_default(self, st_instance: SuperTrend, dummy_df: pd.DataFrame):
        upper_band: pd.Series
        lower_band: pd.Series
        is_up_trend: pd.Series
        upper_band, lower_band, is_up_trend = st_instance._SuperTrend__adjust_bands_and_trend(dummy_df)

        expected_upper_band: pd.Series = dummy_df['expected_upper_band']
        expected_lower_band: pd.Series = dummy_df['expected_lower_band']
        expected_is_up_trend: pd.Series = dummy_df['expected_is_up_trend']

        pd.testing.assert_series_equal(upper_band, expected_upper_band, check_names=False)
        pd.testing.assert_series_equal(lower_band, expected_lower_band, check_names=False)
        pd.testing.assert_series_equal(is_up_trend, expected_is_up_trend, check_names=False)


class TestEraseUnnecessaryBand:
    @pytest.fixture(name='dummy_df', scope='module', autouse=False)
    def fixture_dummy_df(self) -> pd.DataFrame:
        dummy_df: pd.DataFrame = pd.DataFrame(
            {
                'is_up_trend': [False, True, False, True],
                'st_upper_band': [101.0, 101.0, 101.0, 101.0],
                'st_lower_band': [100.0, 100.0, 100.0, 100.0],
                'expected_upper_band': [101.0, np.nan, 101.0, np.nan],
                'expected_lower_band': [np.nan, 100.0, np.nan, 100.0],
            }
        )
        return dummy_df

    def test_default(self, st_instance: SuperTrend, dummy_df: pd.DataFrame):
        upper_band: pd.Series
        lower_band: pd.Series
        upper_band, lower_band = st_instance._SuperTrend__erase_unnecessary_band(
            dummy_df['st_upper_band'],
            dummy_df['st_lower_band'],
            dummy_df['is_up_trend'],
        )
        expected_upper_band: pd.Series = dummy_df['expected_upper_band']
        expected_lower_band: pd.Series = dummy_df['expected_lower_band']

        pd.testing.assert_series_equal(upper_band, expected_upper_band, check_names=False)
        pd.testing.assert_series_equal(lower_band, expected_lower_band, check_names=False)
