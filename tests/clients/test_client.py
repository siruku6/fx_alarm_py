from typing import Any, Dict, Union
import json
import os
from unittest.mock import patch

from oandapyV20.exceptions import V20Error
import responses
import pytest

# My-made modules
import src.clients.oanda_client as watcher
from tests.fixtures.past_transactions import TRANSACTION_IDS


@pytest.fixture(name='client', scope='module', autouse=True)
def oanda_client() -> watcher.OandaClient:
    client = watcher.OandaClient(instrument='USD_JPY')
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


@pytest.fixture(name='dummy_pricing_info')
def fixture_dummy_pricing_info() -> Dict[str, Any]:
    with open('tests/fixtures/api_responses/pricing_info.json', 'r') as f:
        dic_pricing_info: Dict[str, Any] = json.load(f)
    return dic_pricing_info


#  - - - - - - - - - - -
#    Public methods
#  - - - - - - - - - - -
class TestRequestIsTradeable:
    @responses.activate
    def test_default(self, client: watcher.OandaClient, dummy_pricing_info: Dict[str, Any]):
        url: str = f"https://api-fxpractice.oanda.com/v3/accounts/{os.environ['OANDA_ACCOUNT_ID']}/pricing"
        add_simple_get_response(responses, url, response_json=dummy_pricing_info)

        res: Dict[str, Union[str, bool]] = client.request_is_tradeable()
        assert res == {'instrument': 'USD_JPY', 'tradeable': True}


def test_request_open_trades(client, dummy_raw_open_trades):
    assert client.last_transaction_id is None

    with patch('builtins.print'):
        with patch('pprint.pprint'):
            with patch('oandapyV20.API.request', return_value=dummy_raw_open_trades):
                _ = client.request_open_trades()
    assert isinstance(client.last_transaction_id, str)
    assert isinstance(int(client.last_transaction_id), int)


def test_failing_market_ordering(client):
    result = client.request_market_ordering(stoploss_price=None)
    assert 'error' in result


def test_market_ordering(client, dummy_market_order_response, dummy_stoploss_price):
    dummy_response = dummy_market_order_response
    with patch('oandapyV20.API.request', return_value=dummy_response):
        response = client.request_market_ordering('', dummy_stoploss_price)
        assert response == dummy_response['orderCreateTransaction']

    with patch('oandapyV20.API.request', return_value=dummy_response):
        response = client.request_market_ordering('-', dummy_stoploss_price)
        assert response == dummy_response['orderCreateTransaction']

    error_response = {'orderCreateTransaction': {}}
    with patch('oandapyV20.API.request', return_value=error_response):
        response = client.request_market_ordering('', dummy_stoploss_price)
        assert response == error_response['orderCreateTransaction']  # 'response が空でも動作すること'


def test_market_order_args(client, dummy_market_order_response, dummy_stoploss_price):
    data = {
        'order': {
            'stopLossOnFill': {'timeInForce': 'GTC', 'price': str(dummy_stoploss_price)[:7]},
            'instrument': client._OandaClient__instrument,
            'units': '-{}'.format(client._OandaClient__units),
            'type': 'MARKET',
            'positionFill': 'DEFAULT'
        }
    }
    dummy_response = dummy_market_order_response
    with patch('oandapyV20.endpoints.orders.OrderCreate') as mock:
        with patch('oandapyV20.API.request', return_value=dummy_response):
            client.request_market_ordering('-', dummy_stoploss_price)

    mock.assert_called_with(
        accountID=os.environ.get('OANDA_ACCOUNT_ID'), data=data
    )


class TestRequestTrailingStoploss:
    @pytest.fixture(name='dummy_crcdo_result')
    def fixture_dummy_crcdo_result(self) -> Dict[str, Any]:
        with open('tests/fixtures/api_responses/trade_CRCDO.json', 'r') as f:
            dic_crcdo_result: Dict[str, Any] = json.load(f)
        return dic_crcdo_result

    @responses.activate
    def test_default(
        self, client: watcher.OandaClient,
        dummy_crcdo_result: Dict[str, Any], dummy_pricing_info: Dict[str, Any]
    ):
        # NOTE: mock APIs
        url: str = f"https://api-fxpractice.oanda.com/v3/accounts/{os.environ['OANDA_ACCOUNT_ID']}/pricing"
        add_simple_get_response(responses, url, response_json=dummy_pricing_info)

        client._OandaClient__trade_ids = ["999"]
        url: str = f"https://api-fxpractice.oanda.com/v3/accounts/{os.environ['OANDA_ACCOUNT_ID']}/trades/999/orders"
        add_simple_put_response(responses, url, response_json=dummy_crcdo_result)

        # test
        res: Dict[str, Union[str, bool]] = client.request_trailing_stoploss(stoploss_price=123.45)
        assert res == dummy_crcdo_result


