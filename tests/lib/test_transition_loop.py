import math

import pytest

from src.lib import transition_loop
from tests.fixtures.factor_dicts import DUMMY_FACTOR_DICTS

examples_for_exitable = (
    ("long", 40, 90, True),
    ("long", 70, 80, True),
    ("long", 80, 70, False),
    ("short", 90, 40, True),
    ("short", 80, 70, True),
    ("short", 70, 80, False),
)


@pytest.mark.parametrize("position_type, stod, stosd, exitable", examples_for_exitable)
def test_exitable_by_stoccross(position_type, stod, stosd, exitable):
    # for row in test_dicts:
    is_exitable = transition_loop._exitable_by_stoccross(
        position_type=position_type, stod=stod, stosd=stosd
    )
    assert is_exitable == exitable


def test_is_exitable_by_bollinger():
    test_dicts = [
        {"spot_price": 125.5, "plus_2sigma": 130, "minus_2sigma": 120, "exitable": False},
        {"spot_price": 130.5, "plus_2sigma": 130, "minus_2sigma": 120, "exitable": True},
        {"spot_price": 119.5, "plus_2sigma": 130, "minus_2sigma": 120, "exitable": True},
    ]
    for row in test_dicts:
        is_exitable = transition_loop.is_exitable_by_bollinger(
            row["spot_price"], row["plus_2sigma"], row["minus_2sigma"]
        )
        assert is_exitable == row["exitable"]


# def test___trade_routine():
#     dummy_dicts = DUMMY_FACTOR_DICTS.copy()
#     transition_loop.commit_positions_by_loop(dummy_dicts)


def test___trade_routine():
    dummy_dicts = DUMMY_FACTOR_DICTS.copy()

    # Example: no position, but next is long
    index = 1
    next_direction = transition_loop.__trade_routine(None, dummy_dicts, index, dummy_dicts[index])
    assert next_direction == "long"
    assert "position" not in dummy_dicts[index]
    assert dummy_dicts[index + 1]["position"] == dummy_dicts[index + 1]["entryable"]

    # Example: sell_exit
    index = 8
    next_direction = transition_loop.__trade_routine("long", dummy_dicts, index, dummy_dicts[index])
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
    exit_price, exit_type, exit_reason = transition_loop.__decide_exit_price(
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
    # exit_price, exit_reason = transition_loop.__decide_exit_price(entry_direction, one_frame)
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
    exit_price, exit_type, exit_reason = transition_loop.__decide_exit_price(
        entry_direction, one_frame, previous_frame
    )
    assert exit_price is None
    assert exit_type == "buy_exit"
    assert exit_reason is None


def test___exit_by_stoploss():
    def test_stoploss(candles):
        for row in candles:
            exit_price, exit_reason = transition_loop.__exit_by_stoploss(row)

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
