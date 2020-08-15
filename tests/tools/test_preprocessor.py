import numpy as np
import pandas as pd
import pytest

import models.tools.preprocessor as prepro
from tests.oanda_dummy_responses import dummy_instruments
from tests.fixtures.past_transactions import PAST_TRANSACTIONS, NO_PL_TRANSACTIONS


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


def test_to_candle_df():
    no_candles = prepro.to_candle_df({'candles': []})
    assert type(no_candles) == pd.core.frame.DataFrame

    candles = prepro.to_candle_df(dummy_instruments)
    expected_array = ['close', 'high', 'low', 'open', 'time']
    assert (candles.columns == expected_array).all()


def test_extract_transaction_ids():
    dummy_response = {
        "count": 2124,
        "from": "2016-06-24T21:03:50.914647476Z",
        "lastTransactionID": "2124",
        "pageSize": 100,
        "to": "2016-10-05T06:54:14.025946546Z",
        "pages": [
            "https://api-fxpractice.oanda.com/v3/accounts/101-004-1435156-001/transactions/idrange?from=2&to=100",
            "https://api-fxpractice.oanda.com/v3/accounts/101-004-1435156-001/transactions/idrange?from=101&to=200",
            "https://api-fxpractice.oanda.com/v3/accounts/101-004-1435156-001/transactions/idrange?from=201&to=300",
            "https://api-fxpractice.oanda.com/v3/accounts/101-004-1435156-001/transactions/idrange?from=301&to=400"
        ]
    }
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
    # TODO:
    #   FutureWarning: elementwise comparison failed; returning scalar instead,
    #   but in the future will perform elementwise comparison
    result = prepro.filter_and_make_df(no_pl_transactions, instrument)

    # # Assert Columns
    assert (result.columns == expected_columns).all()

    # Assert no error arise, it it were not for any rows
    assert len(result) == 0
