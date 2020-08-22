from unittest.mock import patch
import pytest
import pandas as pd

from models.candle_storage import FXBase
import models.trader as trader
import models.real_trader as real


@pytest.fixture(scope='module')
def trader_instance():
    with patch('models.trader.Trader.get_instrument', return_value='USD_JPY'):
        _trader = trader.Trader(operation='unittest')
        yield _trader
        _trader._client._OandaPyClient__api_client.client.close()


@pytest.fixture(scope='module')
def real_trader_instance():
    with patch('models.trader.Trader.get_instrument', return_value='USD_JPY'):
        real_trader = real.RealTrader(operation='unittest')
        yield real_trader
        real_trader._client._OandaPyClient__api_client.client.close()


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


def test__generate_band_expansion_column(real_trader_instance):
    test_df = pd.DataFrame.from_dict([
        {'band_+2σ': 110.0, 'band_-2σ': 108.5},
        {'band_+2σ': 110.1, 'band_-2σ': 108.6},
        {'band_+2σ': 110.0, 'band_-2σ': 108.3},
        {'band_+2σ': 110.1, 'band_-2σ': 108.6}
    ], orient='columns')
    result = real_trader_instance._Trader__generate_band_expansion_column(df_bands=test_df)
    assert result.iat[-2]
    assert not result.iat[-1]
