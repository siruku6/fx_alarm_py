import unittest
import models.trader as trader

class TestTrader(unittest.TestCase):
    def setUp(self):
        print('[Trader] setup')
        # TODO: TEST用のデータを用意しないとテストもできない
        self.__trader_instance = trader.Trader()

    def test__accurize_entry_prices(self):
        pass
        self.__trader_instance._Trader__accurize_entry_prices()

if __name__ == '__main__':
    unittest.main()
