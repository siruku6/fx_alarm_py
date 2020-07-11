def ask_granularity():
    while True:
        print('取得スパンは？(ex: M5): ', end='')
        granularity = str(input())
        alphabet = granularity[0]
        if (alphabet in 'MH' and granularity[1:].isdecimal()) or (alphabet in 'DW'):
            break

        print('Invalid granularity !\n')
    return granularity


def ask_true_or_false(msg):
    ''' True か False を選択させる '''
    while True:
        print(msg, end='')
        selection = prompt_inputting_decimal()
        if selection == 1:
            return True
        elif selection == 2:
            return False
        else:
            print('[Trader] please input 1 - 2 ! >д<;')


def ask_number(msg, limit):
    ''' limit以下の数値を選択させる '''
    while True:
        print(msg, end='')
        number = prompt_inputting_decimal()
        if number > limit:
            print('[ALERT] 現在は{}までに制限しています'.format(limit))
        else:
            return number


def select_stoploss_digit():
    # print('[Trader] 通貨の価格の桁を選択して下さい [1]: 100.000, [2]: 1.00000, [3]: それ以下又は以外:', end='')
    digit_id = ask_number('[Trader] 通貨の価格の桁を選択して下さい [1]: 100.000, [2]: 1.00000, [3]: それ以下又は以外:', 3)

    if digit_id == 1:
        return 0.01

    if digit_id == 2:
        return 0.0001

    if digit_id == 3:
        return 0.00001


def select_from_dict(dictionary, menumsg='選択して下さい'):
    menu = '[interface] {}'.format(menumsg)
    for i, (key, _val) in enumerate(dictionary.items()):
        menu = '{menu} [{i}]: {key},'.format(menu=menu, i=i, key=key)
    menu = menu[0:-1] + ': '

    dict_len = len(dictionary)
    keys = list(dictionary.keys())
    while True:
        print(menu, end='')
        digit_id = prompt_inputting_decimal()
        if digit_id < dict_len:
            key = keys[digit_id]
            return key
        else:
            print('[interface] please input {} - {} ! >д<;'.format(1, dict_len))


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
