import math

from src.lib.transition_loop import (
    __decide_exit_price,
    __exit_by_stoploss,
    _trade_routine,
)
from tests.fixtures.factor_dicts import DUMMY_FACTOR_DICTS


class TestTradeRoutine:
    def test_no_long(self):
        """
        Example: no position, but next is long
        """
        dummy_dicts = DUMMY_FACTOR_DICTS

        index = 1
        next_direction = _trade_routine(None, dummy_dicts, index, dummy_dicts[index])
        assert next_direction == "long"
        assert "position" not in dummy_dicts[index]
        assert dummy_dicts[index + 1]["position"] == dummy_dicts[index + 1]["entryable"]

    def test_long_sell_exit(self):
        """
        Example: sell_exit
        """
        dummy_dicts = DUMMY_FACTOR_DICTS
        index = 8
        _ = _trade_routine("long", dummy_dicts, index, dummy_dicts[index])
        assert dummy_dicts[index]["position"] == "sell_exit"
        assert dummy_dicts[index + 1]["position"] == dummy_dicts[index + 1]["entryable"]


def test___decide_exit_price():
    # - - - - - - - - - - - - - - - - - - - -
    #             long entry
    # - - - - - - - - - - - - - - - - - - - -
    # 上昇中
    entry_direction = "long"
    one_frame = {
        "open": 100.0,
        "high": 130.0,
        "low": 90.0,
        "close": 120.0,
        "possible_stoploss": 80,
        "sigma*2_band": 140,
        "sigma*-2_band": 85,
        "stoD_3": 60,
        "stoSD_3": 50,
        "stoD_over_stoSD": True,
    }
    previous_frame = {"support": 80.0, "regist": 120.0}
    exit_price, exit_type, exit_reason = __decide_exit_price(
        entry_direction, one_frame, previous_frame
    )
    assert exit_price is None
    assert exit_type == "sell_exit"
    assert exit_reason is None

    # # 下降中
    # one_frame = {
    #     'open': 100.0, 'high': 130.0, 'low': 90.0, 'close': 120.0,
    #     'possible_stoploss': 80, 'sigma*2_band': 140, 'sigma*-2_band': 85, 'stoD_3': 60, 'stoSD_3': 50
    # }
    # exit_price, exit_reason = __decide_exit_price(entry_direction, one_frame)
    # assert exit_price is None

    # - - - - - - - - - - - - - - - - - - - -
    #             short entry
    # - - - - - - - - - - - - - - - - - - - -
    # 下降中
    entry_direction = "short"
    one_frame = {
        "open": 100.0,
        "high": 110.0,
        "low": 80.0,
        "close": 90.0,
        "possible_stoploss": 120,
        "sigma*2_band": 130,
        "sigma*-2_band": 70,
        "stoD_3": 40,
        "stoSD_3": 50,
        "stoD_over_stoSD": False,
    }
    previous_frame = {"support": 90.0, "regist": 120.0}
    exit_price, exit_type, exit_reason = __decide_exit_price(
        entry_direction, one_frame, previous_frame
    )
    assert exit_price is None
    assert exit_type == "buy_exit"
    assert exit_reason is None


def test___exit_by_stoploss():
    def test_stoploss(candles):
        for row in candles:
            exit_price, exit_reason = __exit_by_stoploss(row)

            if exit_price is None:
                assert exit_price is row["expected_exitprice"]
            else:
                assert math.isclose(exit_price, row["expected_exitprice"])
            assert exit_reason == row["expected_exitreason"]

    # INFO: test in long-entry
    long_candles = [
        {
            "entry_direction": "long",
            "high": 130.1,
            "low": 130.0,
            "possible_stoploss": 129.0,
            "expected_exitprice": None,
            "expected_exitreason": None,
        },
        {
            "entry_direction": "long",
            "high": 129.5,
            "low": 128.5,
            "possible_stoploss": 129.0,
            "expected_exitprice": 129.0,
            "expected_exitreason": "Hit stoploss",
        },
    ]
    # INFO: test in short-entry
    short_candles = [
        {
            "entry_direction": "short",
            "high": 130.1,
            "low": 130.0,
            "possible_stoploss": 130.5,
            "expected_exitprice": None,
            "expected_exitreason": None,
        },
        {
            "entry_direction": "short",
            "high": 131.0,
            "low": 130.0,
            "possible_stoploss": 130.5,
            "expected_exitprice": 130.5,
            "expected_exitreason": "Hit stoploss",
        },
    ]
    test_stoploss(long_candles)
    test_stoploss(short_candles)
