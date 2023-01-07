from datetime import datetime, timedelta
import os
from typing import Any, Dict, List
from unittest.mock import call, patch

from moto import mock_sns
import numpy as np
import pandas as pd
import pytest

from src.analyzer import Analyzer
from src.real_trader import Position, RealTrader
from src.trader_config import FILTER_ELEMENTS
from tests.conftest import fixture_sns
from tools.trade_lab import create_trader_instance


@pytest.fixture(scope="function")
def real_trader_client(patch_is_tradeable):
    tr_instance, _ = create_trader_instance(RealTrader, operation="unittest", days=60)
    yield tr_instance


@pytest.fixture(scope="module")
def dummy_candles(d1_stoc_dummy):
    d1_stoc_df = pd.DataFrame.from_dict(d1_stoc_dummy)
    candles = d1_stoc_df[["open", "high", "low", "close"]].copy()
    candles.loc[:, "time"] = pd.date_range(end="2020-05-07", periods=100)
    # candles.set_index('time', inplace=True)
    yield candles


@pytest.fixture(scope="module")
def dummy_indicators(dummy_candles):
    ana = Analyzer()
    ana.calc_indicators(dummy_candles, long_span_candles=dummy_candles)
    yield ana.get_indicators()


@pytest.fixture(name="df_support_and_resistance", scope="session")
def fixture_support_and_resistance() -> pd.DataFrame:
    yield pd.DataFrame({"support": [98.0, 100.0], "regist": [123.456, 112.233]})


@pytest.fixture(name="dummy_position", scope="function")
def fixture_dummy_position() -> Position:
    return Position(
        id="9999",
        type="long",
        price=123.456,
        openTime="2016-10-28T14:28:05.231759081Z",
        stoploss=123.123,
    )


class TestInit:
    def test_not_tradeable(self):
        with patch(
            "tools.trade_lab.is_tradeable",
            return_value={"info": "not tradeable", "tradeable": False},
        ):
            real_trader, _ = create_trader_instance(RealTrader, operation="live", days=60)
        assert real_trader is None


class TestPlayScalpingTrade:
    @pytest.fixture(name="df_past_candles")
    def fixture_past_candles(self, past_usd_candles: List[Dict[str, Any]]) -> pd.DataFrame:
        df_candles: pd.DataFrame = pd.DataFrame(past_usd_candles)
        return df_candles

    @pytest.fixture(name="dummy_indicators")
    def fixture_indicators(self, df_past_candles: pd.DataFrame):
        ana = Analyzer()
        ana.calc_indicators(df_past_candles)
        indicators: pd.DataFrame = ana.get_indicators()
        return indicators

    @patch(
        "src.real_trader.RealTrader._RealTrader__fetch_current_positions",
        return_value=[],
    )
    def test_without_any_position(
        self,
        _patch_fetch_current_positions,
        real_trader_client,
        df_past_candles: pd.DataFrame,
        dummy_indicators: pd.DataFrame,
    ):
        """
        Condition:
            - There is no open position,
            - Doesn't create position.
        """
        df_candles: pd.DataFrame = pd.DataFrame(df_past_candles)

        with patch(
            "src.real_trader.RealTrader._RealTrader__drive_entry_process",
            return_value=None,
        ) as mock:
            real_trader_client._RealTrader__play_scalping_trade(df_candles, dummy_indicators)

        mock.assert_called_once()

    @patch(
        "src.real_trader.RealTrader._RealTrader__fetch_current_positions",
        return_value=[],
    )
    @patch(
        "src.real_trader.scalping.repulsion_exist",
        return_value="long",
    )
    @patch(
        "src.real_trader.RealTrader._RealTrader__since_last_loss",
        return_value=timedelta(hours=99),
    )
    def test_without_any_position_create_position(
        self,
        _patch_fetch_current_positions,
        _patch_repulsion_exist,
        _patch_since_last_loss,
        real_trader_client,
        df_past_candles: pd.DataFrame,
        dummy_indicators: pd.DataFrame,
    ):
        """
        Condition:
            - There is no open position,
            - Create position.
        """
        df_candles: pd.DataFrame = pd.DataFrame(df_past_candles)
        df_candles["preconditions_allows"] = True
        df_candles["trend"] = "long"

        with patch(
            "src.real_trader.RealTrader._create_position",
            return_value=None,
        ) as mock:
            real_trader_client._RealTrader__play_scalping_trade(df_candles, dummy_indicators)

        mock.assert_called_once()


