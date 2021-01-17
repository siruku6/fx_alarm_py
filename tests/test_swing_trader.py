import pytest
from unittest.mock import patch

import models.trader as trader
import models.swing_trader as swing


@pytest.fixture(scope='module', autouse=True)
def swing_client():
    with patch('models.trader.Trader.get_instrument', return_value='USD_JPY'):
        yield swing.SwingTrader(operation='unittest')


def test___add_candle_duration(swing_client):
    with patch('models.trader.Trader.get_entry_rules', return_value='M5'):
        result = swing_client._SwingTrader__add_candle_duration('2020-04-10 10:10:18')
        assert result == '2020-04-10 10:14:18'
    with patch('models.trader.Trader.get_entry_rules', return_value='H4'):
        result = swing_client._SwingTrader__add_candle_duration('2020-04-10 10:10:18')
        assert result == '2020-04-10 14:09:18'
    with patch('models.trader.Trader.get_entry_rules', return_value='D'):
        result = swing_client._SwingTrader__add_candle_duration('2020-04-10 10:10:18')
        assert result == '2020-04-11 10:09:18'
