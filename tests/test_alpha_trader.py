from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal
import pytest

from src.alpha_trader import AlphaTrader
from src.candle_storage import FXBase
from src.data_factory_clerk import prepare_indicators
from tools.trade_lab import create_trader_instance


@pytest.fixture(name="trader_instance", scope="function")
def fixture_trader_instance(set_envs, patch_is_tradeable) -> AlphaTrader:
    set_envs
    patch_is_tradeable

    _trader, _ = create_trader_instance(AlphaTrader, operation="unittest", days=60)
    yield _trader
    _trader._oanda_interface._OandaInterface__oanda_client._OandaClient__api_client.client.close()


class TestGenerateEntryColumn:
    @pytest.fixture(name="commited_df", scope="module")
    def fixture_commited_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            data=[
                [None, 123.456, "reason1", None, 1234.56],
                ["long", 1.23456, "reason2", None, 12.3456],
                [None, 123.456, "reason3", None, 1234.56],
                ["short", 1.23456, "reason4", None, 12.3456],
            ],
            columns=[
                "position",
                "exitable_price",
                "exit_reason",
                "entryable_price",
                "possible_stoploss",
            ],
        )

    def test_columns_adding(self, trader_instance: AlphaTrader, commited_df: pd.DataFrame):
        indicators: pd.DataFrame = prepare_indicators()
        candles: pd.DataFrame = FXBase.get_candles().copy()
        candles.loc[:, "entryable"] = True
        candles.loc[:, "entryable_price"] = 100.0

        # TODO: The result of merge should be also tested!
        with patch("pandas.merge", return_value=candles):
            with patch(
                "src.trade_rules.scalping.commit_positions_by_loop", return_value=commited_df
            ):  # as mock:
                trader_instance._AlphaTrader__generate_entry_column(candles, indicators)

        expected: pd.DataFrame = commited_df.rename(columns={"entryable_price": "entry_price"})
        assert_frame_equal(
            candles.loc[
                0:3,
                ["position", "exitable_price", "exit_reason", "entry_price", "possible_stoploss"],
            ],
            expected,
        )
