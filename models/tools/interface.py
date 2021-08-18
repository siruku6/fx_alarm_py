import typing as t


def ask_granularity() -> str:
    while True:
        error_msg: str = 'Invalid granularity !\n'

        print('取得スパンは？(ex: M5): ', end='')
        granularity: str = str(input())
        if len(granularity) == 0:
            print(error_msg)
            continue

        alphabet: str = granularity[0]
        if not((alphabet in 'MH' and granularity[1:].isdecimal()) or (alphabet in 'DW')):
            print(error_msg)
            continue

        break
    return granularity


def ask_true_or_false(msg) -> bool:
    ''' True か False を選択させる '''
    while True:
        print(msg, end='')
        selection: int = prompt_inputting_decimal()
        if selection == 1:
            return True
        elif selection == 2:
            return False
        else:
            print('[Trader] please input 1 - 2 ! >д<;')


def ask_number(msg, limit) -> int:
    ''' limit以下の数値を選択させる '''
    while True:
        print(msg, end='')
        number: int = prompt_inputting_decimal()
        if number > limit:
            print('[ALERT] 現在は{}までに制限しています'.format(limit))
        else:
            return number


def select_stoploss_digit() -> float:
    # print('[Trader] 通貨の価格の桁を選択して下さい [1]: 100.000, [2]: 1.00000, [3]: それ以下又は以外:', end='')
    digit_id: int = ask_number('[Trader] 通貨の価格の桁を選択して下さい [1]: 100.000, [2]: 1.00000, [3]: それ以下又は以外:', 3)

    if digit_id == 1:
        return 0.01

    if digit_id == 2:
        return 0.0001

    if digit_id == 3:
        return 0.00001


def select_from_dict(dictionary: t.Dict[str, str], menumsg='選択して下さい') -> str:
    menu: str = '[interface] {}'.format(menumsg)
    for i, (key, _) in enumerate(dictionary.items()):
        menu: str = '{menu} [{i}]: {key},'.format(menu=menu, i=i, key=key)
    menu: str = menu[0:-1] + ': '

    dict_len: int = len(dictionary)
    keys: t.List[str] = list(dictionary.keys())
    while True:
        print(menu, end='')
        digit_id: int = prompt_inputting_decimal()
        if digit_id < dict_len:
            key: str = keys[digit_id]
            return key
        else:
            print('[interface] please input {} - {} ! >д<;'.format(1, dict_len))


def prompt_inputting_decimal() -> int:
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
        selection: str = input()
        if selection.isdecimal():
            return int(selection)
        else:
            print('Please, input the positive value (integer) ! \nINPUT AGAIN: ', end='')
