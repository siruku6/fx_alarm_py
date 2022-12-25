import datetime
from unittest.mock import patch  # , MagicMock

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal
import pytest

import src.clients.oanda_accessor_pyv20.preprocessor as prepro
import src.history_visualizer as libra


#  - - - - - - - - - - - - - -
#     Preparing & Clearing
#  - - - - - - - - - - - - - -
@pytest.fixture(scope="module", name="from_iso", autouse=True)
def fixture_from_iso():
    yield "2020-01-01T12:34:56.000Z"


@pytest.fixture(scope="module", name="to_iso", autouse=True)
def fixture_to_iso():
    yield "2020-12-31T23:59:59.000Z"


@pytest.fixture(scope="module", name="libra_client")
def fixture_libra_client(from_iso, to_iso):
    with patch(
        "src.history_visualizer.select_instrument",
        return_value={"name": "USD_JPY", "spread": 0.0},
    ):
        return libra.Visualizer(from_iso, to_iso)


@pytest.fixture(scope="module", name="hist_df", autouse=True)
def fixture_hist_df():
    dummy_hist = pd.DataFrame(
        {
            "time": [
                "2020-02-17 05:12:00",
                "2020-02-17 08:59:00",
                "2020-02-17 15:27:00",
                "2020-03-11 17:31:00",
                "2020-03-12 01:01:00",
                "2020-03-13 01:14:00",
                "2020-03-13 08:48:00",
            ]
        }
    )
    yield dummy_hist


@pytest.fixture(scope="module", name="win_sum_candles", autouse=True)
def fixture_win_sum_candles():
    dummy_candles = pd.DataFrame(
        {
            "time": [
                "2020-02-17 06:00:00",
                "2020-02-17 10:00:00",
                "2020-02-17 14:00:00",
                "2020-03-12 17:00:00",
                "2020-03-12 21:00:00",
                "2020-03-13 01:00:00",
                "2020-03-13 05:00:00",
            ]
        }
    )
    yield dummy_candles


@pytest.fixture(scope="module", name="win_sum_win_candles", autouse=True)
def fixture_win_sum_win_candles():
    dummy_candles = pd.DataFrame(
        {
            "time": [
                "2020-02-17 06:00:00",
                "2020-02-17 10:00:00",
                "2020-02-17 14:00:00",
                "2020-03-12 17:00:00",
                "2020-03-12 21:00:00",
                "2020-03-13 01:00:00",
                "2020-03-13 05:00:00",
                "2020-03-13 06:00:00",
            ]
        }
    )
    yield dummy_candles


#  - - - - - - - - - - -
#    Public methods
#  - - - - - - - - - - -

#  - - - - - - - - - - -
#    Private methods
#  - - - - - - - - - - -
class TestPrepareCandles:
    def test_over_400_H4_candles(self, libra_client, from_iso, to_iso):
        """
        Case1:
            The period between from and to is more than 400 candles
        """
        # from_str = '2020-01-01T12:34:56.000'
        # to_str = '2020-01-20T12:34:56.000'
        granularity = "H4"
        _: float = prepro.granularity_to_timedelta(granularity)
        from_with_spare = pd.Timestamp(to_iso[:19]) - datetime.timedelta(hours=1600)
        to_converted = pd.Timestamp(to_iso[:19])

        with patch(
            "src.candle_loader.CandleLoader.load_candles_by_duration_for_hist",
            return_value=pd.DataFrame(),
        ) as mock:
            _: pd.DataFrame = libra_client._Visualizer__prepare_candles(granularity=granularity)
        mock.assert_called_with(
            instrument="USD_JPY",  # TODO: set not static value
            start=from_with_spare,
            end=to_converted,
            granularity=granularity,
        )

    def test_over_400_H1_candles(self, libra_client, from_iso, to_iso):
        """
        Case2
            The period between from and to is more than 400 candles
        """
        granularity = "H1"
        _: float = prepro.granularity_to_timedelta(granularity)
        to_converted = pd.Timestamp(to_iso[:19])
        from_with_spare = to_converted - datetime.timedelta(hours=400)

        with patch(
            "src.candle_loader.CandleLoader.load_candles_by_duration_for_hist",
            return_value=pd.DataFrame(),
        ) as mock:
            _: pd.DataFrame = libra_client._Visualizer__prepare_candles(granularity=granularity)
        mock.assert_called_with(
            instrument="USD_JPY",  # TODO: set not static value
            start=from_with_spare,
            end=to_converted,
            granularity=granularity,
        )


