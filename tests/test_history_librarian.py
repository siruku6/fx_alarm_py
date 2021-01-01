import pytest
from unittest.mock import patch  # , MagicMock

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal

import models.history_librarian as libra
from tests.fixtures.past_transactions import NO_PL_TRANSACTIONS


#  - - - - - - - - - - - - - -
#     Preparing & Clearing
#  - - - - - - - - - - - - - -
@pytest.fixture(scope='module', autouse=True)
def libra_client():
    with patch('models.client_manager.ClientManager.select_instrument',
            return_value=['USD_JPY', {'spread': 0.0}]):
        yield libra.Librarian()


@pytest.fixture(scope='module', autouse=True)
def hist_df():
    dummy_hist = pd.DataFrame({'time': [
        '2020-02-17 05:12:00', '2020-02-17 08:59:00', '2020-02-17 15:27:00', '2020-03-11 17:31:00',
        '2020-03-12 01:01:00', '2020-03-13 01:14:00', '2020-03-13 08:48:00'
    ]})
    yield dummy_hist


@pytest.fixture(scope='module', autouse=True)
def no_pl_transactions():
    yield NO_PL_TRANSACTIONS


@pytest.fixture(scope='module', autouse=True)
def win_sum_candles():
    dummy_candles = pd.DataFrame({'time': [
        '2020-02-17 06:00:00', '2020-02-17 10:00:00', '2020-02-17 14:00:00', '2020-03-12 17:00:00',
        '2020-03-12 21:00:00', '2020-03-13 01:00:00', '2020-03-13 05:00:00'
    ]})
    yield dummy_candles


@pytest.fixture(scope='module', autouse=True)
def win_sum_win_candles():
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
