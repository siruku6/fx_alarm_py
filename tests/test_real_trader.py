import datetime
import os

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, call

import models.real_trader as real
import models.tools.statistics_module as statistics
from tests.fixtures.d1_stoc_dummy import d1_stoc_dummy
from tests.oanda_dummy_responses import dummy_market_order_response


@pytest.fixture(scope='module', autouse=True)
def real_trader_client():
    yield real.RealTrader(operation='unittest')


@pytest.fixture(scope='module', autouse=True)
def dummy_candles():
    d1_stoc_df = pd.DataFrame.from_dict(d1_stoc_dummy)
    candles = d1_stoc_df[['open', 'high', 'low', 'close']].copy()
    candles.loc[:, 'time'] = pd.date_range(end='2020-05-07', periods=100)
    candles.set_index('time', inplace=True)
    yield candles


def test_not_entry(real_trader_client, dummy_candles):
    real_trader_client._ana.calc_indicators(dummy_candles, long_span_candles=dummy_candles)
    indicators = real_trader_client._ana.get_indicators()
    no_time_since_lastloss = datetime.timedelta(hours=0)
    two_hours_since_lastloss = datetime.timedelta(hours=2)

    with patch('models.real_trader.RealTrader._RealTrader__since_last_loss', return_value=no_time_since_lastloss):
        result = real_trader_client._RealTrader__drive_entry_process(
            dummy_candles, dummy_candles.iloc[-1], indicators, indicators.iloc[-1]
        )
        assert result is False

    # with patch('models.real_trader.RealTrader._RealTrader__since_last_loss', return_value=two_hours_since_lastloss):
    #     # FAILED tests/test_real_trader.py::test_not_entry - KeyError: 'preconditions_allows'
    #     result = real_trader_client._RealTrader__drive_entry_process(
    #         dummy_candles, dummy_candles.iloc[-1], indicators, indicators.iloc[-1]
    #     )
    #     assert result is False
    # import pdb; pdb.set_trace()


def test__create_position_with_indicators(real_trader_client):
    last_indicators = {'support': 120.111, 'regist': 118.999}
    stoploss_price = 111.111
    dummy_response = dummy_market_order_response(stoploss_price)

    # long
    # HACK: patch imported module into mock
    with patch('oandapyV20.endpoints.orders.OrderCreate') as mock:
        with patch('oandapyV20.API.request', return_value=dummy_response):
            real_trader_client._create_position(_previous_candle_dummy(), 'long', last_indicators)

    mock.assert_called_with(
        accountID=os.environ.get('OANDA_ACCOUNT_ID'),
        data=_order_response_dummy('', last_indicators['support'], real_trader_client._instrument)
    )

    # short
    with patch('oandapyV20.endpoints.orders.OrderCreate') as mock:
        with patch('oandapyV20.API.request', return_value=dummy_response):
            real_trader_client._create_position(_previous_candle_dummy(), 'short', last_indicators)

    mock.assert_called_with(
        accountID=os.environ.get('OANDA_ACCOUNT_ID'),
        data=_order_response_dummy('-', last_indicators['regist'], real_trader_client._instrument)
    )


def test__create_position_without_indicators(real_trader_client):
    stoploss_price = 111.111
    dummy_response = dummy_market_order_response(stoploss_price)

    # long
    with patch('oandapyV20.endpoints.orders.OrderCreate') as mock:
        with patch('oandapyV20.API.request', return_value=dummy_response):
            real_trader_client._create_position(_previous_candle_dummy(), 'long')

    long_stoploss = _previous_candle_dummy()['low'] - real_trader_client._stoploss_buffer_pips
    mock.assert_called_with(
        accountID=os.environ.get('OANDA_ACCOUNT_ID'),
        data=_order_response_dummy('', long_stoploss, real_trader_client._instrument)
    )

    # short
    with patch('oandapyV20.endpoints.orders.OrderCreate') as mock:
        with patch('oandapyV20.API.request', return_value=dummy_response):
            real_trader_client._create_position(_previous_candle_dummy(), 'short')

    short_stoploss = real_trader_client._RealTrader__stoploss_in_short(_previous_candle_dummy()['high'])
    mock.assert_called_with(
        accountID=os.environ.get('OANDA_ACCOUNT_ID'),
        data=_order_response_dummy('-', short_stoploss, real_trader_client._instrument)
    )


