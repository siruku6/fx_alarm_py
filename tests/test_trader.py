import unittest
from unittest.mock import patch, MagicMock
import models
import models.trader as trader
from tests.oanda_dummy_responses import dummy_open_trades

class TestTrader(unittest.TestCase):
    def setUp(self):
        print('[Trader] setup')
        # TODO: TEST用のデータを用意しないとテストもできない
        self.__trader = trader.Trader()
        self.__real_trader = trader.RealTrader()

    # def test__accurize_entry_prices(self):
    #     pass
    #     self.__trader._Trader__accurize_entry_prices()

    def test__load_position(self):
        # INFO: Mock解説
        # https://akiyoko.hatenablog.jp/entry/2015/01/04/114642
        # https://thinkami.hatenablog.com/entry/2016/12/24/002922
        # mock = MagicMock()
        # mock.request_open_trades.return_value = dummy_open_trades()
        # with patch('models.trader.OandaPyClient', return_value=mock):
        #     self.__real_trader = trader.RealTrader()

        with patch('models.oanda_py_client.OandaPyClient.request_open_trades', return_value=dummy_open_trades()):
            pos = self.__real_trader._RealTrader__load_position()

        import pdb; pdb.set_trace()
        self.assertTrue('type' in  pos)
        self.assertTrue('price' in  pos)
        self.assertTrue('stoploss' in  pos)

if __name__ == '__main__':
    unittest.main()
