import numpy as np
import pytest

import models.trade_rules.stoploss as stoploss_strategy


class TestStepTrailing():
    PARAMETERS = (
        (None, 101.001, 101.988, None),
        ('long', 101.001, 101.988, 100.971),
        ('short', 101.001, 101.988, 102.032),
        (np.nan, 101.001, 101.988, None)
    )

    @pytest.mark.parametrize(
        'position_type, previous_low, previous_high, expected',
        PARAMETERS
    )
    def test_basic(
        self, position_type, previous_low, previous_high, expected, config
    ):
        config.set_entry_rules('static_spread', 0.014)
        config.set_entry_rules('stoploss_buffer_pips', 0.03)

        result: float = stoploss_strategy.step_trailing(
            position_type, previous_low, previous_high, config
        )
        if result is None:
            assert result is expected
        else:
            np.testing.assert_almost_equal(result, expected)


class TestSupportOrResistance:
    PARAMETERS = [
        ('long', 120.0, 140.0, 120.0),
        (np.nan, 120.0, 140.0, None),
        ('short', 120.0, 140.0, 140.0),
        (None, 120.0, 140.0, None)
    ]

    @pytest.mark.parametrize(
        'position_type, current_sup, current_regist, expected',
        PARAMETERS
    )
    def test_new_stoploss_price(self, position_type, current_sup, current_regist, expected):
        result = stoploss_strategy.support_or_registance(
            position_type, current_sup, current_regist
        )
        if result is None:
            assert result is expected
        else:
            assert result == expected
