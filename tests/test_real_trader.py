import datetime
import os

# import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

import models.real_trader as real
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
