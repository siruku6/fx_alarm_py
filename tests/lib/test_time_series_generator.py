from typing import List

import numpy as np
import pandas as pd
import pytest

from src.lib.time_series_generator import (  # generate_ema_allows_column,
    generate_band_expansion_column,
    generate_following_trend_column,
    generate_getting_steeper_column,
    generate_in_bands_column,
    generate_thrust_column,
)


@pytest.fixture(name="dummy_sigmas", scope="module")
def fixture_dummy_sigmas() -> pd.DataFrame:
    return pd.DataFrame.from_dict(
        [
            {"sigma*2_band": 110.001, "sigma*-2_band": 108.509},
            {"sigma*2_band": 110.1, "sigma*-2_band": 108.631},
            {"sigma*2_band": 110.013, "sigma*-2_band": 108.3},
            {"sigma*2_band": 110.191, "sigma*-2_band": 108.6},
        ],
        orient="columns",
    )


@pytest.fixture(name="dummy_mas", scope="module")
def fixture_dummy_mas() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "20SMA": [98.264, 101.765, 101.891, 100.253, 100.129],
            "10EMA": [98.264, 101.965, 102.191, 100.453, 100.029],
        }
    )


@pytest.fixture(name="dummy_trends", scope="module")
def fixture_dummy_trend() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "bull": [None, True, False, False, True],
            "bear": [None, False, True, True, False],
        }
    )


class TestGenerateThrustColumn:
    def test_swing(self, dummy_trend_candles: List[dict]):
        dummy_df: pd.DataFrame = pd.DataFrame.from_dict(
            dummy_trend_candles,
            orient="columns",
        )
        result: pd.Series = generate_thrust_column(
            "swing",
            candles=dummy_df[["high", "low"]],
            trend=dummy_df[["bull", "bear"]],
            indicators=None,
        )
        pd.testing.assert_series_equal(dummy_df["thrust"].rename(None), result)

    @pytest.fixture(name="candle_with_10ema")
    def fixture_candle_with_10ema(self) -> pd.DataFrame:
        return [
            # ------ bull pattern ------
            {"high": 109.0, "low": 108.3, "10EMA": 108.5, "trend": None, "thrust": None},
            {"high": 109.0, "low": 108.3, "10EMA": 108.5, "trend": None, "thrust": None},
            {"high": 109.0, "low": 108.6, "10EMA": 108.5, "trend": None, "thrust": None},
            {"high": 109.0, "low": 108.3, "10EMA": 108.5, "trend": "bull", "thrust": "long"},
            {"high": 109.0, "low": 108.3, "10EMA": 108.5, "trend": "bull", "thrust": "long"},
            {"high": 108.4, "low": 108.3, "10EMA": 108.5, "trend": "bull", "thrust": "long"},
            # NOTE: `leave_from_ema` is not seen
            {"high": 109.0, "low": 108.3, "10EMA": 108.5, "trend": "bull", "thrust": None},
            # ------ bear pattern ------
            {"high": 109.0, "low": 108.3, "10EMA": 108.5, "trend": None, "thrust": None},
            {"high": 109.0, "low": 108.3, "10EMA": 108.5, "trend": None, "thrust": None},
            {"high": 108.0, "low": 108.3, "10EMA": 108.5, "trend": None, "thrust": None},
            {"high": 109.0, "low": 108.3, "10EMA": 108.5, "trend": "bear", "thrust": "short"},
            {"high": 109.0, "low": 108.3, "10EMA": 108.5, "trend": "bear", "thrust": "short"},
            {"high": 109.0, "low": 108.6, "10EMA": 108.5, "trend": "bear", "thrust": "short"},
            # NOTE: `leave_from_ema` is not seen
            {"high": 109.0, "low": 108.3, "10EMA": 108.5, "trend": "bear", "thrust": None},
        ]

    def test_scalping(self, candle_with_10ema: List[dict]):
        dummy_df: pd.DataFrame = pd.DataFrame.from_dict(
            candle_with_10ema,
            orient="columns",
        )
        result: pd.Series = generate_thrust_column(
            "scalping",
            candles=dummy_df[["high", "low", "trend"]],
            trend=None,
            indicators=dummy_df[["10EMA"]],
        )
        pd.testing.assert_series_equal(dummy_df["thrust"].rename(None), result)


class TestGenerateInBandsColumn:
    @pytest.fixture(name="dummy_entrybale_prices", scope="module")
    def fixture_entrybale_prices(self) -> pd.Series:
        return pd.Series([109.2, 108.58, 110.02, 110.191])

    def test_4_patterns(
        self,
        dummy_sigmas: pd.DataFrame,
        dummy_entrybale_prices: pd.DataFrame,
    ):
        indicators = pd.DataFrame([])
        indicators["sigma*2_band"] = dummy_sigmas["sigma*2_band"]
        indicators["sigma*-2_band"] = dummy_sigmas["sigma*-2_band"]

        result: np.ndarray = generate_in_bands_column(indicators, dummy_entrybale_prices)
        expected: np.ndarray = np.array([True, False, False, False])

        np.testing.assert_array_equal(result, expected)


def test_generate_band_expansion_column(dummy_sigmas):
    result: np.ndarray = generate_band_expansion_column(df_bands=dummy_sigmas)
    expected: np.ndarray = np.array([False, False, True, False])
    np.testing.assert_array_equal(result, expected)


class TestGenerateGettingSteeperColumn:
    def test_5_patterns(self, dummy_mas: pd.DataFrame, dummy_trends: pd.DataFrame):
        result: np.ndarray = generate_getting_steeper_column(dummy_trends, dummy_mas)
        expected: np.ndarray = np.array([False, True, False, True, False])

        np.testing.assert_array_equal(result, expected)


class TestGenerateFollowingTrendColumn:
    def test_5_patterns(self, dummy_mas: pd.DataFrame, dummy_trends: pd.DataFrame):
        result: np.ndarray = generate_following_trend_column(dummy_trends, dummy_mas["20SMA"])
        expected: np.ndarray = np.array([False, True, False, True, False])

        np.testing.assert_array_equal(result, expected)
