import math

import models.tools.mathematics as mtmtcs


def test_int_log10():
    dummy_inputs = [123.4567, 1.145678]
    expecteds = [2, 0]

    for arg, expected in zip(dummy_inputs, expecteds):
        result = mtmtcs.int_log10(arg)
        assert result == expected


def test_generate_float_digits_of():
    dummy_inputs = [-1, -2, -3, -4]
    expecteds = [0.1, 0.01, 0.001, 0.0001]

    for arg, expected in zip(dummy_inputs, expecteds):
        result = mtmtcs.generate_float_digits_of(arg)
        assert math.isclose(result, expected)


def test_range_2nd_decimal():
    dummy_inputs = [
        {'begin': 0.0, 'end': 1.0, 'step': 0.3}
    ]
    expecteds = [
        [0.0, 0.3, 0.6, 0.9]
    ]

    for args, expected in zip(dummy_inputs, expecteds):
        result = mtmtcs.range_2nd_decimal(**args)
        for val, target in zip(result, expected):
            assert math.isclose(val, target)