class TestDriveEntryProcess:
    def test_no_time_since_lastloss(self, real_trader_client, dummy_candles, dummy_indicators):
        """
        Example: An hour hasn't passed since last loss.
        """
        indicators = dummy_indicators

        no_time_since_lastloss = timedelta(hours=0)
        with patch(
            "src.real_trader.RealTrader._RealTrader__since_last_loss",
            return_value=no_time_since_lastloss,
        ):
            result = real_trader_client._RealTrader__drive_entry_process(
                dummy_candles, dummy_candles.iloc[-1], indicators, indicators.iloc[-1]
            )
            assert result is None

    def test_preconditions_not_allows(self, real_trader_client, dummy_indicators):
        """
        Example: An hour has passed since last loss, but preconditions don't allow.
        """
        indicators = dummy_indicators
        two_hours_since_lastloss = timedelta(hours=2)
        columns = ["trend", "preconditions_allows", "time"] + FILTER_ELEMENTS.copy()
        tmp_dummy_candles = pd.DataFrame([[False for _ in columns]], columns=columns)
        with patch(
            "src.real_trader.RealTrader._RealTrader__since_last_loss",
            return_value=two_hours_since_lastloss,
        ):
            result = real_trader_client._RealTrader__drive_entry_process(
                tmp_dummy_candles, tmp_dummy_candles.iloc[-1], indicators, indicators.iloc[-1]
            )
            assert result is None

    @pytest.fixture(name="tmp_dummy_allowed_candles")
    def fixture_tmp_dummy_allowed_candles(self, dummy_candles):
        """
        dummy_candles with "preconditions_allows" assigned True
        """
        columns = ["trend", "preconditions_allows", "time"] + FILTER_ELEMENTS.copy()
        tmp_dummy_candles = pd.DataFrame([[False for _ in columns]], columns=columns)
        tmp_dummy_candles = dummy_candles.tail(10).copy()
        tmp_dummy_candles.loc[:, "preconditions_allows"] = True
        tmp_dummy_candles.loc[:, "trend"] = "bull"
        tmp_dummy_candles.loc[:, "time"] = "xxxx-xx-xx xx:xx"
        return tmp_dummy_candles

    def test_no_repulsion(self, real_trader_client, tmp_dummy_allowed_candles, dummy_indicators):
        """
        Example:
            - An hour has passed since last loss
            - preconditions allow
            - There is no repulsion
        """
        indicators = dummy_indicators
        two_hours_since_lastloss = timedelta(hours=2)

        repulsion = None
        with patch(
            "src.real_trader.RealTrader._RealTrader__since_last_loss",
            return_value=two_hours_since_lastloss,
        ):
            with patch("src.trade_rules.scalping.repulsion_exist", return_value=repulsion):
                result = real_trader_client._RealTrader__drive_entry_process(
                    tmp_dummy_allowed_candles,
                    tmp_dummy_allowed_candles.iloc[-1],
                    indicators,
                    indicators.iloc[-1],
                )
                assert result is None

    def test_entry(self, real_trader_client, tmp_dummy_allowed_candles, dummy_indicators):
        """
        Example:
            - An hour has passed since last loss
            - preconditions allow
            - There is a repulsion
        """
        indicators = dummy_indicators
        two_hours_since_lastloss = timedelta(hours=2)

        with patch(
            "src.real_trader.RealTrader._RealTrader__since_last_loss",
            return_value=two_hours_since_lastloss,
        ):
            repulsion = "long"
            with patch("src.trade_rules.scalping.repulsion_exist", return_value=repulsion):
                with patch("src.real_trader.RealTrader._create_position") as mock:
                    last_indicators = indicators.iloc[-1]
                    result = real_trader_client._RealTrader__drive_entry_process(
                        tmp_dummy_allowed_candles,
                        tmp_dummy_allowed_candles.iloc[-1],
                        indicators,
                        last_indicators,
                    )
                    assert result is repulsion

        pd.testing.assert_series_equal(mock.call_args[0][0], tmp_dummy_allowed_candles.iloc[-2])
        assert mock.call_args[0][1] == repulsion
        pd.testing.assert_series_equal(mock.call_args[0][2], last_indicators)


