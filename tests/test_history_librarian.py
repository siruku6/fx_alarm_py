import datetime
from unittest.mock import patch  # , MagicMock
import pytest

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal

import models.history_librarian as libra
import models.tools.format_converter as converter
from tests.fixtures.past_transactions import NO_PL_TRANSACTIONS


#  - - - - - - - - - - - - - -
#     Preparing & Clearing
#  - - - - - - - - - - - - - -
@pytest.fixture(scope='module', name='libra_client', autouse=True)
def fixture_libra_client():
    with patch('models.client_manager.ClientManager.select_instrument',
               return_value=['USD_JPY', {'spread': 0.0}]):
        yield libra.Librarian()


@pytest.fixture(scope='module', name='hist_df', autouse=True)
def fixture_hist_df():
    dummy_hist = pd.DataFrame({'time': [
        '2020-02-17 05:12:00', '2020-02-17 08:59:00', '2020-02-17 15:27:00', '2020-03-11 17:31:00',
        '2020-03-12 01:01:00', '2020-03-13 01:14:00', '2020-03-13 08:48:00'
    ]})
    yield dummy_hist


@pytest.fixture(scope='module', name='no_pl_transactions', autouse=True)
def fixture_no_pl_transactions():
    yield NO_PL_TRANSACTIONS


@pytest.fixture(scope='module', name='win_sum_candles', autouse=True)
def fixture_win_sum_candles():
    dummy_candles = pd.DataFrame({'time': [
        '2020-02-17 06:00:00', '2020-02-17 10:00:00', '2020-02-17 14:00:00', '2020-03-12 17:00:00',
        '2020-03-12 21:00:00', '2020-03-13 01:00:00', '2020-03-13 05:00:00'
    ]})
    yield dummy_candles


@pytest.fixture(scope='module', name='win_sum_win_candles', autouse=True)
def fixture_win_sum_win_candles():
    dummy_candles = pd.DataFrame({'time': [
        '2020-02-17 06:00:00', '2020-02-17 10:00:00', '2020-02-17 14:00:00',
        '2020-03-12 17:00:00', '2020-03-12 21:00:00', '2020-03-13 01:00:00', '2020-03-13 05:00:00',
        '2020-03-13 06:00:00',
    ]})
    yield dummy_candles


#  - - - - - - - - - - -
#    Public methods
#  - - - - - - - - - - -

#  - - - - - - - - - - -
#    Private methods
#  - - - - - - - - - - -
def test___prepare_candles(libra_client):
    from_str = '2020-01-01T12:34:56.000'
    to_str = '2020-01-20T12:34:56.000'

    # Case1:
    #   The period between from and to is less than 400 candles
    granularity = 'H4'
    buffer = converter.granularity_to_timedelta(granularity)
    from_with_spare = pd.Timestamp(from_str) - datetime.timedelta(hours=80)
    to_converted = pd.Timestamp(to_str)

    with patch('models.client_manager.ClientManager.load_candles_by_duration_for_hist',
               return_value=pd.DataFrame()) as mock:
        result: pd.DataFrame = libra_client._Librarian__prepare_candles(
            from_str=from_str, to_str=to_str, granularity=granularity
        )
    mock.assert_called_with(start=from_with_spare, end=to_converted, granularity=granularity)

    # Case2
    #   The period between from and to is less than 400 candles
    granularity = 'H1'
    buffer = converter.granularity_to_timedelta(granularity)
    to_converted = pd.Timestamp(to_str)
    from_with_spare = to_converted - datetime.timedelta(hours=400)

    with patch('models.client_manager.ClientManager.load_candles_by_duration_for_hist',
               return_value=pd.DataFrame()) as mock:
        result: pd.DataFrame = libra_client._Librarian__prepare_candles(
            from_str=from_str, to_str=to_str, granularity=granularity
        )
    mock.assert_called_with(start=from_with_spare, end=to_converted, granularity=granularity)


def test___adjust_time_for_merging(libra_client, win_sum_candles, hist_df):
    # instrument = 'USD_JPY'

    # Case: H1
    result = libra_client._Librarian__adjust_time_for_merging(win_sum_candles, hist_df, granularity='H1')

    nones_df = pd.DataFrame({'dst': np.full(7, None)})
    assert_series_equal(result['dst'], nones_df['dst'])
    expected_times = pd.DataFrame({'time': [
        '2020-02-17 05:00:00', '2020-02-17 08:00:00', '2020-02-17 15:00:00', '2020-03-11 17:00:00',
        '2020-03-12 01:00:00', '2020-03-13 01:00:00', '2020-03-13 08:00:00'
    ]})
    assert_series_equal(result['time'], expected_times['time'])

    # Case: H4
    result = libra_client._Librarian__adjust_time_for_merging(win_sum_candles, hist_df, granularity='H4')

    expected = pd.DataFrame({'time': [
        '2020-02-17 04:00:00', '2020-02-17 08:00:00', '2020-02-17 12:00:00', '2020-03-11 16:00:00',
        '2020-03-12 00:00:00', '2020-03-13 01:00:00', '2020-03-13 05:00:00'
    ], 'dst': [False, False, False, False, False, True, True]})
    assert_frame_equal(result, expected)


def test___detect_dst_switches(libra_client, win_sum_candles, win_sum_win_candles):
    switch_points = libra_client._Librarian__detect_dst_switches(win_sum_candles)
    expected = [
        {'time': '2020-02-17 06:00:00', 'summer_time': False},
        {'time': '2020-03-12 17:00:00', 'summer_time': True}
    ]
    assert switch_points == expected, 'index == 0 と、サマータイムの適用有無が切り替わった直後の時間を返す'

    switch_points = libra_client._Librarian__detect_dst_switches(win_sum_win_candles)
    expected = [
        {'time': '2020-02-17 06:00:00', 'summer_time': False},
        {'time': '2020-03-12 17:00:00', 'summer_time': True},
        {'time': '2020-03-13 06:00:00', 'summer_time': False},
    ]
    assert switch_points == expected, 'index == 0 と、サマータイムの適用有無が切り替わった直後の時間を何度でも返す'


# def test___merge_hist_dfs():
#     pass
