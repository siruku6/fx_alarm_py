def range_2nd_decimal(begin, end, step):
    return list(calc(begin, end, step))


def calc(begin, end, step):
    decimal_num = begin

    while decimal_num < end:
        yield round(decimal_num, 5)
        decimal_num += step


def prompt_inputting_decimal():
    '''
    整数を入力させ、int型にして返す

    Parameters
    ----------
    -

    Returns
    -------
    int: decimal
    '''
    while True:
        selection = input()
        if selection.isdecimal():
            return int(selection)
        else:
            print('Please, input the positive value (integer) ! \nINPUT AGAIN: ', end='')