@mock_sns
def test__create_position_with_indicators(
    real_trader_client,
    dummy_market_order_response,
):
    last_indicators = {"support": 120.111, "regist": 118.999}
    dummy_response = dummy_market_order_response

    fixture_sns()
    # long
    # HACK: patch imported module into mock
    with patch("oandapyV20.endpoints.orders.OrderCreate") as mock:
        with patch("oandapyV20.API.request", return_value=dummy_response):
            real_trader_client._create_position(_previous_candle_dummy(), "long", last_indicators)

    mock.assert_called_with(
        accountID=os.environ.get("OANDA_ACCOUNT_ID"),
        data=_order_response_dummy(
            "", last_indicators["support"], real_trader_client.config.get_instrument()
        ),
    )

    # short
    with patch("oandapyV20.endpoints.orders.OrderCreate") as mock:
        with patch("oandapyV20.API.request", return_value=dummy_response):
            real_trader_client._create_position(_previous_candle_dummy(), "short", last_indicators)

    mock.assert_called_with(
        accountID=os.environ.get("OANDA_ACCOUNT_ID"),
        data=_order_response_dummy(
            "-", last_indicators["regist"], real_trader_client.config.get_instrument()
        ),
    )


class TestCreatePositionWithoutIndicators:
    @mock_sns
    def test_long(self, real_trader_client, dummy_market_order_response):
        fixture_sns()

        dummy_response = dummy_market_order_response
        with patch("oandapyV20.endpoints.orders.OrderCreate") as mock:
            with patch("oandapyV20.API.request", return_value=dummy_response):
                real_trader_client._create_position(_previous_candle_dummy(), "long")

        long_stoploss = (
            _previous_candle_dummy()["low"] - real_trader_client.config.stoploss_buffer_pips
        )
        mock.assert_called_with(
            accountID=os.environ.get("OANDA_ACCOUNT_ID"),
            data=_order_response_dummy(
                "", long_stoploss, real_trader_client.config.get_instrument()
            ),
        )

    @mock_sns
    def test_short(self, real_trader_client, dummy_market_order_response):
        fixture_sns()
        dummy_response = dummy_market_order_response

        with patch("oandapyV20.endpoints.orders.OrderCreate") as mock:
            with patch("oandapyV20.API.request", return_value=dummy_response):
                real_trader_client._create_position(_previous_candle_dummy(), "short")

        short_stoploss = (
            _previous_candle_dummy()["high"]
            + real_trader_client.config.stoploss_buffer_pips
            + real_trader_client.config.static_spread
        )
        mock.assert_called_with(
            accountID=os.environ.get("OANDA_ACCOUNT_ID"),
            data=_order_response_dummy(
                "-", short_stoploss, real_trader_client.config.get_instrument()
            ),
        )


def test__trail_stoploss(real_trader_client, dummy_position):
    new_stop: float = 111.111
    data = {"stopLoss": {"timeInForce": "GTC", "price": str(new_stop)[:7]}}
    real_trader_client._positions = [dummy_position]

    with patch("oandapyV20.endpoints.trades.TradeCRCDO") as mock:
        with patch("oandapyV20.API.request", return_value={}):
            real_trader_client._trail_stoploss(new_stop)

    mock.assert_called_with(
        accountID=os.environ.get("OANDA_ACCOUNT_ID"),
        tradeID=dummy_position.id,
        data=data,
    )


