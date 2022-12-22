import datetime
from decimal import Decimal
import json

import pandas as pd

import src.lib.format_converter as converter


def test_granularity_to_timedelta():
    dummy_granuralities_and_expecteds = [
        {"granurality": "M1", "expected": datetime.timedelta(minutes=1)},
        {"granurality": "M5", "expected": datetime.timedelta(minutes=5)},
        {"granurality": "M10", "expected": datetime.timedelta(minutes=10)},
        {"granurality": "M30", "expected": datetime.timedelta(minutes=30)},
        {"granurality": "H1", "expected": datetime.timedelta(hours=1)},
        {"granurality": "H4", "expected": datetime.timedelta(hours=4)},
        {"granurality": "D", "expected": datetime.timedelta(days=1)},
    ]
    for dummy_dict in dummy_granuralities_and_expecteds:
        converted_result = converter.granularity_to_timedelta(dummy_dict["granurality"])
        assert converted_result == dummy_dict["expected"]


def test_to_candles_from_dynamo():
    # Case1: blank
    result = converter.to_candles_from_dynamo([])
    expected = pd.DataFrame([])

    pd.testing.assert_frame_equal(result, expected)

    # Case2: Possible candles
    dummy_raw_candles = [
        {"time": "2020-10-01T12:34:00.000000Z", "pareName": "GBP_JPY", "close": 123.456},
        {"time": "2020-10-01T12:34:00.000000Z", "pareName": "GBP_JPY", "close": 135.791357},
    ]
    decimalized_candles = json.loads(json.dumps(dummy_raw_candles), parse_float=Decimal)
    result = converter.to_candles_from_dynamo(decimalized_candles)
    [row.update({"time": converter.convert_to_m10(row["time"])}) for row in dummy_raw_candles]
    expected = pd.DataFrame.from_dict(dummy_raw_candles).drop("pareName", axis=1)

    pd.testing.assert_frame_equal(result, expected, check_like=True)


def test_convert_to_m10():
    dummy_time_str = [
        "2020-10-01T12:34:00.000000Z",
        "1999-12-31T23:59:00.000000Z",
        "1900-01-01T00:00:00.000000Z",
    ]
    expecteds = ["2020-10-01 12:30:00", "1999-12-31 23:50:00", "1900-01-01 00:00:00"]

    for time_str, expected in zip(dummy_time_str, expecteds):
        assert converter.convert_to_m10(time_str) == expected
