import pandas as pd
import pytest

from src.candle_loader import CandleLoader
from src.candle_storage import FXBase


@pytest.fixture(name="loader_instance", scope="module")
def fixture_loader_instance(set_envs, config) -> CandleLoader:
    set_envs

    _loader: CandleLoader = CandleLoader(config)
    yield _loader


@pytest.fixture(name="dummy_candles", scope="module")
def fixture_dummy_candles():
    return pd.DataFrame.from_dict(
        [
            {"open": 100.1, "high": 100.3, "low": 100.0, "close": 100.2},
            {"open": 100.2, "high": 100.4, "low": 100.1, "close": 100.3},
        ]
    )


class TestUpdateLatestCandle:
    def update_all(self, loader_instance, dummy_candles: pd.DataFrame):
        FXBase.set_candles(dummy_candles.copy())
        latest_candle = {"open": 100.2, "high": 100.45, "low": 100.05, "close": 100.312}
        loader_instance._CandleLoader__update_latest_candle(latest_candle)
        assert FXBase.get_candles().iloc[-1].to_dict() == latest_candle

    def update_only_close(self, loader_instance, dummy_candles: pd.DataFrame):
        FXBase.set_candles(dummy_candles.copy())
        latest_candle = {"open": 100.2, "high": 100.35, "low": 100.15, "close": 100.312}
        expect = {"open": 100.2, "high": 100.4, "low": 100.1, "close": 100.312}
        loader_instance._CandleLoader__update_latest_candle(latest_candle)
        assert FXBase.get_candles().iloc[-1].to_dict() == expect