# class TestDriveTrailForSwing:
class TestDriveTrailProcess:
    def real_trader(self, stoploss_strategy_name: str):
        os.environ["STOPLOSS_STRATEGY"] = stoploss_strategy_name
        real_trader, _ = create_trader_instance(RealTrader, operation="unittest", days=60)
        return real_trader

    # # NOTE: stoploss is going to be set by step_trailing
    # def test_no_position_with_step_trailing(self, dummy_candles, df_support_and_resistance):
    #     real_trader_client: RealTrader = self.real_trader("step")
    #     real_trader_client._set_position([])

    #     with patch("src.real_trader.RealTrader._trail_stoploss") as mock:
    #         real_trader_client._RealTrader__drive_trail_process(
    #             dummy_candles.iloc[-2, :], df_support_and_resistance.iloc[-1]
    #         )

    #         mock.assert_not_called()

    def test_long_position_with_step_trailing(
        self,
        patch_is_tradeable,
        dummy_candles,
        df_support_and_resistance,
    ):
        real_trader_client: RealTrader = self.real_trader("step")
        pos: Position = Position(
            id="9999",
            price=99.42,
            type="long",
            openTime="2016-10-28T14:28:05.231759081Z",
            stoploss=98.765,
        )

        with patch("src.real_trader.RealTrader._trail_stoploss") as mock:
            real_trader_client._RealTrader__drive_trail_process(
                pos,
                dummy_candles.iloc[-2, :],
                df_support_and_resistance.iloc[-1],
            )
            new_stop: float = (
                dummy_candles.iloc[-2]["low"] - real_trader_client.config.stoploss_buffer_pips
            )

            mock.assert_called_once_with(new_stop=round(new_stop, 3))

    def test_short_position_with_step_trailing(
        self,
        patch_is_tradeable,
        dummy_candles,
        df_support_and_resistance,
    ):
        real_trader_client: RealTrader = self.real_trader("step")
        pos: Position = Position(
            id="9999",
            price=139.8,
            type="short",
            openTime="2016-10-28T14:28:05.231759081Z",
            stoploss=140.012,
        )

        with patch("src.real_trader.RealTrader._trail_stoploss") as mock:
            real_trader_client._RealTrader__drive_trail_process(
                pos,
                dummy_candles.iloc[-2, :],
                df_support_and_resistance.iloc[-1],
            )
            new_stop: float = (
                dummy_candles.iloc[-2]["high"]
                + real_trader_client.config.stoploss_buffer_pips
                + real_trader_client.config.static_spread
            )

            mock.assert_called_once_with(new_stop=round(new_stop, 3))

    # # NOTE: stoploss is going to be set by support_or_resistance
    # def test_no_position_with_support(self, dummy_candles, df_support_and_resistance):
    #     real_trader_client: RealTrader = self.real_trader("support")
    #     real_trader_client._position = []

    #     with patch("src.real_trader.RealTrader._trail_stoploss") as mock:
    #         real_trader_client._RealTrader__drive_trail_process(
    #             dummy_candles.iloc[-2, :], df_support_and_resistance.iloc[-1]
    #         )
    #         mock.assert_not_called()

    def test_long_position_with_support(
        self, real_trader_client, dummy_candles, df_support_and_resistance
    ):
        real_trader_client: RealTrader = self.real_trader("support")
        pos: Position = Position(
            id="9999",
            price=101.2,
            type="long",
            openTime="2016-10-28T14:28:05.231759081Z",
            stoploss=99.5,
        )

        with patch("src.real_trader.RealTrader._trail_stoploss") as mock:
            real_trader_client._RealTrader__drive_trail_process(
                target_pos=pos,
                previous_candle=dummy_candles.iloc[-2, :],
                last_indicators=df_support_and_resistance.iloc[-1],
            )
            mock.assert_called_once_with(new_stop=100.0)

    def test_short_position_with_support(
        self, real_trader_client, dummy_candles, df_support_and_resistance
    ):
        real_trader_client: RealTrader = self.real_trader("support")
        pos: Position = Position(
            id="9999",
            price=113.2,
            type="short",
            openTime="2016-10-28T14:28:05.231759081Z",
            stoploss=113.5,
        )

        with patch("src.real_trader.RealTrader._trail_stoploss") as mock:
            real_trader_client._RealTrader__drive_trail_process(
                target_pos=pos,
                previous_candle=dummy_candles.iloc[-2, :],
                last_indicators=df_support_and_resistance.iloc[-1],
            )
            mock.assert_called_once_with(new_stop=112.233)


def test___drive_exit_process_dead_cross(real_trader_client):
    # Example: stoD_3 < stoSD_3, stoD_over_stoSD => False
    indicators = pd.DataFrame({"stoD_3": [10.000, 10.000], "stoSD_3": [30.000, 30.000]})
    last_candle = pd.DataFrame(
        [
            {
                "long_stoD": 15.694,
                "long_stoSD": 28.522,
                "stoD_over_stoSD": False,
                "time": "xxxx-xx-xx xx:xx",
            }
        ]
    ).iloc[-1]

    # Example: 'long'
    with patch("src.real_trader.RealTrader._RealTrader__settle_position") as mock:
        real_trader_client._RealTrader__drive_exit_process(
            "long", indicators, last_candle, preliminary=True
        )
        mock.assert_not_called()

        real_trader_client._RealTrader__drive_exit_process("long", indicators, last_candle)
        mock.assert_called_once()

    # Example: 'short'
    with patch("src.real_trader.RealTrader._RealTrader__settle_position") as mock:
        real_trader_client._RealTrader__drive_exit_process("short", indicators, last_candle)
        mock.assert_not_called()


def test___drive_exit_process_golden_cross(real_trader_client):
    # Example: stoD_3 > stoSD_3, stoD_over_stoSD => True
    indicators = pd.DataFrame({"stoD_3": [30.000, 30.000], "stoSD_3": [10.000, 10.000]})
    last_candle = pd.DataFrame(
        [
            {
                "long_stoD": 25.694,
                "long_stoSD": 18.522,
                "stoD_over_stoSD": True,
                "time": "xxxx-xx-xx xx:xx",
            }
        ]
    ).iloc[-1]

    with patch("src.real_trader.RealTrader._RealTrader__settle_position") as mock:
        # Example: 'long'
        real_trader_client._RealTrader__drive_exit_process("long", indicators, last_candle)
        mock.assert_not_called()

        # Example: 'short'
        real_trader_client._RealTrader__drive_exit_process("short", indicators, last_candle)
        mock.assert_called_once()

    # TODO: testcase 不足


