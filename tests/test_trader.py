import unittest
import models.trader as trader

class TestTrader(unittest.TestCase):
    def setUp(self):
        print('[Trader] setup')
        self.__trader_instance = trader.Trader()

    def test_sample(self):
        self.__trader_instance._Trader__check_entry_timing()

if __name__ == '__main__':
    unittest.main()
