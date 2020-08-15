# Open modules
import datetime
import os

import pytest
import unittest
from unittest.mock import patch

# My-made modules
import models.oanda_py_client as watcher
from tests.oanda_dummy_responses import dummy_market_order_response
from tests.fixtures.past_transactions import TRANSACTION_IDS, PAST_TRANSACTIONS


@pytest.fixture(scope='module', autouse=True)
def oanda_client():
    client = watcher.OandaPyClient()
    yield client
    client._OandaPyClient__api_client.client.close()


@pytest.fixture(scope='module', autouse=True)
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
        # INFO: Preventing ResourceWarning: unclosed <ssl.SSLSocket
        # https://stackoverflow.com/questions/48160728/resourcewarning-unclosed-socket-in-python-3-unit-test
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

    def test_failing_market_ordering(self):
        result = self.client_instance.request_market_ordering(stoploss_price=None)
        self.assertTrue('error' in result)

    def test_market_ordering(self):
        stoploss_price = 111.111
        dummy_response = dummy_market_order_response(stoploss_price)
        with patch('oandapyV20.API.request', return_value=dummy_response):
            response = self.client_instance.request_market_ordering('', stoploss_price)
            self.assertEqual(response, dummy_response['orderCreateTransaction'])

        with patch('oandapyV20.API.request', return_value=dummy_response):
            response = self.client_instance.request_market_ordering('-', stoploss_price)
            self.assertEqual(response, dummy_response['orderCreateTransaction'])

        error_response = {'orderCreateTransaction': {}}
        with patch('oandapyV20.API.request', return_value=error_response):
            response = self.client_instance.request_market_ordering('', stoploss_price)
            self.assertEqual(response, error_response['orderCreateTransaction'], 'response が空でも動作すること')

    def test_market_order_args(self):
        stoploss_price = 111.111
        data = {
            'order': {
                'stopLossOnFill': {'timeInForce': 'GTC', 'price': str(stoploss_price)[:7]},
                'instrument': self.client_instance._OandaPyClient__instrument,
                'units': '-{}'.format(self.client_instance._OandaPyClient__units),
                'type': 'MARKET',
                'positionFill': 'DEFAULT'
            }
        }
        dummy_response = dummy_market_order_response(stoploss_price)
        with patch('oandapyV20.endpoints.orders.OrderCreate') as mock:
            with patch('oandapyV20.API.request', return_value=dummy_response):
                self.client_instance.request_market_ordering('-', stoploss_price)

        mock.assert_called_with(
            accountID=os.environ.get('OANDA_ACCOUNT_ID'), data=data
        )

    def test_request_trailing_stoploss(self):
        result = self.client_instance.request_trailing_stoploss()
        assert 'error' in result

    def test_request_closing_position(self):
        result = self.client_instance.request_closing_position()
        assert 'error' in result

# - - - - - - - - - - -
#    Private methods
# - - - - - - - - - - -
def test___request_transactions_once(oanda_client, past_transactions):
    from_id = 1
    to_id = 5
    # import pdb; pdb.set_trace()

    with patch('oandapyV20.endpoints.transactions.TransactionIDRange') as mock:
        with patch('oandapyV20.API.request', return_value=past_transactions):
            response = oanda_client._OandaPyClient__request_transactions_once(from_id=from_id, to_id=to_id)
        mock.assert_called_with(
            accountID=os.environ.get('OANDA_ACCOUNT_ID'), params={'from': from_id, 'to': 5, 'type': ['ORDER']}
        )


def test___request_transaction_ids(oanda_client):
    dummy_from_str = 'xxxx-xx-xxT00:00:00.123456789'

    with patch('oandapyV20.endpoints.transactions.TransactionList') as mock:
        with patch('oandapyV20.API.request', return_value=TRANSACTION_IDS):
            from_id, to_id = oanda_client._OandaPyClient__request_transaction_ids(from_str=dummy_from_str)
            assert from_id == '2'
            assert to_id == '400'

        mock.assert_called_with(
            accountID=os.environ.get('OANDA_ACCOUNT_ID'), params={'from': dummy_from_str, 'pageSize': 1000}
        )


def test___calc_requestable_max_days(oanda_client):
    correction = {
        'D': 5000, 'M12': int(5000 / 120), 'H12': int(5000 / 2)
    }
    for key, expected_count in correction.items():
        cnt = oanda_client._OandaPyClient__calc_requestable_max_days(granularity=key)
        assert cnt == expected_count


def test___calc_requestable_time_duration(oanda_client):
    max_count = oanda_client.REQUESTABLE_COUNT
    granularties = ('M1', 'M5', 'M10', 'M15', 'M30', 'H1', 'H4', 'D')
    durations = [
        datetime.timedelta(minutes=time_int * max_count - 1) for time_int in [1, 5, 10, 15, 30]
    ] + [
        datetime.timedelta(minutes=(time_int * max_count - 1) * 60) for time_int in [1, 4]
    ]
    durations.append(datetime.timedelta(minutes=1 * max_count * 60 * 24))

    for granularity, expected_duration in zip(granularties, durations):
        requestable_time_duration = oanda_client._OandaPyClient__calc_requestable_time_duration(
            granularity=granularity
        )
        assert requestable_time_duration == expected_duration


if __name__ == '__main__':
    unittest.main()
