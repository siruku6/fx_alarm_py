import numpy as np
import pytest

import models.tools.preprocessor as prepro
from tests.oanda_dummy_responses import dummy_instruments
from tests.fixtures.past_transactions import PAST_TRANSACTIONS


@pytest.fixture(scope='module', autouse=True)
def past_transactions():
    yield PAST_TRANSACTIONS


def test_to_candle_df():
    candles = prepro.to_candle_df(dummy_instruments)
    expected_array = ['close', 'high', 'low', 'open', 'time']

    assert (candles.columns == expected_array).all()


def test_filter_and_make_df(past_transactions):
    instrument='USD_JPY'
    result = prepro.filter_and_make_df(past_transactions, instrument)

    # Assert Columns
    expected_columns = np.array([
        'id', 'batchID', 'tradeID',
        'tradeOpened', 'tradesClosed', 'type',
        'price', 'units', 'pl',
        'time', 'reason', 'instrument', 'instrument_parent'
    ])
    assert (result.columns == expected_columns).all()

    # Assert filtering by Instrument
    result_filtered_again_by_instrument = \
        (result['instrument'] == instrument) | \
        (result['instrument_parent'] == instrument)
    assert len(result) == len(result_filtered_again_by_instrument)

