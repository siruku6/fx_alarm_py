from typing import List
from unittest.mock import patch

import pandas as pd
import pytest

from src.alpha_trader import AlphaTrader
from src.swing_trader import SwingTrader
from tools.trade_lab import create_trader_instance


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


@pytest.fixture(name="swing_trader_instance", scope="function")
def fixture_swing_trader_instance(set_envs, patch_is_tradeable) -> SwingTrader:
    set_envs

    with patch(
        "src.lib.instance_builder.CandleLoader._CandleLoader__select_need_request",
        return_value=False,
    ):
        swing_trader, _ = create_trader_instance(SwingTrader, operation="unittest", days=60)
    yield swing_trader
    swing_trader._oanda_interface._OandaInterface__oanda_client._OandaClient__api_client.client.close()


class TestPerform:
    def test_alpha_trader(self, alpha_trader_instance: AlphaTrader):
        default_filters: List[str] = [
            "in_the_band",
            "stoc_allows",
            "band_expansion",
        ]
        result: pd.DataFrame = alpha_trader_instance.perform("scalping", default_filters)
        expected: pd.DataFrame = pd.read_json("tests/fixtures/alpha_perform_result.json")
        pd.testing.assert_frame_equal(expected, result)

    def test_swing_trader(self, swing_trader_instance: SwingTrader):
        default_filters: List[str] = [
            "in_the_band",
            "stoc_allows",
            "band_expansion",
        ]
        result: pd.DataFrame = swing_trader_instance.perform("swing", default_filters)
        # result.to_json("tests/fixtures/swing_perform_result.json", orient="records")
        expected: pd.DataFrame = pd.read_json("tests/fixtures/swing_perform_result.json")
        pd.testing.assert_frame_equal(expected, result)
