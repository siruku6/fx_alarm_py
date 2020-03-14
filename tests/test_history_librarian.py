import unittest
from unittest.mock import patch  #, MagicMock
import pandas as pd

import models.history_librarian as libra

class TestLibrarian(unittest.TestCase):
    #  - - - - - - - - - - - - - -
    #     Preparing & Clearing
    #  - - - - - - - - - - - - - -
    @classmethod
    def setUpClass(cls):
        print('\n[libra] setup')
        with patch('models.oanda_py_client.OandaPyClient.select_instrument',
                   return_value={ 'name': 'USD_JPY', 'spread': 0.0 }):
            cls.libra_instance = libra.Librarian()

    @classmethod
    def tearDownClass(cls):
        print('\n[libra] tearDown')

    #  - - - - - - - - - - -
    #    Public methods
    #  - - - - - - - - - - -

    #  - - - - - - - - - - -
    #    Private methods
    #  - - - - - - - - - - -
    def test___detect_dst_switches(self):
        time_df = pd.DataFrame({'time': [
            '2020-02-17 06:00:00',
            '2020-02-17 10:00:00',
            '2020-02-17 14:00:00',
            '2020-03-12 17:00:00',
            '2020-03-12 21:00:00',
            '2020-03-13 01:00:00',
            '2020-03-13 05:00:00'
        ]})
        switch_points = self.libra_instance._Librarian__detect_dst_switches(time_df)
        self.assertEqual(switch_points, [
            {'time': '2020-02-17 06:00:00', 'summer_time': False},
            {'time': '2020-03-12 17:00:00', 'summer_time': True}
        ], 'index == 0 と、サマータイムの適用有無が切り替わった直後の時間を返す')

        time_df = pd.DataFrame({'time': [
            '2020-02-17 06:00:00',
            '2020-02-17 10:00:00',
            '2020-02-17 14:00:00',
            '2020-03-12 17:00:00',
            '2020-03-12 21:00:00',
            '2020-03-13 01:00:00',
            '2020-03-13 05:00:00',
            '2020-03-13 06:00:00',
        ]})
        switch_points = self.libra_instance._Librarian__detect_dst_switches(time_df)
        self.assertEqual(switch_points, [
            {'time': '2020-02-17 06:00:00', 'summer_time': False},
            {'time': '2020-03-12 17:00:00', 'summer_time': True},
            {'time': '2020-03-13 06:00:00', 'summer_time': False},
        ], 'index == 0 と、サマータイムの適用有無が切り替わった直後の時間を何度でも返す')

if __name__ == '__main__':
    unittest.main()
