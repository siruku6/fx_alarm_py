import unittest

import models.chart_watcher as watcher

class TestWatcher(unittest.TestCase):
    def test_sample(self):
        w = watcher.ChartWatcher()
        result = w.request_latest_candle()
        self.assertEqual(result, 4, 'sample')

if __name__ == '__main__':
    unittest.main()
