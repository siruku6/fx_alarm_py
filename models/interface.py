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
    while True:
        print('[Trader] 通貨の価格の桁を選択して下さい [1]: 100.000, [2]: 1.00000, [3]: それ以下又は以外:', end='')
        digit_id = prompt_inputting_decimal()
        if digit_id == 1:
            return 0.01
        elif digit_id == 2:
            return 0.0001
        elif digit_id == 3:
            return 0.00001
        else:
            print('[Trader] please input 1 - 3 ! >д<;')


def select_from_dict(dictionary, menumsg='選択して下さい'):
    menu = '[interface] {}'.format(menumsg)
    min_num = min(dictionary.keys())
    max_num = max(dictionary.keys())
    dict_len = len(dictionary)
    for i, (key, val) in enumerate(dictionary.items()):
        menu = '{menu} [{key}]:{val},'.format(menu=menu, key=key, val=val)

    menu = menu[0:-1] + ': '

    while True:
        print(menu, end='')
        digit_id = prompt_inputting_decimal()
        if digit_id in dictionary:
            return dictionary[digit_id]
        else:
            print('[interface] please input {} - {} ! >д<;'.format(min_num, max_num))


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
