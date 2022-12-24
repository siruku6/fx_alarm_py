from datetime import datetime, timedelta
import os
from typing import Dict, Union
from unittest.mock import patch

import pandas as pd
import pytest

from src.clients.oanda_accessor_pyv20.api import OandaClient
from src.clients.oanda_accessor_pyv20.interface import OandaInterface


@pytest.fixture(name="o_i_instance", scope="module", autouse=True)
def fixture_interface():
    o_i_instance: OandaInterface = OandaInterface(instrument="USD_JPY")
    yield o_i_instance


class TestInit:
    def test_without_account_id(self):
        os.environ.pop("OANDA_ACCOUNT_ID")
        with pytest.raises(ValueError) as e_info:
            OandaInterface("USD_JPY", test=True)

        assert e_info.value.__str__() == (
            "The following variables are blank: ['account_id']. "
            "You have to set them by environment variables or passing arguments."
        )

    def test_without_access_token(self):
        os.environ.pop("OANDA_ACCESS_TOKEN")
        with pytest.raises(ValueError) as e_info:
            OandaInterface("USD_JPY", test=True)

        assert e_info.value.__str__() == (
            "The following variables are blank: ['access_token']. "
            "You have to set them by environment variables or passing arguments."
        )

    def test_with_necessary_variables(self):
        instrument: str = "USD_JPY"
        oanda_interface: OandaInterface = OandaInterface(instrument, test=True)

        assert oanda_interface._OandaInterface__instrument == instrument


class TestLoadCandlesByDays:
    def test_short_time_period(
        self,
        o_i_instance,
        dummy_instruments: Dict[
            str,
            Union[list, str],
        ],
        converted_dummy_instruments,
    ):
        with patch(
            "src.clients.oanda_accessor_pyv20.api.OandaClient.query_instruments",
            return_value=dummy_instruments,
        ) as mock:
            result: dict = o_i_instance.load_candles_by_days(
                days=100,
                granularity="H1",
                sleep_time=0,
            )
        expected: pd.DataFrame = pd.DataFrame(converted_dummy_instruments)
        pd.testing.assert_frame_equal(result["candles"], expected)
        mock.call_count == 1

    def test_long_time_period(self, o_i_instance, dummy_instruments: Dict[str, Union[list, str]]):
        with patch(
            "src.clients.oanda_accessor_pyv20.api.OandaClient.query_instruments",
            return_value=dummy_instruments,
        ) as mock:
            o_i_instance.load_candles_by_days(
                days=300,
                granularity="H1",
                sleep_time=0,
            )

        assert mock.call_count == 2


class TestLoadCandlesByDuration:
    def test_short_time_period(
        self,
        o_i_instance,
        dummy_instruments: Dict[
            str,
            Union[list, str],
        ],
        converted_dummy_instruments,
    ):
        with patch(
            "src.clients.oanda_accessor_pyv20.api.OandaClient.query_instruments",
            return_value=dummy_instruments,
        ) as mock:
            result: dict = o_i_instance.load_candles_by_duration(
                start=datetime(2019, 4, 28, 21, 0),
                end=datetime(2019, 4, 28, 22, 0),
                granularity="H1",
                sleep_time=0,
            )
        expected: pd.DataFrame = pd.DataFrame(converted_dummy_instruments)
        pd.testing.assert_frame_equal(result["candles"], expected)
        mock.call_count == 1

    def test_long_time_period(self, o_i_instance, dummy_instruments: Dict[str, Union[list, str]]):
        with patch(
            "src.clients.oanda_accessor_pyv20.api.OandaClient.query_instruments",
            return_value=dummy_instruments,
        ) as mock:
            o_i_instance.load_candles_by_duration(
                start=datetime(2019, 4, 1, 0, 0),
                end=datetime(2019, 10, 31, 0, 0),
                granularity="H1",
                sleep_time=0,
            )

        assert mock.call_count == 2


# - - - - - - - - - - -
#    Private methods
# - - - - - - - - - - -
examples_for_minimizer = (
    (
        datetime(2020, 1, 1),
        datetime(2020, 1, 5),
        timedelta(days=3),
        datetime(2020, 1, 4),
    ),
    (
        datetime(2020, 1, 1),
        datetime(2020, 1, 3),
        timedelta(days=3),
        datetime(2020, 1, 3),
    ),
)


@pytest.mark.parametrize("start, end, duration, expected", examples_for_minimizer)
def test___minimize_period(start, end, duration, expected, o_i_instance):
    result = o_i_instance._OandaInterface__minimize_period(start, end, duration)
    assert result == expected


def test_prepare_one_page_transactions(o_i_instance, dummy_raw_open_trades, past_transactions):
    expected_columns = [
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

    # INFO: Skip requesting open_trades
    with patch("oandapyV20.API.request", return_value=dummy_raw_open_trades):
        # INFO: Skip requesting transactions
        with patch(
            "src.clients.oanda_accessor_pyv20.api.OandaClient.request_transactions_once",
            return_value=past_transactions,
        ):
            with patch("pandas.DataFrame.to_csv", return_value=None):
                # 2317
                result: pd.DataFrame = o_i_instance.prepare_one_page_transactions()
    assert ((result["instrument"] == "USD_JPY") | (result["instrument_parent"] == "USD_JPY")).all()
    assert all(result.columns == expected_columns)


def test___calc_requestable_max_days(o_i_instance):
    correction = {"D": 5000, "M12": int(5000 / 120), "H12": int(5000 / 2)}
    for key, expected_count in correction.items():
        cnt = o_i_instance._OandaInterface__calc_requestable_max_days(granularity=key)
        assert cnt == expected_count


def test___calc_requestable_time_duration(o_i_instance):
    max_count = OandaClient.REQUESTABLE_COUNT - 1
    granularties = ("M1", "M5", "M10", "M15", "M30", "H1", "H4", "D")
    durations = [timedelta(minutes=time_int * max_count) for time_int in [1, 5, 10, 15, 30]] + [
        timedelta(minutes=time_int * max_count * 60) for time_int in [1, 4]
    ]
    durations.append(timedelta(minutes=1 * max_count * 60 * 24))

    for granularity, expected_duration in zip(granularties, durations):
        requestable_time_duration = o_i_instance._OandaInterface__calc_requestable_time_duration(
            granularity=granularity
        )
        assert requestable_time_duration == expected_duration


def test___union_candles_distinct(o_i_instance, past_usd_candles):
    # Case1:
    candles = pd.DataFrame(past_usd_candles)
    result = o_i_instance._OandaInterface__union_candles_distinct(None, candles)
    pd.testing.assert_frame_equal(result, candles)

    # Case2: duplicated candles should droped
    old_candles = candles.iloc[:40, :].copy()
    new_candles = candles.iloc[-40:, :].copy()
    result = o_i_instance._OandaInterface__union_candles_distinct(new_candles, old_candles)
    pd.testing.assert_frame_equal(result, candles)
