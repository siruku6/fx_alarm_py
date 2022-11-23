import datetime
import os
from unittest.mock import call, patch

from moto import mock_sns
import numpy as np
import pandas as pd
import pytest

import src.real_trader as real
from src.trader_config import FILTER_ELEMENTS
from tests.conftest import fixture_sns
from tools.trade_lab import create_trader_instance


@pytest.fixture(scope="module")
def real_trader_client():
    tr_instance, _ = create_trader_instance(real.RealTrader, operation="unittest", days=60)
    yield tr_instance


@pytest.fixture(scope="module")
def dummy_candles(d1_stoc_dummy):
    d1_stoc_df = pd.DataFrame.from_dict(d1_stoc_dummy)
    candles = d1_stoc_df[["open", "high", "low", "close"]].copy()
    candles.loc[:, "time"] = pd.date_range(end="2020-05-07", periods=100)
    # candles.set_index('time', inplace=True)
    yield candles


# INFO:
#   fixture の使い方 https://qiita.com/_akiyama_/items/9ead227227d669b0564e
@pytest.fixture(scope="module")
def dummy_indicators(real_trader_client, dummy_candles):
    real_trader_client._ana.calc_indicators(dummy_candles, long_span_candles=dummy_candles)
    yield real_trader_client._ana.get_indicators()


@pytest.fixture(name="df_support_and_resistance", scope="session")
def fixture_support_and_resistance() -> pd.DataFrame:
    yield pd.DataFrame({"support": [98.0, 100.0], "regist": [123.456, 112.233]})


class TestInit:
    def test_not_tradeable(self):
        with patch(
            "src.client_manager.ClientManager.call_oanda", return_value={"tradeable": False}
        ):
            real_trader, _ = create_trader_instance(real.RealTrader, operation="live", days=60)
        assert real_trader is None


def test_not_entry(real_trader_client, dummy_candles, dummy_indicators):
    # real_trader_client._ana.calc_indicators(dummy_candles, long_span_candles=dummy_candles)
    indicators = dummy_indicators

    # Example: 最後の損失から1時間が経過していない場合
    no_time_since_lastloss = datetime.timedelta(hours=0)
    with patch(
        "src.real_trader.RealTrader._RealTrader__since_last_loss",
        return_value=no_time_since_lastloss,
    ):
        result = real_trader_client._RealTrader__drive_entry_process(
            dummy_candles, dummy_candles.iloc[-1], indicators, indicators.iloc[-1]
        )
        assert result is False

    # Example: 最後の損失から1時間が経過しているが、Entry条件を満たしていない(preconditions_allows が False)
    two_hours_since_lastloss = datetime.timedelta(hours=2)
    columns = ["trend", "preconditions_allows", "time"] + FILTER_ELEMENTS.copy()
    tmp_dummy_candles = pd.DataFrame([[False for _ in columns]], columns=columns)
    with patch(
        "src.real_trader.RealTrader._RealTrader__since_last_loss",
        return_value=two_hours_since_lastloss,
    ):
        result = real_trader_client._RealTrader__drive_entry_process(
            tmp_dummy_candles, tmp_dummy_candles.iloc[-1], indicators, indicators.iloc[-1]
        )
        assert result is False

    # Example: 最後の損失から1時間が経過し、preconditions_allows が True だが、 repulsion なし
    tmp_dummy_candles = dummy_candles.tail(10).copy()
    tmp_dummy_candles.loc[:, "preconditions_allows"] = True
    tmp_dummy_candles.loc[:, "trend"] = "bull"
    tmp_dummy_candles.loc[:, "time"] = "xxxx-xx-xx xx:xx"
    repulsion = None
    with patch(
        "src.real_trader.RealTrader._RealTrader__since_last_loss",
        return_value=two_hours_since_lastloss,
    ):
        with patch("src.trade_rules.scalping.repulsion_exist", return_value=repulsion):
            result = real_trader_client._RealTrader__drive_entry_process(
                tmp_dummy_candles, tmp_dummy_candles.iloc[-1], indicators, indicators.iloc[-1]
            )
            assert result is False

    # Example: 最後の損失から1時間が経過し、preconditions_allows が True で、 repulsion あり
    with patch(
        "src.real_trader.RealTrader._RealTrader__since_last_loss",
        return_value=two_hours_since_lastloss,
    ):
        repulsion = "long"
        with patch("src.trade_rules.scalping.repulsion_exist", return_value=repulsion):
            with patch("src.real_trader.RealTrader._create_position") as mock:
                last_indicators = indicators.iloc[-1]
                result = real_trader_client._RealTrader__drive_entry_process(
                    tmp_dummy_candles, tmp_dummy_candles.iloc[-1], indicators, last_indicators
                )
                assert result is repulsion

    pd.testing.assert_series_equal(mock.call_args[0][0], tmp_dummy_candles.iloc[-2])
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


def test__trail_stoploss(real_trader_client):
    new_stop = 111.111
    dummy_trade_id = "999"
    real_trader_client._client._ClientManager__oanda_client._OandaClient__trade_ids = [
        dummy_trade_id
    ]
    data = {"stopLoss": {"timeInForce": "GTC", "price": str(new_stop)[:7]}}

    with patch("oandapyV20.endpoints.trades.TradeCRCDO") as mock:
        with patch("oandapyV20.API.request", return_value=""):
            real_trader_client._trail_stoploss(new_stop)

    mock.assert_called_with(
        accountID=os.environ.get("OANDA_ACCOUNT_ID"), tradeID=dummy_trade_id, data=data
    )


