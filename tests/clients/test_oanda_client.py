import json
import os
from typing import Any, Dict, Union
from unittest.mock import patch

from moto import mock_sns
import pytest
import responses

# My-made modules
from src.clients.oanda_accessor_pyv20.api import OandaClient
from tests.conftest import fixture_sns
from tests.fixtures.past_transactions import TRANSACTION_IDS


@pytest.fixture(name="client", scope="module", autouse=True)
def oanda_client() -> OandaClient:
    client = OandaClient(instrument="USD_JPY", environment="practice")
    yield client
    # INFO: Preventing ResourceWarning: unclosed <ssl.SSLSocket
    # https://stackoverflow.com/questions/48160728/resourcewarning-unclosed-socket-in-python-3-unit-test
    client._OandaClient__api_client.client.close()


def add_simple_get_response(responses, url: str, response_json: Dict[str, Any]):
    responses.add(
        responses.GET,
        url=url,
        json=response_json,
        content_type="application/json",
        status=200,
    )


def add_simple_put_response(responses, url: str, response_json: Dict[str, Any]):
    responses.add(
        responses.PUT,
        url=url,
        json=response_json,
        content_type="application/json",
        status=200,
    )


@pytest.fixture(name="dummy_pricing_info")
def fixture_dummy_pricing_info() -> Dict[str, Any]:
    with open("tests/fixtures/api_responses/pricing_info.json", "r") as f:
        dic_pricing_info: Dict[str, Any] = json.load(f)
    return dic_pricing_info


#  - - - - - - - - - - -
#    Public methods
#  - - - - - - - - - - -
class TestRequestIsTradeable:
    @responses.activate
    def test_default(self, client: OandaClient, dummy_pricing_info: Dict[str, Any]):
        url: str = (
            f"https://api-fxpractice.oanda.com/v3/accounts/{os.environ['OANDA_ACCOUNT_ID']}/pricing"
        )
        add_simple_get_response(responses, url, response_json=dummy_pricing_info)

        res: Dict[str, Union[str, bool]] = client.request_is_tradeable()
        assert res == {"instrument": "USD_JPY", "tradeable": True}


def test_request_open_trades(client, dummy_raw_open_trades):
    assert client.last_transaction_id is None

    with patch("builtins.print"):
        with patch("pprint.pprint"):
            with patch("oandapyV20.API.request", return_value=dummy_raw_open_trades):
                _ = client.request_open_trades()
    assert isinstance(client.last_transaction_id, str)
    assert isinstance(int(client.last_transaction_id), int)


class TestRequestMarketOrdering:
    @pytest.fixture(name="market_order_response_for_display")
    def fixture_market_order_response(self, dummy_market_order_response):
        return {
            "messsage": "Market order is done !",
            "order": dummy_market_order_response["orderCreateTransaction"],
        }

    @mock_sns
    def test_positive_market_order(
        self,
        client,
        dummy_market_order_response,
        dummy_stoploss_price,
        market_order_response_for_display,
    ):
        fixture_sns()
        dummy_response = dummy_market_order_response
        with patch("oandapyV20.API.request", return_value=dummy_response):
            response = client.request_market_ordering("", dummy_stoploss_price)
            assert response == market_order_response_for_display

    @mock_sns
    def test_negative_market_order(
        self,
        client,
        dummy_market_order_response,
        dummy_stoploss_price,
        market_order_response_for_display,
    ):
        fixture_sns()
        dummy_response = dummy_market_order_response
        with patch("oandapyV20.API.request", return_value=dummy_response):
            response = client.request_market_ordering("-", dummy_stoploss_price)
            assert response == market_order_response_for_display

    @mock_sns
    def test_error_response(self, client, dummy_stoploss_price):
        fixture_sns()
        error_response = {"orderCreateTransaction": {}}
        with patch("oandapyV20.API.request", return_value=error_response):
            response = client.request_market_ordering("", dummy_stoploss_price)
            assert response == {"messsage": "Market order is failed.", "result": error_response}

    @mock_sns
    def test_market_order_args(
        self,
        client,
        dummy_market_order_response,
        dummy_stoploss_price,
    ):
        fixture_sns()

        data = {
            "order": {
                "stopLossOnFill": {"timeInForce": "GTC", "price": str(dummy_stoploss_price)[:7]},
                "instrument": client._OandaClient__instrument,
                "units": "-{}".format(client._OandaClient__units),
                "type": "MARKET",
                "positionFill": "DEFAULT",
            }
        }
        dummy_response = dummy_market_order_response
        with patch("oandapyV20.endpoints.orders.OrderCreate") as mock:
            with patch("oandapyV20.API.request", return_value=dummy_response):
                client.request_market_ordering("-", dummy_stoploss_price)

        mock.assert_called_with(accountID=os.environ.get("OANDA_ACCOUNT_ID"), data=data)

    def test_without_stoploss(self, client):
        result = client.request_market_ordering(stoploss_price=None)
        assert "error" in result