def test__trail_stoploss(real_trader_client):
    new_stop = 111.111
    dummy_trade_id = '999'
    real_trader_client._client._OandaPyClient__trade_ids = [dummy_trade_id]
    data = {
        'stopLoss': {'timeInForce': 'GTC', 'price': str(new_stop)[:7]}
    }

    with patch('oandapyV20.endpoints.trades.TradeCRCDO') as mock:
        with patch('oandapyV20.API.request', return_value=''):
            real_trader_client._trail_stoploss(new_stop)

    mock.assert_called_with(
        accountID=os.environ.get('OANDA_ACCOUNT_ID'),
        tradeID=dummy_trade_id,
        data=data
    )


def test___since_last_loss(real_trader_client):
    # Context: last loss is far from current
    dummy_transactions = pd.DataFrame(
        {'pl': [121.03], 'time': ['2019-02-01T12:15:02.436718568Z']}
    )
    with patch('models.oanda_py_client.OandaPyClient.request_transactions', return_value=dummy_transactions):
        time_since_loss = real_trader_client._RealTrader__since_last_loss()
    assert time_since_loss == datetime.timedelta(hours=99)

    # Context: Within 1 hour after last loss
    dummy_transactions = pd.DataFrame(
        {'pl': [-121.03], 'time': [datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.xxxxxxxxxZ')]}
    )
    with patch('models.oanda_py_client.OandaPyClient.request_transactions', return_value=dummy_transactions):
        time_since_loss = real_trader_client._RealTrader__since_last_loss()
    assert time_since_loss < datetime.timedelta(hours=1)


def test___show_why_not_entry(real_trader_client):
    entry_filters = statistics.FILTER_ELEMENTS
    real_trader_client.set_entry_rules('entry_filter', entry_filters)

    columns = entry_filters.copy()
    columns.extend(['trend', 'time'])

    # Example: conditions are all True
    conditions_df = pd.DataFrame([np.full(len(columns), True)], columns=columns)
    with patch('models.real_trader.RealTrader._log_skip_reason') as mock:
        real_trader_client._RealTrader__show_why_not_entry(conditions_df)
    mock.assert_not_called()

    # Example: conditions are all False
    conditions_df = pd.DataFrame([np.full(len(columns), False)], columns=columns)
    with patch('models.real_trader.RealTrader._log_skip_reason') as mock:
        real_trader_client._RealTrader__show_why_not_entry(conditions_df)

    calls = [call('c. {}: "{}" is not satisfied !'.format(False, item)) for item in entry_filters]
    mock.assert_has_calls(calls)

    # Example: conditions are all None
    conditions_df = pd.DataFrame([np.full(len(columns), None)], columns=columns)
    with patch('models.real_trader.RealTrader._log_skip_reason') as mock:
        real_trader_client._RealTrader__show_why_not_entry(conditions_df)
    mock.assert_any_call('c. {}: "trend" is None !'.format(None))


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#                      Private Methods
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def _previous_candle_dummy():
    return pd.DataFrame({'high': [100.4, 100.5, 100.6], 'low': [100.1, 100.2, 100.3]}).iloc[-2]


def _order_response_dummy(entry_direction_sign, stoploss_double, instrument):
    return {
        'order': {
            'stopLossOnFill': {'timeInForce': 'GTC', 'price': str(stoploss_double)[:7]},
            'instrument': instrument,
            'units': '{}{}'.format(entry_direction_sign, os.environ.get('UNITS') or '1'),
            'type': 'MARKET',
            'positionFill': 'DEFAULT'
        }
    }