class TestRequestClosing:
    @pytest.fixture(name='dummy_closing_result')
    def fixture_dummy_crcdo_result(self) -> Dict[str, Any]:
        with open('tests/fixtures/api_responses/trade_close.json', 'r') as f:
            dic_closing_result: Dict[str, Any] = json.load(f)
        return dic_closing_result

    @responses.activate
    def test_default(self, client: watcher.OandaClient, dummy_closing_result: Dict[str, Any]):
        # NOTE: mock APIs
        client._OandaClient__trade_ids = ["999"]
        url: str = f"https://api-fxpractice.oanda.com/v3/accounts/{os.environ['OANDA_ACCOUNT_ID']}/trades/999/close"
        add_simple_put_response(responses, url, response_json=dummy_closing_result)

        # test
        res: Dict[str, Union[str, bool]] = client.request_closing(reason='test')
        assert res == dummy_closing_result['orderFillTransaction']


# TODO: request_latest_transactions
#   from_id ~ to_id が 1000以内に収まっていること
#   assert_called_with で確認


def test_request_transactions_once(client, past_transactions):
    from_id = 1
    to_id = 5

    with patch('oandapyV20.endpoints.transactions.TransactionIDRange') as mock:
        with patch('oandapyV20.API.request', return_value=past_transactions):
            _ = client.request_transactions_once(from_id=from_id, to_id=to_id)
        mock.assert_called_with(
            accountID=os.environ.get('OANDA_ACCOUNT_ID'), params={'from': from_id, 'to': 5, 'type': ['ORDER']}
        )


def test_request_transaction_ids(client):
    dummy_from_str = 'xxxx-xx-xxT00:00:00.123456789Z'
    dummy_to_str = 'xxxx-xx-xxT00:00:00.123456789Z'

    with patch('oandapyV20.endpoints.transactions.TransactionList') as mock:
        with patch('oandapyV20.API.request', return_value=TRANSACTION_IDS):
            from_id, to_id = client.request_transaction_ids(from_str=dummy_from_str, to_str=dummy_to_str)
            assert from_id == '2'
            assert to_id == '400'

        mock.assert_called_with(
            accountID=os.environ.get('OANDA_ACCOUNT_ID'),
            params={'from': dummy_from_str, 'pageSize': 1000, 'to': dummy_to_str}
        )


def test_request_transaction_ids_failed(client):
    with patch('oandapyV20.API.request', side_effect=V20Error(code=400, msg="Invalid value specified for 'accountID'")):
        from_id, to_id = client.request_transaction_ids(from_str='', to_str='')
        assert from_id is None
        assert to_id is None
        assert client.accessable is False


def test_query_instruments(client, dummy_instruments):
    granularity = 'M5'
    candles_count = 399
    start = 'xxxx-xx-xxT00:00:00.123456789Z'
    end = 'xxxx-xx-xxT12:34:56.123456789Z'

    with patch('oandapyV20.endpoints.instruments.InstrumentsCandles') as mock:
        with patch('oandapyV20.API.request', return_value=dummy_instruments):
            result = client.query_instruments(granularity=granularity, candles_count=candles_count)
        assert result == dummy_instruments

        mock.assert_called_with(
            instrument=client._OandaClient__instrument,
            params={
                'alignmentTimezone': 'Etc/GMT',
                'count': candles_count,
                'dailyAlignment': 0,
                'granularity': granularity
            }
        )

    with patch('oandapyV20.endpoints.instruments.InstrumentsCandles') as mock:
        with patch('oandapyV20.API.request', return_value=dummy_instruments):
            result = client.query_instruments(granularity=granularity, start=start, end=end)
        assert result == dummy_instruments

        mock.assert_called_with(
            instrument=client._OandaClient__instrument,
            params={
                'alignmentTimezone': 'Etc/GMT',
                'from': start,
                'to': end,
                'dailyAlignment': 0,
                'granularity': granularity
            }
        )