class TestRequestTrailingStoploss:
    @pytest.fixture(name="dummy_crcdo_result")
    def fixture_dummy_crcdo_result(self) -> Dict[str, Any]:
        with open("tests/fixtures/api_responses/trade_CRCDO.json", "r") as f:
            dic_crcdo_result: Dict[str, Any] = json.load(f)
        return dic_crcdo_result

    @responses.activate
    def test_default(
        self,
        client: OandaClient,
        dummy_crcdo_result: Dict[str, Any],
        dummy_pricing_info: Dict[str, Any],
    ):
        # NOTE: mock APIs
        url: str = (
            f"https://api-fxpractice.oanda.com/v3/accounts/{os.environ['OANDA_ACCOUNT_ID']}/pricing"
        )
        add_simple_get_response(responses, url, response_json=dummy_pricing_info)

        client._OandaClient__trade_ids = ["999"]
        url: str = f"https://api-fxpractice.oanda.com/v3/accounts/{os.environ['OANDA_ACCOUNT_ID']}/trades/999/orders"
        add_simple_put_response(responses, url, response_json=dummy_crcdo_result)

        # test
        res: Dict[str, Union[str, bool]] = client.request_trailing_stoploss(stoploss_price=123.45)
        assert res == dummy_crcdo_result


class TestRequestClosing:
    @pytest.fixture(name="dummy_closing_result")
    def fixture_dummy_crcdo_result(self) -> Dict[str, Any]:
        with open("tests/fixtures/api_responses/trade_close.json", "r") as f:
            dic_closing_result: Dict[str, Any] = json.load(f)
        return dic_closing_result

    @mock_sns
    @responses.activate
    def test_default(
        self,
        client: OandaClient,
        dummy_closing_result: Dict[str, Any],
    ):
        fixture_sns()

        # NOTE: mock APIs
        client._OandaClient__trade_ids = ["999"]
        url: str = f"https://api-fxpractice.oanda.com/v3/accounts/{os.environ['OANDA_ACCOUNT_ID']}/trades/999/close"
        add_simple_put_response(responses, url, response_json=dummy_closing_result)

        # test
        res: Dict[str, Union[str, bool]] = client.request_closing(reason="test")
        assert res == {
            "[Client] message": "Position is closed",
            "reason": "test",
            "result": dummy_closing_result,
        }


# TODO: request_latest_transactions
#   from_id ~ to_id が 1000以内に収まっていること
#   assert_called_with で確認


def test_request_transactions_once(client, past_transactions):
    from_id = 1
    to_id = 5

    with patch("oandapyV20.endpoints.transactions.TransactionIDRange") as mock:
        with patch("oandapyV20.API.request", return_value=past_transactions):
            _ = client.request_transactions_once(from_id=from_id, to_id=to_id)
        mock.assert_called_with(
            accountID=os.environ.get("OANDA_ACCOUNT_ID"),
            params={"from": from_id, "to": 5, "type": ["ORDER"]},
        )


class TestRequestTransactionIds:
    def test_success(self, client):
        dummy_from_str = "xxxx-xx-xxT00:00:00.123456789Z"
        dummy_to_str = "xxxx-xx-xxT00:00:00.123456789Z"

        with patch("oandapyV20.endpoints.transactions.TransactionList") as mock:
            with patch("oandapyV20.API.request", return_value=TRANSACTION_IDS):
                from_id, to_id = client.request_transaction_ids(
                    from_str=dummy_from_str, to_str=dummy_to_str
                )
                assert from_id == "2"
                assert to_id == "400"

            mock.assert_called_with(
                accountID=os.environ.get("OANDA_ACCOUNT_ID"),
                params={"from": dummy_from_str, "pageSize": 1000, "to": dummy_to_str},
            )


class TestQueryInstruments:
    def test_query_by_count(self, client, dummy_instruments):
        granularity = "M5"
        candles_count = 399

        with patch("oandapyV20.endpoints.instruments.InstrumentsCandles") as mock:
            with patch("oandapyV20.API.request", return_value=dummy_instruments):
                result = client.query_instruments(
                    granularity=granularity, candles_count=candles_count
                )
            assert result == dummy_instruments

            mock.assert_called_with(
                instrument=client._OandaClient__instrument,
                params={
                    "alignmentTimezone": "Etc/GMT",
                    "count": candles_count,
                    "dailyAlignment": 0,
                    "granularity": granularity,
                },
            )

    def test_query_by_start_and_end(self, client, dummy_instruments):
        granularity = "M5"
        start = "xxxx-xx-xxT00:00:00.123456789Z"
        end = "xxxx-xx-xxT12:34:56.123456789Z"

        with patch("oandapyV20.endpoints.instruments.InstrumentsCandles") as mock:
            with patch("oandapyV20.API.request", return_value=dummy_instruments):
                result = client.query_instruments(granularity=granularity, start=start, end=end)
            assert result == dummy_instruments

            mock.assert_called_with(
                instrument=client._OandaClient__instrument,
                params={
                    "alignmentTimezone": "Etc/GMT",
                    "from": start,
                    "to": end,
                    "dailyAlignment": 0,
                    "granularity": granularity,
                },
            )
