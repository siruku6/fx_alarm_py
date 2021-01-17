import math


def int_log10(number):
    '''
    calcuate digits number of integer part

    Parameters
    ----------
    number : integer, float or double (any types of number)
        but only > 1.0

    Returns
    -------
    integer

    Example
    -------
    int_log10(1234) -> 3
    int_log10(1.234567) -> 0
    int_log10(12.345) -> 1
    '''
    return int(math.log10(number))


def generate_float_digits_of(digit):
    '''
    generate float value

    Parameters
    ----------
    digit : integer

    Returns
    -------
    float (only negative)

    Example
    -------
    generate_float_digits_of(-1) -> 0.1
    generate_float_digits_of(-2) -> 0.01
    generate_float_digits_of(-3) -> 0.001
    '''
    return float('0.' + '0' * (-digit - 1) + '1')


def range_2nd_decimal(begin, end, step):
    return list(__calc(begin, end, step))


def __calc(begin, end, step):
    decimal_num = begin

    while decimal_num < end:
        yield round(decimal_num, 5)
        decimal_num += step
