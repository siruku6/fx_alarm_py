from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

import src.clients.oanda_accessor_pyv20.preprocessor as prepro
from tests.fixtures.past_transactions import TRANSACTION_IDS


def test_to_oanda_format():
    dummy_date_elements = [
        {"year": 2020, "month": 10, "day": 1, "hour": 12, "min": 34, "sec": 56},
        {"year": 1999, "month": 12, "day": 31, "hour": 23, "min": 59, "sec": 59},
        {"year": 1900, "month": 1, "day": 1, "hour": 0, "min": 0, "sec": 0},
    ]
    expecteds = [
        "2020-10-01T12:34:00.000000Z",
        "1999-12-31T23:59:00.000000Z",
        "1900-01-01T00:00:00.000000Z",
    ]

    for date_element, expected in zip(dummy_date_elements, expecteds):
        converted_result = prepro.to_oanda_format(
            datetime(
                year=date_element["year"],
                month=date_element["month"],
                day=date_element["day"],
                hour=date_element["hour"],
                minute=date_element["min"],
                second=date_element["sec"],
            )
        )
        assert converted_result == expected


examples_for_granularity_to_timedelta = (
    ("M1", timedelta(minutes=1)),
    ("M5", timedelta(minutes=5)),
    ("M10", timedelta(minutes=10)),
    ("M30", timedelta(minutes=30)),
    ("H1", timedelta(hours=1)),
    ("H4", timedelta(hours=4)),
    ("D", timedelta(days=1)),
)


@pytest.mark.parametrize(
    "granurality, expected",
    examples_for_granularity_to_timedelta,
)
def test_granularity_to_timedelta(granurality, expected):
    converted_result = prepro.granularity_to_timedelta(granurality)
    assert converted_result == expected


class TestToCandleDf:
    def test_blank_candle(self, dummy_instruments):
        no_candles = prepro.to_candle_df({"candles": []})
        assert isinstance(no_candles, pd.core.frame.DataFrame)

    def test_exist_candles(self, dummy_instruments):
        candles = prepro.to_candle_df(dummy_instruments)
        expected_array = ["close", "high", "low", "open", "volume", "complete", "time"]
        assert (candles.columns == expected_array).all()
        assert candles["time"][0] == "2019-04-28 21:00:00"


def test_extract_transaction_ids():
    dummy_response = TRANSACTION_IDS
    result = prepro.extract_transaction_ids(dummy_response)
    assert result == {"old_id": "2", "last_id": "400"}


def test_filter_and_make_df(past_transactions, expected_columns):
    instrument = "USD_JPY"
    result = prepro.filter_and_make_df(past_transactions["transactions"], instrument)

    # Assert Columns
    assert (result.columns == expected_columns).all()

    # Assert filtering by Instrument
    result_filtered_again_by_instrument = (result["instrument"] == instrument) | (
        result["instrument_parent"] == instrument
    )
    assert len(result) == len(result_filtered_again_by_instrument)


@pytest.fixture(scope="module", autouse=True)
def expected_columns():
    yield np.array(
        [
            "id",
            "batchID",
            "tradeID",
            "tradeOpened",
            "tradesClosed",
            "type",
            "price",
            "units",
            "pl",
            "time",
            "reason",
            "instrument",
            "instrument_parent",
        ]
    )


def test_filter_and_make_df_with_no_pl(no_pl_transactions, expected_columns):
    instrument = "USD_JPY"
    result = prepro.filter_and_make_df(no_pl_transactions, instrument)

    # # Assert Columns
    assert (result.columns == expected_columns).all()

    # Assert no error arise, it it were not for any rows
    assert len(result) == 0
