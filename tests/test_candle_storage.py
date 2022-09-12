import pandas as pd
import pytest

from src.candle_storage import FXBase


@pytest.fixture(name="dummy_candles", scope="module")
def fixture_dummy_candles() -> pd.DataFrame:
    candles: pd.DataFrame = pd.DataFrame(
        {
            "open": [100, 100, 100],
            "high": [100, 100, 100],
            "low": [100, 100, 100],
            "close": [100, 100, 100],
            "time": [100, 100, 100],
        }
    )
    yield candles


class TestSetCandles:
    def test_pass(self, dummy_candles: pd.DataFrame):
        FXBase.set_candles(dummy_candles)
        pd.testing.assert_frame_equal(FXBase.get_candles(), dummy_candles)

    def test_error(self, dummy_candles: pd.DataFrame):
        partially_missing_candles: pd.DataFrame = pd.DataFrame(
            {
                "open": [100, 100, 100],
                "High": [100, 100, 100],
                "low": [100, 100, 100],
                "close": [100, 100, 100],
                "time": [100, 100, 100],
            }
        )

        with pytest.raises(ValueError) as e_info:
            FXBase.set_candles(partially_missing_candles)

        assert e_info.value.__str__() == 'There is not the column "high" in your candles !'
