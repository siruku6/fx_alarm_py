from datetime import datetime, timedelta
from typing import Dict, Union
from unittest.mock import patch

import pandas as pd
import pytest

import src.client_manager as manager
from src.clients.oanda_accessor_pyv20.api import OandaClient


@pytest.fixture(name="client", scope="module", autouse=True)
def fixture_client_manager():
    client = manager.ClientManager(instrument="USD_JPY")
    yield client


class TestLoadCandlesByDuration:
    @patch("time.sleep")
    def test_short_time_period(
        self,
        mock_time,
        client,
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
            result: dict = client.load_candles_by_duration(
                start=datetime(2019, 4, 28, 21, 0),
                end=datetime(2019, 4, 28, 22, 0),
                granularity="H1",
            )
        expected: pd.DataFrame = pd.DataFrame(converted_dummy_instruments)
        pd.testing.assert_frame_equal(result["candles"], expected)
        mock.call_count == 1

    @patch("time.sleep")
    def test_long_time_period(
        self, mock_time, client, dummy_instruments: Dict[str, Union[list, str]]
    ):
        with patch(
            "src.clients.oanda_accessor_pyv20.api.OandaClient.query_instruments",
            return_value=dummy_instruments,
        ) as mock:
            client.load_candles_by_duration(
                start=datetime(2019, 4, 1, 0, 0),
                end=datetime(2019, 10, 31, 0, 0),
                granularity="H1",
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
def test___minimize_period(start, end, duration, expected, client):
    result = client._ClientManager__minimize_period(start, end, duration)
    assert result == expected


def test_prepare_one_page_transactions(client, dummy_raw_open_trades, past_transactions):
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
                result: pd.DataFrame = client.prepare_one_page_transactions()
    assert ((result["instrument"] == "USD_JPY") | (result["instrument_parent"] == "USD_JPY")).all()
    assert all(result.columns == expected_columns)


def test___calc_requestable_max_days(client):
    correction = {"D": 5000, "M12": int(5000 / 120), "H12": int(5000 / 2)}
    for key, expected_count in correction.items():
        cnt = client._ClientManager__calc_requestable_max_days(granularity=key)
        assert cnt == expected_count


def test___calc_requestable_time_duration(client):
    max_count = OandaClient.REQUESTABLE_COUNT - 1
    granularties = ("M1", "M5", "M10", "M15", "M30", "H1", "H4", "D")
    durations = [timedelta(minutes=time_int * max_count) for time_int in [1, 5, 10, 15, 30]] + [
        timedelta(minutes=time_int * max_count * 60) for time_int in [1, 4]
    ]
    durations.append(timedelta(minutes=1 * max_count * 60 * 24))

    for granularity, expected_duration in zip(granularties, durations):
        requestable_time_duration = client._ClientManager__calc_requestable_time_duration(
            granularity=granularity
        )
        assert requestable_time_duration == expected_duration


def test___union_candles_distinct(client, past_usd_candles):
    # Case1:
    candles = pd.DataFrame(past_usd_candles)
    result = client._ClientManager__union_candles_distinct(None, candles)
    pd.testing.assert_frame_equal(result, candles)

    # Case2: duplicated candles should droped
    old_candles = candles.iloc[:40, :].copy()
    new_candles = candles.iloc[-40:, :].copy()
    result = client._ClientManager__union_candles_distinct(new_candles, old_candles)
    pd.testing.assert_frame_equal(result, candles)
