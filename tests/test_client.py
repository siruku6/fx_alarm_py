# Open modules
import unittest
import datetime
from unittest.mock import patch, MagicMock

# My-made modules
import models.oanda_py_client as watcher
from tests.oanda_dummy_responses import *


class TestClient(unittest.TestCase):
    #  - - - - - - - - - - - - - -
    #     Preparing & Clearing
    #  - - - - - - - - - - - - - -
    # def setUp(self):
    #     print('[Watcher] setup')
    #     self.__watcher_instance = watcher.OandaPyClient()

    @classmethod
    def setUpClass(cls):
        print('\n[Watcher] setup')
        cls.__watcher_instance = watcher.OandaPyClient()

    @classmethod
    def tearDownClass(cls):
        print('\n[Watcher] tearDown')
        # INFO: Preventing ResourceWarning: unclosed <ssl.SSLSocket
        # https://stackoverflow.com/questions/48160728/resourcewarning-unclosed-socket-in-python-3-unit-test
        cls.__watcher_instance._OandaPyClient__api_client.client.close()

    #  - - - - - - - - - - -
    #    Public methods
    #  - - - - - - - - - - -
    # def test_request_latest_candles(self):
    #     # Case1
    #     result = self.__watcher_instance.request_latest_candles(
    #         target_datetime='2018-07-12 21:00:00',
    #         granularity='M10',
    #         period_of_time='D'
    #     )
    #     result_start = datetime.strptime(result['time'][0], '%Y-%m-%d %H:%M:%S')
    #     result_end   = datetime.strptime(result['time'].values[-1], '%Y-%m-%d %H:%M:%S')
    #     result_size  = len(result)

    #     expected_start = datetime(2018, 7, 11, 21)
    #     expected_end   = datetime(2018, 7, 12, 20, 50)
    #     expected_size  = 144
    #     self.assertEqual(result_start, expected_start, '[request_latest_candles] １行目のtime')
    #     self.assertEqual(result_end,   expected_end,   '[request_latest_candles] 最終行のtime')
    #     self.assertEqual(result_size,  expected_size,  '[request_latest_candles] 戻り値のサイズ')

    #     # Case2
    #     result = self.__watcher_instance.request_latest_candles(
    #         target_datetime='2017-06-29 21:00:00',
    #         granularity='M30',
    #         period_of_time='H4'
    #     )
    #     result_start = datetime.strptime(result['time'][0], '%Y-%m-%d %H:%M:%S')
    #     result_end   = datetime.strptime(result['time'].values[-1], '%Y-%m-%d %H:%M:%S')
    #     result_size  = len(result)

    #     expected_start = datetime(2017, 6, 29, 17)
    #     expected_end   = datetime(2017, 6, 29, 20, 30)
    #     expected_size  = 8
    #     self.assertEqual(result_start, expected_start, '[request_latest_candles] １行目のtime')
    #     self.assertEqual(result_end,   expected_end,   '[request_latest_candles] 最終行のtime')
    #     self.assertEqual(result_size,  expected_size,  '[request_latest_candles] 戻り値のサイズ')

    def test_request_open_trades(self):
        self.assertIsNone(self.__watcher_instance._OandaPyClient__last_transaction_id)

        with patch('builtins.print'):
            with patch('pprint.pprint'):
                result = self.__watcher_instance.request_open_trades()
        self.assertIsInstance(int(self.__watcher_instance._OandaPyClient__last_transaction_id), int)

    def test_failing_market_ordering(self):
        result = self.__watcher_instance.request_market_ordering(stoploss_price=None)
        self.assertTrue('error' in result)

    def test_market_ordering(self):
        stoploss_price = 111.111
        dummy_response = {
            'orderCreateTransaction': {
                'instrument': 'dummy_instrument',
                'units': '1000',
                'time': '2020-01-13T12:34:56.912794035Z',  # 2019-04-18T14:05:59.912794035Z
                'stopLossOnFill': str(stoploss_price)
            }
        }
        with patch('oandapyV20.API.request', return_value=dummy_response):
            response = self.__watcher_instance.request_market_ordering('', stoploss_price)
            self.assertEqual(response, dummy_response['orderCreateTransaction'])

        with patch('oandapyV20.API.request', return_value=dummy_response):
            response = self.__watcher_instance.request_market_ordering('-', stoploss_price)
            self.assertEqual(response, dummy_response['orderCreateTransaction'])

        error_response = {'orderCreateTransaction': {}}
        with patch('oandapyV20.API.request', return_value=error_response):
            response = self.__watcher_instance.request_market_ordering('', stoploss_price)
            self.assertEqual(response, error_response['orderCreateTransaction'], 'response が空でも動作すること')

    def test_request_trailing_stoploss(self):
        result = self.__watcher_instance.request_trailing_stoploss()
        self.assertTrue('error' in result)

    def test_request_closing_position(self):
        result = self.__watcher_instance.request_closing_position()
        self.assertTrue('error' in result)

    # TODO: もうテスト対象メソッドはない。必要な情報を抜き出したら削除する
    # def test_request_trades_history(self):
    #     # INFO: Mock解説
    #     # https://akiyoko.hatenablog.jp/entry/2015/01/04/114642
    #     # https://thinkami.hatenablog.com/entry/2016/12/24/002922
    #     # mock = MagicMock()
    #     # mock.request_open_trades.return_value = dummy_open_trades()
    #
    #     with patch('oandapyV20.API.request', return_value=dummy_trades_list):
    #         trades_list = self.__watcher_instance.request_trades_history()
    #
    #     expected_columns = [
    #         'openTime', 'closeTime', 'position_type',
    #         'open', 'close', 'units',
    #         'gain', 'realizedPL'
    #     ]
    #     self.assertEqual(len(trades_list), 4, '生成されるレコード数は4')
    #     for index, trade in trades_list.iterrows():
    #         self.assertNotEqual(trade['state'], 'OPEN', 'OPENではない履歴だけを抽出')
    #         self.assertTrue((trade.index.values == expected_columns).all(), '列名が正しい')

    # def test_request_transactions(self):
    #     self.__watcher_instance._OandaPyClient__last_transaction_id = 1000
    #     result = self.__watcher_instance.request_transactions()
    #     # import pdb; pdb.set_trace()
    #     # TODO: testcord がない

    #  - - - - - - - - - - -
    #    Private methods
    #  - - - - - - - - - - -
    def test___transform_to_candle_chart(self):
        candles = self.__watcher_instance._OandaPyClient__transform_to_candle_chart(
            response=dummy_instruments
        )
        expected_array = ['close', 'high', 'low', 'open', 'time']
        self.assertTrue((candles.columns == expected_array).all())

    def test___calc_requestable_max_days(self):
        correction = {
            'D': 5000, 'M12': int(5000 / 120), 'H12': int(5000 / 2)
        }
        for key, val in correction.items():
            cnt = self.__watcher_instance._OandaPyClient__calc_requestable_max_days(
                granularity=key
            )
            self.assertEqual(cnt, val, '[Client __calc_requestable_max_days] {}'.format(key))

    def test___calc_requestable_time_duration(self):
        max_count = watcher.OandaPyClient.REQUESTABLE_COUNT
        granularties = ('M1', 'M5', 'M10', 'M15', 'M30', 'H1', 'H4', 'D')
        durations = [
            datetime.timedelta(minutes=time_int * max_count - 1) for time_int in [1, 5, 10, 15, 30]
        ] + [
            datetime.timedelta(minutes=(time_int * max_count - 1) * 60) for time_int in [1, 4]
        ]
        durations.append(datetime.timedelta(minutes=1 * max_count * 60 * 24))

        for granularity, duration in zip(granularties, durations):
            requestable_time_duration = self.__watcher_instance._OandaPyClient__calc_requestable_time_duration(
                granularity=granularity
            )
            # print(granularity, duration)
            self.assertEqual(
                requestable_time_duration, duration, '[Client __calc_requestable_time_duration] {}'.format(granularity)
            )


if __name__ == '__main__':
    unittest.main()
