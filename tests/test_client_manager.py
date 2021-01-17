import datetime
import pandas as pd
import pytest

import models.client_manager as manager
from models.clients.oanda_client import OandaClient
import models.tools.format_converter as converter


@pytest.fixture(name='client', scope='module', autouse=True)
def fixture_client_manager():
    client = manager.ClientManager(instrument='USD_JPY')
    yield client


def test_load_candles_by_duration_for_hist():
    pass


# - - - - - - - - - - -
#    Private methods
# - - - - - - - - - - -
examples_for_minimizer = (
    (datetime.datetime(2020, 1, 1), datetime.datetime(2020, 1, 5),
     datetime.timedelta(days=3), datetime.datetime(2020, 1, 4)),
    (datetime.datetime(2020, 1, 1), datetime.datetime(2020, 1, 3),
     datetime.timedelta(days=3), datetime.datetime(2020, 1, 3)),
)


@pytest.mark.parametrize('start, end, duration, expected', examples_for_minimizer)
def test___minimize_period(start, end, duration, expected, client):
    result = client._ClientManager__minimize_period(start, end, duration)
    assert result == expected


def test___detect_missings_with_no_candles(client):
    start = datetime.datetime(2020, 7, 6)
    end = datetime.datetime(2020, 7, 7)
    candles = pd.DataFrame([])
    missing_start, missing_end = client._ClientManager__detect_missings(candles, start, end)

    assert missing_start == start
    assert missing_end == end


examples_for_detector = (
    # Case1: No missing candles
    (datetime.datetime(2020, 7, 8), datetime.datetime(2020, 7, 8, 11),
     datetime.datetime(2020, 7, 8), datetime.datetime(2020, 7, 8, 11)),
    # Case2: No missing candles
    (datetime.datetime(2020, 7, 8, 1), datetime.datetime(2020, 7, 8, 10),
     datetime.datetime(2020, 7, 8, 11), datetime.datetime(2020, 7, 8)),
    # Case3: No missing candles
    (datetime.datetime(2020, 7, 8), datetime.datetime(2020, 7, 8, 10),
     datetime.datetime(2020, 7, 8), datetime.datetime(2020, 7, 8)),
    # Case4~6: There are missing candles
    (datetime.datetime(2020, 7, 5), datetime.datetime(2020, 7, 8, 10),
     datetime.datetime(2020, 7, 5), datetime.datetime(2020, 7, 8)),
    (datetime.datetime(2020, 7, 8, 1), datetime.datetime(2020, 7, 9),
     datetime.datetime(2020, 7, 8, 11), datetime.datetime(2020, 7, 9)),
    (datetime.datetime(2020, 7, 5), datetime.datetime(2020, 7, 9),
     datetime.datetime(2020, 7, 5), datetime.datetime(2020, 7, 9)),
)


@pytest.mark.parametrize('start, end, exp_missing_start, exp_missing_end', examples_for_detector)
def test___detect_missings(start, end, exp_missing_start, exp_missing_end, client, past_usd_candles):
    candles = pd.DataFrame(past_usd_candles).iloc[-12:, :]
    missing_start, missing_end = client._ClientManager__detect_missings(candles, start, end)

    assert missing_start == exp_missing_start
    assert missing_end == exp_missing_end


def test___calc_requestable_max_days(client):
    correction = {
        'D': 5000, 'M12': int(5000 / 120), 'H12': int(5000 / 2)
    }
    for key, expected_count in correction.items():
        cnt = client._ClientManager__calc_requestable_max_days(granularity=key)
        assert cnt == expected_count


def test___calc_requestable_time_duration(client):
    max_count = OandaClient.REQUESTABLE_COUNT - 1
    granularties = ('M1', 'M5', 'M10', 'M15', 'M30', 'H1', 'H4', 'D')
    durations = [
        datetime.timedelta(minutes=time_int * max_count) for time_int in [1, 5, 10, 15, 30]
    ] + [
        datetime.timedelta(minutes=time_int * max_count * 60) for time_int in [1, 4]
    ]
    durations.append(datetime.timedelta(minutes=1 * max_count * 60 * 24))

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
