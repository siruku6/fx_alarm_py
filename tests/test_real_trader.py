import datetime
import os

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, call

import models.real_trader as real
import models.tools.statistics_module as statistics
from tests.fixtures.d1_stoc_dummy import d1_stoc_dummy
from tests.oanda_dummy_responses import dummy_open_trades, dummy_market_order_response


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


# INFO:
#   fixture の使い方 https://qiita.com/_akiyama_/items/9ead227227d669b0564e
@pytest.fixture(scope='module', autouse=True)
def dummy_indicators(real_trader_client, dummy_candles):
    real_trader_client._ana.calc_indicators(dummy_candles, long_span_candles=dummy_candles)
    yield real_trader_client._ana.get_indicators()


def test_not_entry(real_trader_client, dummy_candles, dummy_indicators):
    # real_trader_client._ana.calc_indicators(dummy_candles, long_span_candles=dummy_candles)
    indicators = dummy_indicators

    # Example: 最後の損失から1時間が経過していない場合
    no_time_since_lastloss = datetime.timedelta(hours=0)
    with patch('models.real_trader.RealTrader._RealTrader__since_last_loss', return_value=no_time_since_lastloss):
        result = real_trader_client._RealTrader__drive_entry_process(
            dummy_candles, dummy_candles.iloc[-1], indicators, indicators.iloc[-1]
        )
        assert result is False

    # Example: 最後の損失から1時間が経過しているが、Entry条件を満たしていない(preconditions_allows が False)
    two_hours_since_lastloss = datetime.timedelta(hours=2)
    columns = ['trend', 'preconditions_allows', 'time'] + statistics.FILTER_ELEMENTS.copy()
    tmp_dummy_candles = pd.DataFrame([[False for _ in columns]], columns=columns)
    with patch('models.real_trader.RealTrader._RealTrader__since_last_loss', return_value=two_hours_since_lastloss):
        result = real_trader_client._RealTrader__drive_entry_process(
            tmp_dummy_candles, tmp_dummy_candles.iloc[-1], indicators, indicators.iloc[-1]
        )
        assert result is False

    # Example: 最後の損失から1時間が経過し、preconditions_allows が True だが、 repulsion なし
    tmp_dummy_candles = dummy_candles.tail(10).copy()
    tmp_dummy_candles.loc[:, 'preconditions_allows'] = True
    tmp_dummy_candles.loc[:, 'trend'] = 'bull'
    tmp_dummy_candles.loc[:, 'time'] = 'xxxx-xx-xx xx:xx'
    repulsion = None
    with patch('models.real_trader.RealTrader._RealTrader__since_last_loss', return_value=two_hours_since_lastloss):
        with patch('models.trade_rules.scalping.repulsion_exist', return_value=repulsion):
            result = real_trader_client._RealTrader__drive_entry_process(
                tmp_dummy_candles, tmp_dummy_candles.iloc[-1], indicators, indicators.iloc[-1]
            )
            assert result is False

    # Example: 最後の損失から1時間が経過し、preconditions_allows が True で、 repulsion あり
    with patch('models.real_trader.RealTrader._RealTrader__since_last_loss', return_value=two_hours_since_lastloss):
        repulsion = 'long'
        with patch('models.trade_rules.scalping.repulsion_exist', return_value=repulsion):
            with patch('models.real_trader.RealTrader._create_position') as mock:
                last_indicators = indicators.iloc[-1]
                result = real_trader_client._RealTrader__drive_entry_process(
                    tmp_dummy_candles, tmp_dummy_candles.iloc[-1], indicators, last_indicators
                )
                assert result is repulsion

    pd.testing.assert_series_equal(mock.call_args[0][0], tmp_dummy_candles.iloc[-2])
    assert mock.call_args[0][1] == repulsion
    pd.testing.assert_series_equal(mock.call_args[0][2], last_indicators)


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


def test___drive_exit_process(real_trader_client):
    indicators = pd.DataFrame({'stoD_3': [10.000, None], 'stoSD_3': [30.000, None]})
    last_candle = pd.DataFrame([{'long_stoD': 25.694, 'long_stoSD': 18.522, 'stoD_over_stoSD': False}]) \
                    .iloc[-1]
    # Example: 'long'
    #   stoD_3 < stoSD_3, stoD_over_stoSD => False
    with patch('models.real_trader.RealTrader._RealTrader__settle_position', return_value=None) as mock:
        real_trader_client._RealTrader__drive_exit_process(
            'long', indicators, last_candle, preliminary=True
        )
    mock.assert_not_called()

    with patch('models.real_trader.RealTrader._RealTrader__settle_position', return_value=[]) as mock:
        real_trader_client._RealTrader__drive_exit_process(
            'long', indicators, last_candle
        )
    mock.assert_called_once()

    # Example: 'short'
    #   stoD_3 < stoSD_3, stoD_over_stoSD => False
    with patch('models.real_trader.RealTrader._RealTrader__settle_position', return_value=None) as mock:
        real_trader_client._RealTrader__drive_exit_process(
            'short', indicators, last_candle
        )
    mock.assert_not_called()
    # import pdb; pdb.set_trace()
    # TODO: testcase 不足


def test___load_position(real_trader_client):
    with patch('models.oanda_py_client.OandaPyClient.request_open_trades', return_value=[]):
        pos = real_trader_client._RealTrader__load_position()
    assert pos == {'type': 'none'}


    with patch('models.oanda_py_client.OandaPyClient.request_open_trades', return_value=dummy_open_trades):
        pos = real_trader_client._RealTrader__load_position()
    assert type(pos) is dict # '戻り値は辞書型'
    assert 'type' in pos
    assert 'price' in pos
    assert 'stoploss' in pos


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
