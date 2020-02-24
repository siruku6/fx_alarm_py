import unittest
from unittest.mock import patch
import models.interface as interface

class TestInterface(unittest.TestCase):
    def test_ask_true_or_false(self):
        with patch('builtins.print'):
            with patch('builtins.input', side_effect=['1']):
                self.assertTrue(interface.ask_true_or_false('msg'))
            with patch('builtins.input', side_effect=['2']):
                self.assertFalse(interface.ask_true_or_false('msg'))
            with patch('builtins.input', side_effect=['a', '', '0', '-1', 'e3\n', '1']):
                self.assertTrue((interface.ask_true_or_false('msg')))

    def test_select_stoploss_digit(self):
        with patch('models.interface.print'):
            with patch('models.interface.prompt_inputting_decimal', return_value=1):
                stoploss_digit = interface.select_stoploss_digit()
            self.assertEqual(type(stoploss_digit), float, '戻り値はfloat型')
            self.assertEqual(0.01, stoploss_digit)

            with patch('models.interface.prompt_inputting_decimal', return_value=2):
                stoploss_digit = interface.select_stoploss_digit()
            self.assertEqual(type(stoploss_digit), float, '戻り値はfloat型')
            self.assertEqual(0.0001, stoploss_digit)

            with patch('models.interface.prompt_inputting_decimal', return_value=3):
                stoploss_digit = interface.select_stoploss_digit()
            self.assertEqual(type(stoploss_digit), float, '戻り値はfloat型')
            self.assertEqual(0.00001, stoploss_digit)

    def test_select_from_dict(self):
        dict_for_testcase = {1: 'swing', 2: 'scalping', 3: 'other'}
        with patch('models.interface.print'):
            for key, val in dict_for_testcase.items():
                with patch('models.interface.prompt_inputting_decimal', return_value=key):
                    result = interface.select_from_dict(dict_for_testcase)
                    self.assertEqual(result, val, '選択したkeyに対応するvalを得る')


if __name__ == '__main__':
    unittest.main()
