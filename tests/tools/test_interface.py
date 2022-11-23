from collections import OrderedDict
import unittest
from unittest.mock import call, patch

import src.tools.interface as interface


def test_ask_granularity():
    dummy_inputs = ["M1", "M30", "H4", "D", "W"]
    for dummy_input in dummy_inputs:
        with patch("builtins.print") as mock:
            with patch("builtins.input", side_effect=[dummy_input]):
                assert interface.ask_granularity() == dummy_input
        mock.assert_called_once_with("取得スパンは？(ex: M5): ", end="")

    dummy_inputs = ["", "M", "30", "F4", "M5"]
    with patch("builtins.print") as mock:
        with patch("builtins.input", side_effect=dummy_inputs):
            assert interface.ask_granularity() == "M5"

    calls = [call("Invalid granularity !\n") for _ in dummy_inputs[:-1]]
    mock.assert_has_calls(calls, any_order=True)


class TestInterface(unittest.TestCase):
    def test_ask_true_or_false(self):
        with patch("builtins.print"):
            with patch("builtins.input", side_effect=["1"]):
                self.assertTrue(interface.ask_true_or_false("msg"))
            with patch("builtins.input", side_effect=["2"]):
                self.assertFalse(interface.ask_true_or_false("msg"))
            with patch("builtins.input", side_effect=["a", "", "0", "-1", "e3\n", "1"]):
                self.assertTrue((interface.ask_true_or_false("msg")))

    def test_select_stoploss_digit(self):
        with patch("src.tools.interface.print"):
            with patch("src.tools.interface.prompt_inputting_decimal", return_value=1):
                stoploss_digit = interface.select_stoploss_digit()
            self.assertEqual(type(stoploss_digit), float, "戻り値はfloat型")
            self.assertEqual(0.01, stoploss_digit)

            with patch("src.tools.interface.prompt_inputting_decimal", return_value=2):
                stoploss_digit = interface.select_stoploss_digit()
            self.assertEqual(type(stoploss_digit), float, "戻り値はfloat型")
            self.assertEqual(0.0001, stoploss_digit)

            with patch("src.tools.interface.prompt_inputting_decimal", return_value=3):
                stoploss_digit = interface.select_stoploss_digit()
            self.assertEqual(type(stoploss_digit), float, "戻り値はfloat型")
            self.assertEqual(0.00001, stoploss_digit)


class TestSelectFromDict:
    def test_default(self):
        dict_for_testcase = OrderedDict(
            USD_JPY={"spread": 0.004},
            EUR_USD={"spread": 0.00014},
            GBP_JPY={"spread": 0.014},
            USD_CHF={"spread": 0.00014},
        )
        with patch("src.tools.interface.print"):
            for i, (key, _val) in enumerate(dict_for_testcase.items()):
                with patch("src.tools.interface.prompt_inputting_decimal", return_value=i + 1):
                    result = interface.select_from_dict(dict_for_testcase)
                assert result == key  # "Get the name of key which is selected"


class TestSelectInstrument:
    def test_default(self):
        dict_for_testcase = OrderedDict(
            USD_JPY={"spread": 0.004},
            EUR_USD={"spread": 0.00014},
            GBP_JPY={"spread": 0.014},
            USD_CHF={"spread": 0.00014},
        )
        with patch("src.tools.interface.print"):
            for i, (key, val) in enumerate(dict_for_testcase.items()):
                with patch("src.tools.interface.prompt_inputting_decimal", return_value=i + 1):
                    instrument = interface.select_instrument()
                assert instrument["name"] == key
                assert instrument["spread"] == val["spread"]


if __name__ == "__main__":
    unittest.main()
