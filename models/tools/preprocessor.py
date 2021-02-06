import urllib

import pandas as pd


def to_candle_df(response):
    ''' APIレスポンスをチャートデータに整形 '''
    if response['candles'] == []:
        return pd.DataFrame(columns=[])

    candle = pd.DataFrame.from_dict([row['mid'] for row in response['candles']])
    candle = candle.astype({
        # INFO: 'float32' の方が速度は早くなるが、不要な小数点4桁目以下が出現するので64を使用
        'c': 'float64', 'h': 'float64', 'l': 'float64', 'o': 'float64'
    })
    candle.rename(columns={'c': 'close', 'h': 'high', 'l': 'low', 'o': 'open'}, inplace=True)
    candle['time'] = [row['time'] for row in response['candles']]
    # 冗長な日時データを短縮
    # https://note.nkmk.me/python-pandas-datetime-timestamp/
    candle['time'] = pd.to_datetime(candle['time'], format='%Y-%m-%dT%H:%M:%S.000000000Z') \
                       .astype(str)
    # INFO: time ... '2018-06-03 21:00:00'
    candle['time'] = [time[:19] for time in candle.time]

    return candle


def extract_transaction_ids(response):
    top_url = response['pages'][0]
    last_url = response['pages'][-1]
    top_query = urllib.parse.urlparse(top_url).query
    last_query = urllib.parse.urlparse(last_url).query

    # INFO: top_query.split('&')[0] => from=xxxxx
    return {
        'old_id': top_query.split('&')[0][5:],
        'last_id': last_query.split('&')[1][3:]
    }


def filter_and_make_df(response_transactions, instrument):
    ''' 必要なrecordのみ残してdataframeに変換する '''
    # INFO: filtering by transaction-type
    filtered_transactions = [
        row for row in response_transactions if (
            row['type'] != 'ORDER_CANCEL'
            and row['type'] != 'MARKET_ORDER'
            # and row['type']!='MARKET_ORDER_REJECT'
        )
    ]

    hist_df = pd.DataFrame.from_dict(filtered_transactions).fillna({'pl': 0})
    hist_columns = [
        'id', 'batchID', 'tradeID',
        'tradeOpened', 'tradesClosed', 'type',
        'price', 'units', 'pl',
        'time', 'reason', 'instrument'
    ]

    # INFO: supply the columns missing
    for column_name in hist_columns:
        if column_name not in hist_df.columns:
            hist_df[column_name] = 0

    # INFO: filtering by column
    hist_df = hist_df.loc[:, hist_columns]
    hist_df['pl'] = hist_df['pl'].astype({'pl': 'float'}).astype({'pl': 'int'})
    hist_df['time'] = [row['time'][:19] for row in filtered_transactions]

    # INFO: filtering by instrument
    hist_df = __fill_instrument_for_history(hist_df.copy())
    # INFO: transaction が一切なかった場合の warning 回避のため
    hist_df['instrument'] = hist_df['instrument'].astype(str, copy=False)
    hist_df['instrument_parent'] = hist_df['instrument_parent'].astype(str, copy=False)
    hist_df = hist_df[
        (hist_df['instrument'].str.contains(instrument))
        | (hist_df['instrument_parent'].str.contains(instrument))
    ]
    return hist_df


def __fill_instrument_for_history(hist_df):
    hist_df_parent = hist_df.set_index(hist_df.id)['instrument']
    result_df = hist_df.merge(
        hist_df_parent, how='left',
        left_on='tradeID', right_index=True, suffixes=['', '_parent']
    )
    return result_df
