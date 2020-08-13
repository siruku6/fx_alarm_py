import models.tools.preprocessor as prepro
from tests.oanda_dummy_responses import dummy_instruments


def test_to_candle_df():
    candles = prepro.to_candle_df(dummy_instruments)
    expected_array = ['close', 'high', 'low', 'open', 'time']

    assert (candles.columns == expected_array).all()
