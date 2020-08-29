# Open modules
import datetime
import os

import pytest
import unittest
from unittest.mock import patch

# My-made modules
import models.oanda_py_client as watcher
from tests.fixtures.past_transactions import TRANSACTION_IDS, PAST_TRANSACTIONS


@pytest.fixture(name='client', scope='module', autouse=True)
def oanda_client():
    client = watcher.OandaPyClient()
    yield client
    # INFO: Preventing ResourceWarning: unclosed <ssl.SSLSocket
    # https://stackoverflow.com/questions/48160728/resourcewarning-unclosed-socket-in-python-3-unit-test
    client._OandaPyClient__api_client.client.close()


@pytest.fixture(scope='session', autouse=True)
def past_transactions():
    yield PAST_TRANSACTIONS


class TestClient(unittest.TestCase):
    #  - - - - - - - - - - - - - -
    #     Preparing & Clearing
    #  - - - - - - - - - - - - - -
    @classmethod
    def setUpClass(cls):
        cls.client_instance = watcher.OandaPyClient()

    @classmethod
    def tearDownClass(cls):
        cls.client_instance._OandaPyClient__api_client.client.close()

    #  - - - - - - - - - - -
    #    Public methods
    #  - - - - - - - - - - -
    def test_request_open_trades(self):
        self.assertIsNone(self.client_instance._OandaPyClient__last_transaction_id)

        with patch('builtins.print'):
            with patch('pprint.pprint'):
                result = self.client_instance.request_open_trades()
        self.assertIsInstance(int(self.client_instance._OandaPyClient__last_transaction_id), int)


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
            'instrument': client._OandaPyClient__instrument,
            'units': '-{}'.format(client._OandaPyClient__units),
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


def test_request_trailing_stoploss(client):
    result = client.request_trailing_stoploss()
    assert 'error' in result


def test_request_closing_position(client):
    result = client.request_closing_position()
    assert 'error' in result


# TODO: request_latest_transactions
#   from_id ~ to_id が 1000以内に収まっていること
#   assert_called_with で確認


def test_request_transactions_once(client, past_transactions):
    from_id = 1
    to_id = 5

    with patch('oandapyV20.endpoints.transactions.TransactionIDRange') as mock:
        with patch('oandapyV20.API.request', return_value=past_transactions):
            response = client.request_transactions_once(from_id=from_id, to_id=to_id)
        mock.assert_called_with(
            accountID=os.environ.get('OANDA_ACCOUNT_ID'), params={'from': from_id, 'to': 5, 'type': ['ORDER']}
        )


def test_request_transaction_ids(client):
    dummy_from_str = 'xxxx-xx-xxT00:00:00.123456789'

    with patch('oandapyV20.endpoints.transactions.TransactionList') as mock:
        with patch('oandapyV20.API.request', return_value=TRANSACTION_IDS):
            from_id, to_id = client.request_transaction_ids(from_str=dummy_from_str)
            assert from_id == '2'
            assert to_id == '400'

        mock.assert_called_with(
            accountID=os.environ.get('OANDA_ACCOUNT_ID'), params={'from': dummy_from_str, 'pageSize': 1000}
        )


# - - - - - - - - - - -
#    Private methods
# - - - - - - - - - - -
def test___calc_requestable_max_days(client):
    correction = {
        'D': 5000, 'M12': int(5000 / 120), 'H12': int(5000 / 2)
    }
    for key, expected_count in correction.items():
        cnt = client._OandaPyClient__calc_requestable_max_days(granularity=key)
        assert cnt == expected_count


def test___calc_requestable_time_duration(client):
    max_count = client.REQUESTABLE_COUNT
    granularties = ('M1', 'M5', 'M10', 'M15', 'M30', 'H1', 'H4', 'D')
    durations = [
        datetime.timedelta(minutes=time_int * max_count - 1) for time_int in [1, 5, 10, 15, 30]
    ] + [
        datetime.timedelta(minutes=(time_int * max_count - 1) * 60) for time_int in [1, 4]
    ]
    durations.append(datetime.timedelta(minutes=1 * max_count * 60 * 24))

    for granularity, expected_duration in zip(granularties, durations):
        requestable_time_duration = client._OandaPyClient__calc_requestable_time_duration(
            granularity=granularity
        )
        assert requestable_time_duration == expected_duration


if __name__ == '__main__':
    unittest.main()
