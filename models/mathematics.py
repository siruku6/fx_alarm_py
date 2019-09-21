def range_2nd_decimal(begin, end, step):
    return list(calc(begin, end, step))

def calc(begin, end, step):
    decimal_num = begin

    while decimal_num < end:
        yield round(decimal_num, 5)
        decimal_num += step
