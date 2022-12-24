from datetime import datetime
from typing import Dict
from unittest.mock import patch

import pandas as pd
import pytest

from src.candle_loader import CandleLoader
from src.candle_storage import FXBase
from src.clients.oanda_accessor_pyv20.interface import OandaInterface


@pytest.fixture(name="loader_instance")
def fixture_loader_instance(set_envs, config) -> CandleLoader:
    set_envs

    _loader: CandleLoader = CandleLoader(config, OandaInterface(instrument="USD_JPY"), days=60)
    yield _loader


@pytest.fixture(name="dummy_candles", scope="module")
def fixture_dummy_candles():
    return pd.DataFrame.from_dict(
        [
            {
                "open": 100.1,
                "high": 100.3,
                "low": 100.0,
                "close": 100.2,
                "time": "2020-10-01 12:30:00",
            },
            {
                "open": 100.2,
                "high": 100.4,
                "low": 100.1,
                "close": 100.3,
                "time": "2020-10-01 12:40:00",
            },
        ]
    )


class TestRun:
    def test_not_need_request(self, loader_instance):
        with patch(
            "src.candle_loader.CandleLoader._CandleLoader__select_need_request", return_value=False
        ):
            result: Dict[str, str] = loader_instance.run()
            candles: pd.DataFrame = FXBase.get_candles(0, 10)

        assert result["info"] is None
        assert isinstance(candles, pd.DataFrame)
        assert len(candles) == 10

    # def test_operation_backtest_or_forward_test(self, loader_instance):

    def test_operation_live(self, loader_instance):
        dummy_df: pd.DataFrame = pd.read_csv("tests/fixtures/sample_candles.csv")
        with patch(
            "src.clients.oanda_accessor_pyv20.interface.OandaInterface.load_specify_length_candles",
            return_value=dummy_df,
        ):
            result: Dict[str, str] = loader_instance.run()
            candles: pd.DataFrame = FXBase.get_candles()

        assert result["info"] is None
        pd.testing.assert_frame_equal(candles, dummy_df)

    def test_invalid_operation(self, loader_instance):
        loader_instance.config.operation: str = "invalid"
        loader_instance.need_request: bool = True
        with pytest.raises(ValueError) as e_info:
            loader_instance.run()

        assert (
            e_info.value.__str__()
            == f"trader_config.operation is invalid!: {loader_instance.config.operation}"
        )


class TestSelectNeedRequest:
    def test_operation_live(self, loader_instance):
        result: bool = loader_instance._CandleLoader__select_need_request(operation="live")
        assert result is True

    def test_operation_backtest(self, loader_instance):
        selection: bool = True
        with patch("src.lib.interface.ask_true_or_false", return_value=selection):
            result: bool = loader_instance._CandleLoader__select_need_request(operation="backtest")
            assert result is selection

    def test_operation_unittest(self, loader_instance):
        result: bool = loader_instance._CandleLoader__select_need_request(operation="unittest")
        assert result is False


class TestUpdateLatestCandle:
    def test_update_all(self, loader_instance, dummy_candles: pd.DataFrame):
        FXBase.set_candles(dummy_candles.copy())
        latest_candle = {
            "open": 100.2,
            "high": 100.45,
            "low": 100.05,
            "close": 100.312,
            "time": "2020-10-01 12:40:00",
        }
        loader_instance._CandleLoader__update_latest_candle(latest_candle)
        assert FXBase.get_candles().iloc[-1].to_dict() == latest_candle

    def test_update_only_close(self, loader_instance, dummy_candles: pd.DataFrame):
        FXBase.set_candles(dummy_candles.copy())
        latest_candle = {
            "open": 100.2,
            "high": 100.35,
            "low": 100.15,
            "close": 100.312,
            "time": "2020-10-01 12:40:00",
        }
        expect = {
            "open": 100.2,
            "high": 100.4,
            "low": 100.1,
            "close": 100.312,
            "time": "2020-10-01 12:40:00",
        }
        loader_instance._CandleLoader__update_latest_candle(latest_candle)
        assert FXBase.get_candles().iloc[-1].to_dict() == expect


examples_for_detector = (
    # Case1: No missing candles
    (
        datetime(2020, 7, 8),
        datetime(2020, 7, 8, 11),
        datetime(2020, 7, 8),
        datetime(2020, 7, 8, 11),
    ),
    # Case2: No missing candles
    (
        datetime(2020, 7, 8, 1),
        datetime(2020, 7, 8, 10),
        datetime(2020, 7, 8, 11),
        datetime(2020, 7, 8),
    ),
    # Case3: No missing candles
    (
        datetime(2020, 7, 8),
        datetime(2020, 7, 8, 10),
        datetime(2020, 7, 8),
        datetime(2020, 7, 8),
    ),
    # Case4~6: There are missing candles
    (
        datetime(2020, 7, 5),
        datetime(2020, 7, 8, 10),
        datetime(2020, 7, 5),
        datetime(2020, 7, 8),
    ),
    (
        datetime(2020, 7, 8, 1),
        datetime(2020, 7, 9),
        datetime(2020, 7, 8, 11),
        datetime(2020, 7, 9),
    ),
    (
        datetime(2020, 7, 5),
        datetime(2020, 7, 9),
        datetime(2020, 7, 5),
        datetime(2020, 7, 9),
    ),
)


class TestDetectMissings:
    @pytest.mark.parametrize(
        "start, end, exp_missing_start, exp_missing_end", examples_for_detector
    )
    def test___detect_missings(
        self, start, end, exp_missing_start, exp_missing_end, loader_instance, past_usd_candles
    ):
        candles = pd.DataFrame(past_usd_candles).iloc[-12:, :]
        missing_start, missing_end = loader_instance._CandleLoader__detect_missings(
            candles, start, end
        )

        assert missing_start == exp_missing_start
        assert missing_end == exp_missing_end

    def test___detect_missings_with_no_candles(self, loader_instance):
        start = datetime(2020, 7, 6)
        end = datetime(2020, 7, 7)
        candles = pd.DataFrame([])
        missing_start, missing_end = loader_instance._CandleLoader__detect_missings(
            candles, start, end
        )

        assert missing_start == start
        assert missing_end == end