def test___adjust_time_for_merging(libra_client, win_sum_candles, hist_df):
    # instrument = 'USD_JPY'

    # Case: H1
    result = libra_client._Visualizer__adjust_time_for_merging(
        win_sum_candles, hist_df, granularity="H1"
    )

    nones_df = pd.DataFrame({"dst": np.full(7, None)})
    assert_series_equal(result["dst"], nones_df["dst"])
    expected_times = pd.DataFrame(
        {
            "time": [
                "2020-02-17 05:00:00",
                "2020-02-17 08:00:00",
                "2020-02-17 15:00:00",
                "2020-03-11 17:00:00",
                "2020-03-12 01:00:00",
                "2020-03-13 01:00:00",
                "2020-03-13 08:00:00",
            ]
        }
    )
    assert_series_equal(result["time"], expected_times["time"])

    # Case: H4
    result = libra_client._Visualizer__adjust_time_for_merging(
        win_sum_candles, hist_df, granularity="H4"
    )

    expected = pd.DataFrame(
        {
            "time": [
                "2020-02-17 04:00:00",
                "2020-02-17 08:00:00",
                "2020-02-17 12:00:00",
                "2020-03-11 16:00:00",
                "2020-03-12 00:00:00",
                "2020-03-13 01:00:00",
                "2020-03-13 05:00:00",
            ],
            "dst": [False, False, False, False, False, True, True],
        }
    )
    assert_frame_equal(result, expected)


def test___detect_dst_switches(libra_client, win_sum_candles, win_sum_win_candles):
    switch_points = libra_client._Visualizer__detect_dst_switches(win_sum_candles)
    expected = [
        {"time": "2020-02-17 06:00:00", "summer_time": False},
        {"time": "2020-03-12 17:00:00", "summer_time": True},
    ]
    assert switch_points == expected, "index == 0 と、サマータイムの適用有無が切り替わった直後の時間を返す"

    switch_points = libra_client._Visualizer__detect_dst_switches(win_sum_win_candles)
    expected = [
        {"time": "2020-02-17 06:00:00", "summer_time": False},
        {"time": "2020-03-12 17:00:00", "summer_time": True},
        {"time": "2020-03-13 06:00:00", "summer_time": False},
    ]
    assert switch_points == expected, "index == 0 と、サマータイムの適用有無が切り替わった直後の時間を何度でも返す"


def test___merge_hist_dfs(libra_client, past_usd_candles, past_transactions):
    # Case1: granularity = 'H1'
    granularity = "H1"
    candles = pd.DataFrame(past_usd_candles)
    hist_df = prepro.filter_and_make_df(past_transactions["transactions"], "USD_JPY")
    hist_df = libra_client._Visualizer__adjust_time_for_merging(candles, hist_df, granularity)
    pl_and_gross_df = libra_client._Visualizer__extract_pl(
        granularity, hist_df[["time", "pl", "dst"]]
    )
    hist_df = hist_df.drop("pl", axis=1)

    result = libra_client._Visualizer__merge_hist_dfs(candles, hist_df, pl_and_gross_df)
    result = result.loc[:, ["close", "time", "id", "reason", "type", "price", "dst", "pl"]]

    close_by_stoploss = result.iloc[27, :]
    assert np.all(
        close_by_stoploss.values
        == [
            107.397,
            "2020-07-07 03:00:00",
            "24222",
            "REPLACEMENT",
            "STOP_LOSS_ORDER",
            "107.410",
            None,
            730.0,
        ]
    )

    market_order = result.iloc[31, :]
    assert np.all(
        market_order.values
        == [
            107.632,
            "2020-07-07 07:00:00",
            "24225",
            "MARKET_ORDER",
            "ORDER_FILL",
            "107.579",
            None,
            0.0,
        ]
    )

    close_order = result.iloc[34, :]
    assert np.all(
        close_order.values
        == [
            107.707,
            "2020-07-07 10:00:00",
            "24232",
            "MARKET_ORDER_TRADE_CLOSE",
            "ORDER_FILL",
            "107.733",
            None,
            1540.0,
        ]
    )
