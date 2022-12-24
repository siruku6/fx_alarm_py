from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from src.real_trader import RealTrader
from src.swing_trader import SwingTrader
from tools.trade_lab import create_trader_instance


@pytest.fixture(name="trader_instance", scope="module")
def fixture_trader_instance(set_envs) -> SwingTrader:
    set_envs

    _trader, _ = create_trader_instance(SwingTrader, operation="unittest", days=60)
    yield _trader
    _trader._oanda_interface._OandaInterface__oanda_client._OandaClient__api_client.client.close()


@pytest.fixture(name="real_trader_instance", scope="module")
def fixture_real_trader_instance(set_envs) -> RealTrader:
    set_envs

    real_trader, _ = create_trader_instance(RealTrader, operation="unittest", days=60)
    yield real_trader
    real_trader._oanda_interface._OandaInterface__oanda_client._OandaClient__api_client.client.close()


@pytest.fixture(scope="module")
def dummy_trend_candles():
    return pd.DataFrame.from_dict(
        [
            {"high": 110.0, "low": 108.5, "bull": False, "bear": False, "thrust": None},
            {"high": 110.0, "low": 108.5, "bull": False, "bear": False, "thrust": None},
            {"high": 110.0, "low": 108.5, "bull": False, "bear": False, "thrust": None},
            {"high": 110.0, "low": 108.5, "bull": False, "bear": False, "thrust": None},
            {"high": 110.0, "low": 108.5, "bull": False, "bear": False, "thrust": None},
            {"high": 110.0, "low": 108.5, "bull": False, "bear": False, "thrust": None},
            {"high": 110.0, "low": 108.5, "bull": False, "bear": False, "thrust": None},
            {"high": 110.0, "low": 108.5, "bull": False, "bear": False, "thrust": None},
            {"high": 110.0, "low": 108.5, "bull": False, "bear": False, "thrust": None},
            {"high": 110.0, "low": 108.5, "bull": False, "bear": False, "thrust": None},
            {"high": 111.0, "low": 108.5, "bull": True, "bear": False, "thrust": "long"},
            {"high": 110.0, "low": 107.5, "bull": False, "bear": True, "thrust": "short"},
            {"high": 111.0, "low": 108.5, "bull": True, "bear": False, "thrust": "long"},
            {"high": 110.0, "low": 107.5, "bull": False, "bear": True, "thrust": "short"},
            {"high": 112.0, "low": 106.5, "bull": False, "bear": False, "thrust": None},
        ],
        orient="columns",
    )


def test__accurize_entry_prices():
    pass
    # self.__trader._Trader__accurize_entry_prices()


@pytest.fixture(name="dummy_candles", scope="module")
def fixture_dummy_candles():
    return pd.DataFrame.from_dict(
        [
            {"open": 100.1, "high": 100.3, "low": 100.0, "close": 100.2},
            {"open": 100.2, "high": 100.4, "low": 100.1, "close": 100.3},
        ]
    )


def test__generate_thrust_column(real_trader_instance, dummy_trend_candles):
    dummy_df = dummy_trend_candles
    result: pd.Series = real_trader_instance._generate_thrust_column(
        candles=dummy_df[["high", "low"]], trend=dummy_df[["bull", "bear"]]
    )
    pd.testing.assert_series_equal(dummy_df["thrust"].rename(None), result)


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


class TestGenerateInBandsColumn:
    @pytest.fixture(name="dummy_candles", scope="module")
    def fixture_dummy_candles(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "close": [109.2, 108.58, 110.02, 110.191],
                "thrust": ["dummy", "dummy", "dummy", "dummy"],
            }
        )

    @pytest.fixture(name="dummy_entrybale_prices", scope="module")
    def fixture_entrybale_prices(self) -> pd.Series:
        return pd.Series([109.2, 108.58, 110.02, 110.191])

    def test_4_patterns(
        self,
        trader_instance: SwingTrader,
        dummy_sigmas: pd.DataFrame,
        dummy_entrybale_prices: pd.DataFrame,
        dummy_candles: pd.DataFrame,
    ):
        trader_instance._indicators = pd.DataFrame([])
        trader_instance._indicators["sigma*2_band"] = dummy_sigmas["sigma*2_band"]
        trader_instance._indicators["sigma*-2_band"] = dummy_sigmas["sigma*-2_band"]
        with patch(
            "src.swing_trader.SwingTrader._generate_entryable_price",
            return_value=dummy_entrybale_prices,
        ):
            result: np.ndarray = trader_instance._Trader__generate_in_bands_column(dummy_candles)
        expected: np.ndarray = np.array([True, False, False, False])

        np.testing.assert_array_equal(result, expected)


def test___generate_band_expansion_column(real_trader_instance, dummy_sigmas):
    result: np.ndarray = real_trader_instance._Trader__generate_band_expansion_column(
        df_bands=dummy_sigmas
    )
    expected: np.ndarray = np.array([False, False, True, False])
    np.testing.assert_array_equal(result, expected)


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


class TestGenerateGettingSteeperColumn:
    def test_5_patterns(
        self, trader_instance: SwingTrader, dummy_mas: pd.DataFrame, dummy_trends: pd.DataFrame
    ):
        trader_instance._indicators = dummy_mas
        result: np.ndarray = trader_instance._Trader__generate_getting_steeper_column(dummy_trends)
        expected: np.ndarray = np.array([False, True, False, True, False])

        np.testing.assert_array_equal(result, expected)


class TestGenerateFollowingTrendColumn:
    def test_5_patterns(
        self, trader_instance: SwingTrader, dummy_mas: pd.DataFrame, dummy_trends: pd.DataFrame
    ):
        trader_instance._indicators = dummy_mas
        result: np.ndarray = trader_instance._Trader__generate_following_trend_column(dummy_trends)
        expected: np.ndarray = np.array([False, True, False, True, False])

        np.testing.assert_array_equal(result, expected)


class TestMarkEntryableRows:
    def test_default(self, trader_instance: SwingTrader, dummy_trend_candles: pd.DataFrame):
        trader_instance.config.set_entry_rules("entry_filters", ["in_the_band", "band_expansion"])

        candles: pd.DataFrame = dummy_trend_candles.copy()
        candles: pd.DataFrame = candles.assign(in_the_band=False, band_expansion=False)
        candles.loc[10:12, "in_the_band"] = True
        candles.loc[11:, "band_expansion"] = True

        trader_instance._mark_entryable_rows(candles)
        expected: pd.Series = pd.Series(
            [
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                candles.loc[11, "thrust"],
                candles.loc[12, "thrust"],
                None,
                None,
            ],
            name="entryable",
        )

        pd.testing.assert_series_equal(candles["entryable"], expected)
