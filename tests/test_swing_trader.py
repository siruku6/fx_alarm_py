# from typing import Dict, List, Union

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from src.swing_trader import SwingTrader


@pytest.fixture(name='swing_client', scope='module', autouse=True)
def fixture_swing_client(set_envs):
    with patch('src.trader_config.TraderConfig.get_instrument', return_value='USD_JPY'):
        set_envs

        _trader: SwingTrader = SwingTrader(operation='unittest')
        yield _trader
        _trader._client._ClientManager__oanda_client._OandaClient__api_client.client.close()


class TestSetStoplossPrices:
    # @pytest.fixture(name='h1_candles', scope='module')
    # def fixture_h1_candles(self, past_usd_candles: List[Dict[str, Union[float, str, int]]]) -> pd.DataFrame:
    #     return pd.DataFrame(past_usd_candles)

    def test_format(self, swing_client: SwingTrader):
        dummy_candles: pd.DataFrame = pd.DataFrame(
            [
                {'high': 111.222, 'low': 123.456},
                {'high': 111.222, 'low': 123.456}
            ]
        )
        result: pd.DataFrame = swing_client._SwingTrader__set_stoploss_prices(
            dummy_candles.copy(),
            entry_direction=np.array([np.nan, 'long'])
        )
        np.testing.assert_array_equal(result.columns, ['high', 'low', 'possible_stoploss'])
        assert result['possible_stoploss'].dtype == np.float64

    def test_basic(self, swing_client: SwingTrader, stoploss_buffer: float):
        dummy_candles: pd.DataFrame = pd.DataFrame(
            [
                {'high': 111.222, 'low': 123.456},
                {'high': 111.222, 'low': 123.456},
                {'high': 111.222, 'low': 123.456},
                {'high': 111.222, 'low': 123.456}
            ]
        )
        result: pd.DataFrame = swing_client._SwingTrader__set_stoploss_prices(
            dummy_candles.copy(),
            entry_direction=np.array([np.nan, 'long', 'short', 'short'])
        )

        expected: pd.DataFrame = dummy_candles
        expected.loc[1, 'possible_stoploss'] = expected.loc[1, 'low'] - stoploss_buffer
        expected.loc[2:4, 'possible_stoploss'] = expected.loc[2:4, 'high'] + stoploss_buffer
        pd.testing.assert_frame_equal(result, expected)
