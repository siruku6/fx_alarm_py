from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP  # , ROUND_HALF_EVEN
import numpy as np
from pandas import DataFrame

TRADE_RESULT_ITEMS = [
    'DoneTime', 'Rule', 'Granularity', 'StoplossBuf', 'Spread',
    'Duration', 'CandlesCnt', 'EntryCnt', 'WinRate', 'WinCnt', 'LoseCnt',
    'Gross', 'GrossProfit', 'GrossLoss', 'MaxProfit', 'MaxLoss',
    'MaxDrawdown', 'Profit Factor', 'Recovery Factor'
]
FILTER_ELEMENTS = [
    'in_the_band',
    'ma_gap_expanding',
    'sma_follow_trend',
    'stoc_allows',
    'ema60_allows',
    'band_expansion'
]


def aggregate_backtest_result(rule, df_positions, granularity, stoploss_buffer, spread, entry_filter):
    '''
    トレード履歴の統計情報計算処理を呼び出す(new)
    params:
        rule
            type:    string
            example: 'swing', 'scalping', ... etc
        df_positions
            type:    DataFrame
            columns: [
                'time',          # str ('2xxx/xx/xx hh:MM:ss')
                'position',      # str ('long', 'short', 'sell_exit', 'buy_exit' or None)
                'entry_price',   # float64
                'exitable_price' # float64
            ]
    '''
    filter_boolean = __filter_to_boolean(entry_filter)

    positions = df_positions.loc[df_positions.position.notnull(), :].copy()
    positions = __calc_profit_2(copied_positions=positions)
    positions.loc[:, 'gross'] = positions.profit.cumsum()
    positions.loc[:, 'drawdown'] = positions.gross - positions.gross.cummax()

    performance_result = __calc_performance_indicators(positions)
    __append_performance_result_to_csv(
        rule=rule,
        granularity=granularity,
        sl_buf=stoploss_buffer,
        spread=spread,
        candles=df_positions,
        performance_result=performance_result,
        filter_boolean=filter_boolean
    )
    # TODO: 要削除 一時的なコード
    positions.to_csv('./tmp/csvs/positions_dump.csv')
    return positions[['time', 'profit', 'gross']].copy()


def __filter_to_boolean(_filter):
    return [(elem in _filter) for elem in FILTER_ELEMENTS]


def __calc_profit_2(copied_positions):
    # INFO: entry したその足で exit してしまった分の profit を計算
    is_soon_exit = \
        copied_positions.exitable_price.notnull() \
        & copied_positions.entry_price.notnull() \
        & ~(copied_positions.shift(1).exitable_price.isna())
    soon_exit_positions = copied_positions[is_soon_exit]
    exit_entry_diffs = (soon_exit_positions.exitable_price - soon_exit_positions.entry_price).map(__round_really)
    copied_positions.loc[is_soon_exit, 'profit'] = np.where(
        # INFO: long か short かで正負を逆にする
        soon_exit_positions.position == 'sell_exit', exit_entry_diffs, exit_entry_diffs * -1
    )

    # INFO: entry 後、次の足までは position を持ち越した分の profit を計算
    continued_index = copied_positions.exitable_price.notnull() & ~is_soon_exit
    continued_positions = copied_positions[continued_index]
    previous_positions = copied_positions.shift(1)
    exit_entry_diffs = \
        (copied_positions.exitable_price - previous_positions.entry_price).map(__round_really)[continued_index]
    copied_positions.loc[continued_index, 'profit'] = np.where(
        # INFO: sell_exit か buy_exit かで正負を逆にする
        continued_positions.position == 'sell_exit', exit_entry_diffs, exit_entry_diffs * -1
    )

    return copied_positions


def __calc_performance_indicators(positions):
    long_cnt = len(positions[(positions.position == 'sell_exit')])
    short_cnt = len(positions[(positions.position == 'buy_exit')])
    entry_cnt = long_cnt + short_cnt
    win_positions = positions[positions.profit >= 0]
    lose_positions = positions[positions.profit < 0]
    gross_profit = win_positions.profit.sum()
    gross_loss = lose_positions.profit.sum()
    max_drawdown = positions.drawdown.min()

    return {
        'entry_count': entry_cnt,
        'win_rate': round(len(win_positions) / entry_cnt * 100, 2) if entry_cnt > 0 else '-',
        'win_count': len(win_positions),
        'lose_count': len(lose_positions),
        'long_count': long_cnt,
        'short_count': short_cnt,
        'profit_sum': positions.profit.sum(),
        'gross_profit': gross_profit,
        'gross_loss': gross_loss,
        'max_profit': win_positions.profit.max(),
        'max_loss': lose_positions.profit.min(),
        'drawdown': max_drawdown,
        'profit_factor': round(-gross_profit / gross_loss, 2) if gross_loss != 0 else '-',
        'recovery_factor': round((gross_profit + gross_loss) / -max_drawdown, 2) if max_drawdown != 0 else '-'
    }


def __append_performance_result_to_csv(rule, granularity, sl_buf, spread, candles, performance_result, filter_boolean):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    duration = '{start} ~ {end}'.format(
        start=candles.time[20],
        end=candles.iloc[-1].time
    )
    result_row = [
        now,                                # 'DoneTime'
        rule,                               # 'Rule'
        granularity,                        # 'Granularity'
        sl_buf,                             # 'StoplossBuf'
        spread,                             # 'Spread'
        duration,                           # 'Duration'
        len(candles) - 20,                  # 'CandlesCnt'
        performance_result['entry_count'],  # 'EntryCnt'
        performance_result['win_rate'],     # 'WinRate'
        performance_result['win_count'],    # 'WinCnt'
        performance_result['lose_count'],   # 'LoseCnt'
        round(performance_result['profit_sum'] * 100, 3),    # 'Gross'
        round(performance_result['gross_profit'] * 100, 3),  # 'GrossProfit'
        round(performance_result['gross_loss'] * 100, 3),    # 'GrossLoss'
        round(performance_result['max_profit'] * 100, 3),    # 'MaxProfit'
        round(performance_result['max_loss'] * 100, 3),      # 'MaxLoss'
        round(performance_result['drawdown'] * 100, 3),      # 'MaxDrawdown'
        performance_result['profit_factor'],                 # 'Profit Factor'
        performance_result['recovery_factor']                # 'Recovery Factor'
    ]
    result_df = DataFrame([result_row + filter_boolean], columns=TRADE_RESULT_ITEMS + FILTER_ELEMENTS)
    result_df.to_csv('tmp/csvs/verify_results.csv', encoding='shift-jis', mode='a', index=False, header=False)
    print('[Trader] トレード統計(vectorized)をcsv追記完了')


def __round_really(x):
    ''' 小数点第3位で四捨五入(roundでは四捨五入できないため、実装した) '''
    return float(Decimal(str(x)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP))