class TestFetchCurrentPosition:
    def test_none_position(self, real_trader_client):
        with patch(
            "oanda_accessor_pyv20.OandaClient.request_open_trades",
            return_value={
                "positions": [],
                "last_transaction_id": "9999",
                "response": {"trades": [], "lastTransactionID": "2317"},
            },
        ):
            pos = real_trader_client._RealTrader__fetch_current_positions()
        assert pos == []

    def test_short_position(self, real_trader_client, dummy_open_trades):
        with patch(
            "oanda_accessor_pyv20.OandaClient.request_open_trades",
            return_value={
                "positions": dummy_open_trades,
                "last_transaction_id": "9999",
                "response": dummy_open_trades,
            },
        ):
            positions = real_trader_client._RealTrader__fetch_current_positions()
            pos = positions[-1]
        assert isinstance(positions, list)
        assert pos.type == "short"
        assert isinstance(pos.price, float)
        assert isinstance(pos.stoploss, float)

    def test_long_position(self, real_trader_client, dummy_long_without_stoploss_trades):
        with patch(
            "oanda_accessor_pyv20.OandaClient.request_open_trades",
            return_value={
                "positions": dummy_long_without_stoploss_trades,
                "last_transaction_id": "9999",
                "response": dummy_long_without_stoploss_trades,
            },
        ):
            positions = real_trader_client._RealTrader__fetch_current_positions()
            pos = positions[-1]
        assert isinstance(positions, list)
        assert pos.type == "long"
        assert isinstance(pos.price, float)
        assert pos.stoploss is None


def test___since_last_loss(real_trader_client):
    # Context: last loss is far from current
    dummy_transactions = pd.DataFrame({"pl": [121.03], "time": ["2019-02-01T12:15:02.436718568Z"]})
    with patch(
        "oanda_accessor_pyv20.OandaInterface._OandaInterface__request_latest_transactions",
        return_value=dummy_transactions,
    ):
        time_since_loss = real_trader_client._RealTrader__since_last_loss()
    assert time_since_loss == timedelta(hours=99)

    # Context: Within 1 hour after last loss
    dummy_transactions = pd.DataFrame(
        {
            "pl": [-121.03],
            "time": [datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.xxxxxxxxxZ")],
        }
    )
    with patch(
        "oanda_accessor_pyv20.OandaInterface._OandaInterface__request_latest_transactions",
        return_value=dummy_transactions,
    ):
        time_since_loss = real_trader_client._RealTrader__since_last_loss()
    assert time_since_loss < timedelta(hours=1)


def test___show_why_not_entry(real_trader_client):
    entry_filters = FILTER_ELEMENTS
    real_trader_client.config.set_entry_rules("entry_filters", entry_filters)

    columns = entry_filters.copy()
    columns.extend(["trend", "time"])

    # Example: conditions are all True
    conditions_df = pd.DataFrame([np.full(len(columns), True)], columns=columns)
    with patch("src.real_trader.RealTrader._log_skip_reason") as mock:
        real_trader_client._RealTrader__show_why_not_entry(conditions_df)
    mock.assert_not_called()

    # Example: conditions are all False
    conditions_df = pd.DataFrame([np.full(len(columns), False)], columns=columns)
    with patch("src.real_trader.RealTrader._log_skip_reason") as mock:
        real_trader_client._RealTrader__show_why_not_entry(conditions_df)

    calls = [call('c. {}: "{}" is not satisfied !'.format(False, item)) for item in entry_filters]
    mock.assert_has_calls(calls)

    # Example: conditions are all None
    conditions_df = pd.DataFrame([np.full(len(columns), None)], columns=columns)
    with patch("src.real_trader.RealTrader._log_skip_reason") as mock:
        real_trader_client._RealTrader__show_why_not_entry(conditions_df)
    mock.assert_any_call('c. {}: "trend" is None !'.format(None))


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#                      Private Methods
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def _previous_candle_dummy():
    return pd.DataFrame({"high": [100.4, 100.5, 100.6], "low": [100.1, 100.2, 100.3]}).iloc[-2]


def _order_response_dummy(entry_direction_sign, stoploss_double, instrument):
    return {
        "order": {
            "stopLossOnFill": {"timeInForce": "GTC", "price": str(stoploss_double)[:7]},
            "instrument": instrument,
            "units": "{}{}".format(entry_direction_sign, os.environ.get("UNITS") or "1"),
            "type": "MARKET",
            "positionFill": "DEFAULT",
        }
    }
