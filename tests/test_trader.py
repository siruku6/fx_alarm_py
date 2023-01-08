from typing import List
from unittest.mock import patch

import pandas as pd
import pytest

from src.alpha_trader import AlphaTrader
from src.real_trader import RealTrader
from src.swing_trader import SwingTrader
from tools.trade_lab import create_trader_instance


@pytest.fixture(name="trader_instance", scope="function")
def fixture_trader_instance(set_envs, patch_is_tradeable) -> SwingTrader:
    set_envs

    _trader, _ = create_trader_instance(SwingTrader, operation="unittest", days=60)
    yield _trader
    _trader._oanda_interface._OandaInterface__oanda_client._OandaClient__api_client.client.close()


@pytest.fixture(name="alpha_trader_instance", scope="function")
def fixture_alpha_trader_instance(set_envs, patch_is_tradeable) -> AlphaTrader:
    set_envs

    with patch(
        "src.lib.instance_builder.CandleLoader._CandleLoader__select_need_request",
        return_value=False,
    ):
        _trader, _ = create_trader_instance(AlphaTrader, operation="unittest", days=60)
    yield _trader
    _trader._oanda_interface._OandaInterface__oanda_client._OandaClient__api_client.client.close()


@pytest.fixture(name="real_trader_instance", scope="function")
def fixture_real_trader_instance(set_envs, patch_is_tradeable) -> RealTrader:
    set_envs

    real_trader, _ = create_trader_instance(RealTrader, operation="unittest", days=60)
    yield real_trader
    real_trader._oanda_interface._OandaInterface__oanda_client._OandaClient__api_client.client.close()


class TestPerform:
    def test_default(self, alpha_trader_instance: AlphaTrader):
        default_filters: List[str] = [
            "in_the_band",
            "stoc_allows",
            "band_expansion",
        ]
        result: pd.DataFrame = alpha_trader_instance.perform("scalping", default_filters)

        expected: pd.DataFrame = pd.read_json("tests/fixtures/alpha_perform_result.json")
        pd.testing.assert_frame_equal(expected, result)


def test__accurize_entry_prices():
    pass
    # self.__trader._Trader__accurize_entry_prices()


class TestMarkEntryableRows:
    def test_default(self, trader_instance: SwingTrader, dummy_trend_candles: List[dict]):
        trader_instance.config.set_entry_rules("entry_filters", ["in_the_band", "band_expansion"])

        candles: pd.DataFrame = pd.DataFrame.from_dict(dummy_trend_candles, orient="columns")
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
