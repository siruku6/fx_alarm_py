import unittest
from unittest.mock import patch
import models
import models.trader as trader
import models.real_trader as real
from tests.oanda_dummy_responses import dummy_open_trades

class TestTrader(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print('\n[Trader] setup')
        # TODO: TEST用のデータを用意しないとテストもできない
        with patch('builtins.print'):
            with patch('models.trader.Trader.get_instrument', return_value='USD_JPY'):
                cls.__trader = trader.Trader(operation='unittest')
                cls.__real_trader = real.RealTrader(operation='unittest')

    @classmethod
    def tearDownClass(cls):
        print('\n[Trader] tearDown')
        cls.__trader._client._OandaPyClient__api_client.client.close()
        cls.__real_trader._client._OandaPyClient__api_client.client.close()

    def test__accurize_entry_prices(self):
        pass
        # self.__trader._Trader__accurize_entry_prices()

    def test__load_position(self):
        with patch('models.oanda_py_client.OandaPyClient.request_open_trades', return_value=dummy_open_trades):
            pos = self.__real_trader._RealTrader__load_position()

        self.assertEqual(type(pos), dict, '戻り値は辞書型')
        self.assertTrue('type' in  pos)
        self.assertTrue('price' in  pos)
        self.assertTrue('stoploss' in  pos)


if __name__ == '__main__':
    unittest.main()
