from typing import Dict, List


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


def ask_true_or_false(msg: str) -> bool:
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


def ask_number(msg: str, limit: int) -> int:
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
    digit_id: int = ask_number(
        '[Trader] 通貨の価格の桁を選択して下さい [1]: 100.000, [2]: 1.00000, [3]: それ以下又は以外:', 3
    )
    stoploss_digit: float = 0.01
    if digit_id == 1:
        stoploss_digit = 0.01
    elif digit_id == 2:
        stoploss_digit = 0.0001
    elif digit_id == 3:
        stoploss_digit = 0.00001

    return stoploss_digit


def select_from_dict(dictionary: Dict[str, str], menumsg: str = 'Please select one from followings!') -> str:
    menu: str = '[interface] {}'.format(menumsg)
    for i, (key, _) in enumerate(dictionary.items()):
        menu = '{menu} [{i}]: {key},'.format(menu=menu, i=i + 1, key=key)
    menu = menu + ': '

    dict_len: int = len(dictionary)
    keys: List[str] = list(dictionary.keys())
    while True:
        print(menu, end='')
        digit_id: int = prompt_inputting_decimal() - 1
        if 0 <= digit_id < dict_len:
            key = keys[digit_id]
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
