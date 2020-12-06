import numpy as np
import pandas as pd
import pytest

import models.tools.preprocessor as prepro
from tests.fixtures.past_transactions import TRANSACTION_IDS, PAST_TRANSACTIONS, NO_PL_TRANSACTIONS


@pytest.fixture(scope='module', autouse=True)
def past_transactions():
    yield PAST_TRANSACTIONS


@pytest.fixture(scope='module', autouse=True)
def no_pl_transactions():
    yield NO_PL_TRANSACTIONS


@pytest.fixture(scope='module', autouse=True)
def expected_columns():
    yield np.array([
        'id', 'batchID', 'tradeID',
        'tradeOpened', 'tradesClosed', 'type',
        'price', 'units', 'pl',
        'time', 'reason', 'instrument', 'instrument_parent'
    ])


def test_to_candle_df(dummy_instruments):
    no_candles = prepro.to_candle_df({'candles': []})
    assert isinstance(no_candles, pd.core.frame.DataFrame)

    candles = prepro.to_candle_df(dummy_instruments)
    expected_array = ['close', 'high', 'low', 'open', 'time']
    assert (candles.columns == expected_array).all()


def test_extract_transaction_ids():
    dummy_response = TRANSACTION_IDS
    result = prepro.extract_transaction_ids(dummy_response)
    assert result == {'old_id': '2', 'last_id': '400'}


def test_filter_and_make_df(past_transactions, expected_columns):
    instrument = 'USD_JPY'
    result = prepro.filter_and_make_df(past_transactions, instrument)

    # Assert Columns
    assert (result.columns == expected_columns).all()

    # Assert filtering by Instrument
    result_filtered_again_by_instrument = \
        (result['instrument'] == instrument) | \
        (result['instrument_parent'] == instrument)
    assert len(result) == len(result_filtered_again_by_instrument)


def test_filter_and_make_df_with_no_pl(no_pl_transactions, expected_columns):
    instrument = 'USD_JPY'
    result = prepro.filter_and_make_df(no_pl_transactions, instrument)

    # # Assert Columns
    assert (result.columns == expected_columns).all()

    # Assert no error arise, it it were not for any rows
    assert len(result) == 0
