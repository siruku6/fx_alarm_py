from datetime import datetime
from pandas import DataFrame

def aggregate_history(candles, hist_positions, granularity, stoploss_buffer, spread):
    ''' トレード履歴の統計情報計算処理を呼び出す '''
    long_entry_array = __calc_profit(hist_positions['long'], sign=1)
    short_entry_array = __calc_profit(hist_positions['short'], sign=-1)

    result = __calc_detaild_statistics(long_entry_array, short_entry_array)

    duration = '{start} ~ {end}'.format(
        start=candles.time[20],
        end=candles.time.tail(1).values[0]
    )
    columns = [
        'DoneTime', 'Granularity', 'StoplossBuf', 'Spread',
        'Duration', 'CandlesCnt', 'EntryCnt', 'WinRate', 'WinCnt', 'LoseCnt',
        'Gross', 'GrossProfit', 'GrossLoss', 'MaxProfit', 'MaxLoss',
        'MaxDrawdown', 'Profit Factor', 'Recovery Factor'
    ]
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    result_row = [
        now,                         # 'DoneTime'
        granularity,                 # 'Granularity'
        stoploss_buffer,             # 'StoplossBuf'
        spread,                      # 'Spread'
        duration,                    # 'Duration'
        len(candles) - 20,           # 'CandlesCnt'
        result['trades_count'],      # 'EntryCnt'
        result['win_rate'],          # 'WinRate'
        result['win_count'],         # 'WinCnt'
        result['lose_count'],        # 'LoseCnt'
        round(result['profit_sum'] * 100, 3),    # 'Gross'
        round(result['gross_profit'] * 100, 3),  # 'GrossProfit'
        round(result['gross_loss'] * 100, 3),    # 'GrossLoss'
        round(result['max_profit'] * 100, 3),    # 'MaxProfit'
        round(result['max_loss'] * 100, 3),      # 'MaxLoss'
        round(result['drawdown'] * 100, 3),      # 'MaxDrawdown'
        result['profit_factor'],                 # 'Profit Factor'
        result['recovery_factor']                # 'Recovery Factor'
    ]
    result_df = DataFrame([result_row], columns=columns)
    result_df.to_csv('tmp/verify_results.csv', encoding='shift-jis', mode='a', index=False, header=False)
    print('[Trader] トレード統計をcsv追記完了')


def __calc_profit(entry_array, sign=1):
    ''' トレード履歴の利益を計算 '''
    gross = 0
    gross_max = 0
    # INFO: pandas-dataframe化して計算するよりも速度が圧倒的に早い
    for i, row in enumerate(entry_array):
        if row['type'] == 'close':
            row['profit'] = sign * (row['price'] - entry_array[i - 1]['price'])
            gross += row['profit']
            gross_max = max(gross_max, gross)
        row['gross'] = gross
        row['drawdown'] = gross - gross_max
    return entry_array


def __calc_detaild_statistics(long_entry_array, short_entry_array):
    ''' トレード履歴の詳細な分析を行う '''
    long_count = len([row['type'] for row in long_entry_array if row['type'] == 'long'])
    short_count = len([row['type'] for row in short_entry_array if row['type'] == 'short'])

    long_profit_array = \
        [row['profit'] for row in long_entry_array if row['type'] == 'close']
    short_profit_array = \
        [row['profit'] for row in short_entry_array if row['type'] == 'close']

    profit_array \
        = [profit for profit in long_profit_array if profit > 0] \
        + [profit for profit in short_profit_array if profit > 0]
    loss_array \
        = [profit for profit in long_profit_array if profit < 0] \
        + [profit for profit in short_profit_array if profit < 0]
    max_profit = max(profit_array) if profit_array != [] else 0
    max_loss = min(loss_array) if loss_array != [] else 0

    # TODO: in 以下が空だとエラーになるバグが残っている
    max_drawdown = min([row['drawdown'] for row in (long_entry_array + short_entry_array)])
    gross_profit = sum(profit_array)
    gross_loss = sum(loss_array)

    return {
        'trades_count': long_count + short_count,
        'win_rate': round(len(profit_array) / (long_count + short_count) * 100, 2),
        'win_count': len(profit_array),
        'lose_count': len(loss_array),
        'long_count': long_count,
        'short_count': short_count,
        'profit_sum': sum(long_profit_array + short_profit_array),
        'gross_profit': gross_profit,
        'gross_loss': gross_loss,
        'max_profit': max_profit,
        'max_loss': max_loss,
        'drawdown': max_drawdown,
        'profit_factor': round(-gross_profit / gross_loss, 2),
        'recovery_factor': round((gross_profit + gross_loss) / -max_drawdown, 2)
    }
