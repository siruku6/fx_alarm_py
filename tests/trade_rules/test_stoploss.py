import numpy as np
import pytest

import models.trade_rules.stoploss as stoploss_strategy


class TestPreviousCandleOtherside():
    PARAMETERS = (
        (None, 101.001, 101.988, 100.882, None),
        ('long', 101.001, 101.988, 100.970, 100.971),
        ('long', 101.001, 101.988, 100.972, 100.972),
        ('short', 101.001, 101.988, 102.033, 102.032),
        ('short', 101.001, 101.988, 102.031, 102.031),
        (np.nan, 101.001, 101.988, 102.031, None)
    )

    @pytest.mark.parametrize(
        'position_type, previous_low, previous_high, old_stoploss, expected',
        PARAMETERS
    )
    def test_basic(
        self, position_type, previous_low, previous_high, old_stoploss, expected, config
    ):
        config.set_entry_rules('static_spread', 0.014)
        config.set_entry_rules('stoploss_buffer_pips', 0.03)

        result: float = stoploss_strategy.previous_candle_otherside(
            position_type, previous_low, previous_high, old_stoploss, config
        )
        if result is None:
            assert result is expected
        else:
            np.testing.assert_almost_equal(result, expected)


class TestSupportOrResistance:
    PARAMETERS = [
        ('long', 120.0, 140.0, np.nan, 120.0),
        ('long', 120.0, 140.0, 110.0, 120.0),
        ('long', 120.0, 140.0, 130.0, np.nan),
        ('short', 120.0, 140.0, np.nan, 140.0),
        ('short', 120.0, 140.0, 150.0, 140.0),
        ('short', 120.0, 140.0, 130.0, np.nan)
    ]

    @pytest.mark.parametrize(
        'position_type, current_sup, current_regist, old_stoploss, expected',
        PARAMETERS
    )
    def test_new_stoploss_price(self, position_type, current_sup, current_regist, old_stoploss, expected):
        stoploss = stoploss_strategy.support_or_registance(
            position_type, current_sup, current_regist, old_stoploss
        )
        assert stoploss == expected or stoploss is expected
