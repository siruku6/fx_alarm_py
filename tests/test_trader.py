from unittest.mock import patch
import pytest
import pandas as pd
from pandas.testing import assert_series_equal

from models.candle_storage import FXBase
import models.trader as trader
import models.real_trader as real


@pytest.fixture(scope='module')
def trader_instance():
    with patch('models.trader.Trader.get_instrument', return_value='USD_JPY'):
        _trader = trader.Trader(operation='unittest')
        yield _trader
        _trader._client._ClientManager__oanda_client._OandaClient__api_client.client.close()


@pytest.fixture(scope='module')
def real_trader_instance():
    with patch('models.trader.Trader.get_instrument', return_value='USD_JPY'):
        real_trader = real.RealTrader(operation='unittest')
        yield real_trader
        real_trader._client._ClientManager__oanda_client._OandaClient__api_client.client.close()

@pytest.fixture(scope='module')
def dummy_trend_candles():
    return pd.DataFrame.from_dict([
        {'high': 110.0, 'low': 108.5, 'bull': False, 'bear': False, 'result': None},
        {'high': 110.0, 'low': 108.5, 'bull': False, 'bear': False, 'result': None},
        {'high': 110.0, 'low': 108.5, 'bull': False, 'bear': False, 'result': None},
        {'high': 110.0, 'low': 108.5, 'bull': False, 'bear': False, 'result': None},
        {'high': 110.0, 'low': 108.5, 'bull': False, 'bear': False, 'result': None},
        {'high': 110.0, 'low': 108.5, 'bull': False, 'bear': False, 'result': None},
        {'high': 110.0, 'low': 108.5, 'bull': False, 'bear': False, 'result': None},
        {'high': 110.0, 'low': 108.5, 'bull': False, 'bear': False, 'result': None},
        {'high': 110.0, 'low': 108.5, 'bull': False, 'bear': False, 'result': None},
        {'high': 110.0, 'low': 108.5, 'bull': False, 'bear': False, 'result': None},
        {'high': 111.0, 'low': 108.5, 'bull': True, 'bear': False, 'result': 'long'},
        {'high': 110.0, 'low': 107.5, 'bull': False, 'bear': True, 'result': 'short'},
        {'high': 111.0, 'low': 108.5, 'bull': True, 'bear': False, 'result': 'long'},
        {'high': 110.0, 'low': 107.5, 'bull': False, 'bear': True, 'result': 'short'},
        {'high': 112.0, 'low': 106.5, 'bull': False, 'bear': False, 'result': None}
    ], orient='columns')


def test__accurize_entry_prices():
    pass
    # self.__trader._Trader__accurize_entry_prices()


def test___update_latest_candle(trader_instance):
    dummy_candles = pd.DataFrame.from_dict([
        {'open': 100.1, 'high': 100.3, 'low': 100.0, 'close': 100.2},
        {'open': 100.2, 'high': 100.4, 'low': 100.1, 'close': 100.3},
    ])

    # Example1: the latest high > the previous high,
    #   and the latest low < the previous low
    FXBase.set_candles(dummy_candles.copy())
    latest_candle = {'open': 100.2, 'high': 100.45, 'low': 100.05, 'close': 100.312}
    trader_instance._Trader__update_latest_candle(latest_candle)
    assert FXBase.get_candles().iloc[-1].to_dict() == latest_candle

    # Example2: the latest high < the previous high,
    #   and the latest low > the previous low
    FXBase.set_candles(dummy_candles.copy())
    latest_candle = {'open': 100.2, 'high': 100.35, 'low': 100.15, 'close': 100.312}
    expect = {'open': 100.2, 'high': 100.4, 'low': 100.1, 'close': 100.312}
    trader_instance._Trader__update_latest_candle(latest_candle)
    assert FXBase.get_candles().iloc[-1].to_dict() == expect


def test___generate_thrust_column(real_trader_instance, dummy_trend_candles):
    dummy_df = dummy_trend_candles
    result = real_trader_instance._Trader__generate_thrust_column(
        candles=dummy_df[['high', 'low']], trend=dummy_df[['bull', 'bear']]
    ).rename('result')
    assert_series_equal(dummy_df['result'], result)


def test___generate_band_expansion_column(real_trader_instance):
    test_df = pd.DataFrame.from_dict([
        {'sigma*2_band': 110.0, 'sigma*-2_band': 108.5},
        {'sigma*2_band': 110.1, 'sigma*-2_band': 108.6},
        {'sigma*2_band': 110.0, 'sigma*-2_band': 108.3},
        {'sigma*2_band': 110.1, 'sigma*-2_band': 108.6}
    ], orient='columns')
    result = real_trader_instance._Trader__generate_band_expansion_column(df_bands=test_df)
    assert result.iat[-2]
    assert not result.iat[-1]
