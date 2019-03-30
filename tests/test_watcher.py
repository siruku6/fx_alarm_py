import unittest
import datetime
import models.chart_watcher as watcher

class TestWatcher(unittest.TestCase):
    def setUp(self):
        print('setup')
        self.__watcher_instance = watcher.ChartWatcher()

    def test_request_latest_candles(self):
        # ResourceWarning: unclosed <ssl.SSLSocket
        # https://qiita.com/zaneli@github/items/db680489d1fbccac44f2
        result = self.__watcher_instance.request_latest_candles(
            target_datetime='2018-07-12 00:00:00',
            granularity='M10'
        )
        result_start = result['time'][0]
        result_end   = result.tail(1)['time'].values[0]
        result_size  = len(result)

        expected_start = str(datetime.datetime(2018, 7, 12, 21))
        expected_end   = str(datetime.datetime(2018, 7, 13, 20, 50))
        expected_size  = 144
        self.assertEqual(result_start, expected_start, '[request_latest_candles] １行目のtime')
        self.assertEqual(result_end,   expected_end,   '[request_latest_candles] 最終行のtime')
        self.assertEqual(result_size,  expected_size,  '[request_latest_candles] 戻り値のサイズ')

if __name__ == '__main__':
    unittest.main()