# class TestDriveTrailForSwing:
class TestDriveTrailProcess:
    def real_trader(self, stoploss_strategy_name: str):
        os.environ["STOPLOSS_STRATEGY"] = stoploss_strategy_name
        real_trader, _ = create_trader_instance(real.RealTrader, operation="unittest", days=60)
        return real_trader

    # NOTE: stoploss is going to be set by step_trailing
    def test_no_position_with_step_trailing(self, dummy_candles, df_support_and_resistance):
        real_trader_client: real.RealTrader = self.real_trader("step")
        real_trader_client._set_position({"type": "none"})

        with patch("src.real_trader.RealTrader._trail_stoploss") as mock:
            real_trader_client._RealTrader__drive_trail_process(
                dummy_candles.iloc[-2, :], df_support_and_resistance.iloc[-1]
            )

            mock.assert_not_called()

    def test_long_position_with_step_trailing(self, dummy_candles, df_support_and_resistance):
        real_trader_client: real.RealTrader = self.real_trader("step")
        real_trader_client._set_position({"type": "long", "stoploss": 98.765})

        with patch("src.real_trader.RealTrader._trail_stoploss") as mock:
            real_trader_client._RealTrader__drive_trail_process(
                dummy_candles.iloc[-2, :], df_support_and_resistance.iloc[-1]
            )
            new_stop: float = (
                dummy_candles.iloc[-2]["low"] - real_trader_client.config.stoploss_buffer_pips
            )

            mock.assert_called_once_with(new_stop=round(new_stop, 3))

    def test_short_position_with_step_trailing(self, dummy_candles, df_support_and_resistance):
        real_trader_client: real.RealTrader = self.real_trader("step")
        real_trader_client._set_position({"type": "short", "stoploss": 140.012})

        with patch("src.real_trader.RealTrader._trail_stoploss") as mock:
            real_trader_client._RealTrader__drive_trail_process(
                dummy_candles.iloc[-2, :], df_support_and_resistance.iloc[-1]
            )
            new_stop: float = (
                dummy_candles.iloc[-2]["high"]
                + real_trader_client.config.stoploss_buffer_pips
                + real_trader_client.config.static_spread
            )

            mock.assert_called_once_with(new_stop=round(new_stop, 3))

    # NOTE: stoploss is going to be set by support_or_resistance
    def test_no_position_with_support(self, dummy_candles, df_support_and_resistance):
        real_trader_client: real.RealTrader = self.real_trader("support")
        real_trader_client._position = {"type": "none"}

        with patch("src.real_trader.RealTrader._trail_stoploss") as mock:
            real_trader_client._RealTrader__drive_trail_process(
                dummy_candles.iloc[-2, :], df_support_and_resistance.iloc[-1]
            )
            mock.assert_not_called()

    def test_long_position_with_support(
        self, real_trader_client, dummy_candles, df_support_and_resistance
    ):
        real_trader_client: real.RealTrader = self.real_trader("support")
        real_trader_client._position = {"type": "long", "stoploss": 99.5}

        with patch("src.real_trader.RealTrader._trail_stoploss") as mock:
            real_trader_client._RealTrader__drive_trail_process(
                dummy_candles.iloc[-2, :], df_support_and_resistance.iloc[-1]
            )
            mock.assert_called_once_with(new_stop=100.0)

    def test_short_position_with_support(
        self, real_trader_client, dummy_candles, df_support_and_resistance
    ):
        real_trader_client: real.RealTrader = self.real_trader("support")
        real_trader_client._position = {"type": "short", "stoploss": 113.5}

        with patch("src.real_trader.RealTrader._trail_stoploss") as mock:
            real_trader_client._RealTrader__drive_trail_process(
                dummy_candles.iloc[-2, :], df_support_and_resistance.iloc[-1]
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
        with patch("src.clients.oanda_client.OandaClient.request_open_trades", return_value=[]):
            pos = real_trader_client._RealTrader__fetch_current_position()
        assert pos == {"type": "none"}

    def test_short_position(self, real_trader_client, dummy_open_trades):
        with patch(
            "src.clients.oanda_client.OandaClient.request_open_trades",
            return_value=dummy_open_trades,
        ):
            pos = real_trader_client._RealTrader__fetch_current_position()
        assert isinstance(pos, dict)
        assert pos["type"] == "short"
        assert isinstance(pos["price"], float)
        assert isinstance(pos["stoploss"], float)

    def test_long_position(self, real_trader_client, dummy_long_without_stoploss_trades):
        with patch(
            "src.clients.oanda_client.OandaClient.request_open_trades",
            return_value=dummy_long_without_stoploss_trades,
        ):
            pos = real_trader_client._RealTrader__fetch_current_position()
        assert isinstance(pos, dict)
        assert pos["type"] == "long"
        assert isinstance(pos["price"], float)
        assert "stoploss" not in pos


def test___since_last_loss(real_trader_client):
    # Context: last loss is far from current
    dummy_transactions = pd.DataFrame({"pl": [121.03], "time": ["2019-02-01T12:15:02.436718568Z"]})
    with patch(
        "src.client_manager.ClientManager._ClientManager__request_latest_transactions",
        return_value=dummy_transactions,
    ):
        time_since_loss = real_trader_client._RealTrader__since_last_loss()
    assert time_since_loss == datetime.timedelta(hours=99)

    # Context: Within 1 hour after last loss
    dummy_transactions = pd.DataFrame(
        {
            "pl": [-121.03],
            "time": [datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.xxxxxxxxxZ")],
        }
    )
    with patch(
        "src.client_manager.ClientManager._ClientManager__request_latest_transactions",
        return_value=dummy_transactions,
    ):
        time_since_loss = real_trader_client._RealTrader__since_last_loss()
    assert time_since_loss < datetime.timedelta(hours=1)


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
