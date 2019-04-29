# Open modules
import unittest
from datetime import datetime
from unittest.mock import patch

# My-made modules
import models.oanda_py_client as watcher
from tests.oanda_dummy_responses import dummy_trades_list

class TestClient(unittest.TestCase):
    def setUp(self):
        print('[Watcher] setup')
        self.__watcher_instance = watcher.OandaPyClient()

    # @classmethod
    # def setUpClass(self):
    #     print('[Watcher] setup')
    #     self.__watcher_instance = watcher.OandaPyClient()

    def tearDown(self):
        print('[Watcher] tearDown')
        # INFO: Preventing ResourceWarning
        # https://stackoverflow.com/questions/48160728/resourcewarning-unclosed-socket-in-python-3-unit-test
        self.__watcher_instance._OandaPyClient__api_client.client.close()

    def test_request_latest_candles(self):
        # ResourceWarning: unclosed <ssl.SSLSocket
        # https://qiita.com/zaneli@github/items/db680489d1fbccac44f2

        # Case1
        result = self.__watcher_instance.request_latest_candles(
            target_datetime='2018-07-12 21:00:00',
            granularity='M10',
            period_m=1440
        )
        result_start = datetime.strptime(result['time'][0], '%Y-%m-%d %H:%M:%S+00:00')
        result_end   = datetime.strptime(result['time'].values[-1], '%Y-%m-%d %H:%M:%S+00:00')
        result_size  = len(result)

        expected_start = datetime(2018, 7, 12, 21)
        expected_end   = datetime(2018, 7, 13, 20, 50)
        expected_size  = 144
        self.assertEqual(result_start, expected_start, '[request_latest_candles] １行目のtime')
        self.assertEqual(result_end,   expected_end,   '[request_latest_candles] 最終行のtime')
        self.assertEqual(result_size,  expected_size,  '[request_latest_candles] 戻り値のサイズ')

        # Case2
        result = self.__watcher_instance.request_latest_candles(
            target_datetime='2017-06-29 21:00:00',
            granularity='M30',
            period_m=240
        )
        result_start = datetime.strptime(result['time'][0], '%Y-%m-%d %H:%M:%S+00:00')
        result_end   = datetime.strptime(result['time'].values[-1], '%Y-%m-%d %H:%M:%S+00:00')
        result_size  = len(result)

        expected_start = datetime(2017, 6, 29, 21)
        expected_end   = datetime(2017, 6, 30,  0, 30)
        expected_size  = 8
        self.assertEqual(result_start, expected_start, '[request_latest_candles] １行目のtime')
        self.assertEqual(result_end,   expected_end,   '[request_latest_candles] 最終行のtime')
        self.assertEqual(result_size,  expected_size,  '[request_latest_candles] 戻り値のサイズ')

    def test_request_market_ordering(self):
        result = self.__watcher_instance.request_market_ordering(stoploss_price=None)
        self.assertTrue('error' in result)

    def test_request_trailing_stoploss(self):
        result = self.__watcher_instance.request_trailing_stoploss()
        self.assertTrue('error' in result)

    def test_request_closing_position(self):
        result = self.__watcher_instance.request_closing_position()
        self.assertTrue('error' in result)

    def test_request_trades_history(self):
        # HACK: side_effect はイテラブルを1つずつしか返さないので、返却値を配列として渡す
        with patch('oandapyV20.endpoints.trades.TradesList', side_effect=[dummy_trades_list()]):
            with patch('oandapyV20.API.request', return_value=None):
                trades_list = self.__watcher_instance.request_trades_history()

        for trade in trades_list:
            self.assertEqual(trade['state'], 'CLOSED')
            self.assertNotEqual(trade['state'], 'OPEN')

if __name__ == '__main__':
    unittest.main()
