import math


def int_digits(number):
    '''
    calcuate digits number of integer part

    Parameters
    ----------
    number : integer, float or double (any types of number)

    Returns
    -------
    integer

    Example
    -------
    int_digits(1234) -> 4
    int_digits(1.234567) -> 1
    int_digits(12.345) -> 2
    '''
    return int(math.log10(number) + 1)


def generate_float_digits_of(digit):
    '''
    generate float value

    Parameters
    ----------
    digit : integer

    Returns
    -------
    float

    Example
    -------
    generate_float_digits_of(1) -> 0.1
    generate_float_digits_of(2) -> 0.01
    generate_float_digits_of(3) -> 0.001
    '''
    return float('0.' + '0' * (digit - 1) + '1')


def range_2nd_decimal(begin, end, step):
    return list(__calc(begin, end, step))


def __calc(begin, end, step):
    decimal_num = begin

    while decimal_num < end:
        yield round(decimal_num, 5)
        decimal_num += step
