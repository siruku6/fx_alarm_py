import datetime
import time
from typing import List
from collections import OrderedDict
import pandas as pd

from models.clients.oanda_client import OandaClient
from models.clients.dynamodb_accessor import DynamodbAccessor
import models.tools.format_converter as converter
import models.tools.interface as i_face
import models.tools.preprocessor as prepro

# pd.set_option('display.max_rows', candles_count)  # 表示可能な最大行数を設定


class ClientManager():
    @classmethod
    def select_instrument(cls, instrument=None):
        # TODO: 正しいspreadを後で確認して設定する
        instruments = OrderedDict(
            USD_JPY={'spread': 0.004},
            EUR_USD={'spread': 0.00014},
            GBP_JPY={'spread': 0.014},
            USD_CHF={'spread': 0.00014}
        )
        if instrument is not None:
            return instrument, instruments[instrument]

        instrument = i_face.select_from_dict(instruments, menumsg='通貨ペアは？\n')
        return instrument, instruments[instrument]

    def __init__(self, instrument, test=False):
        self.__instrument = instrument
        self.__oanda_client = OandaClient(instrument=self.__instrument, test=test)

    # INFO: request-candles
    def load_specify_length_candles(self, length=60, granularity='M5'):
        ''' チャート情報を更新 '''
        response = self.__oanda_client.query_instruments(
            candles_count=length,
            granularity=granularity,
        )

        candles = prepro.to_candle_df(response)
        return {'success': '[Watcher] Oandaからのレート取得に成功', 'candles': candles}

    def load_long_chart(self, days=0, granularity='M5'):
        ''' 長期間のチャート取得のために複数回APIリクエスト '''
        remaining_days = days
        candles = None
        requestable_max_days = self.__calc_requestable_max_days(granularity=granularity)

        last_datetime = datetime.datetime.utcnow()
        while remaining_days > 0:
            start_datetime = last_datetime - datetime.timedelta(days=remaining_days)
            remaining_days -= requestable_max_days
            if remaining_days < 0: remaining_days = 0
            end_datetime = last_datetime - datetime.timedelta(days=remaining_days)

            response = self.__oanda_client.query_instruments(
                start=converter.to_oanda_format(start_datetime),
                end=converter.to_oanda_format(end_datetime),
                granularity=granularity
            )
            tmp_candles = prepro.to_candle_df(response)
            candles = self.__union_candles_distinct(candles, tmp_candles)
            print('[Client] Remaining: {remaining_days} days'.format(remaining_days=remaining_days))
            time.sleep(1)

        return {'success': '[Watcher] APIリクエスト成功', 'candles': candles}

    def load_candles_by_duration(self, start, end, granularity):
        ''' 広範囲期間チャート取得用の複数回リクエスト '''
        candles = None
        requestable_duration = self.__calc_requestable_time_duration(granularity)
        next_starttime = start
        next_endtime = self.__minimize_period(start, end, requestable_duration)

        while next_starttime < end:
            now = datetime.datetime.utcnow() - datetime.timedelta(minutes=1)
            if now < next_endtime: next_endtime = now
            response = self.__oanda_client.query_instruments(
                start=converter.to_oanda_format(next_starttime),
                end=converter.to_oanda_format(next_endtime),
                granularity=granularity
            )
            tmp_candles = prepro.to_candle_df(response)
            candles = self.__union_candles_distinct(candles, tmp_candles)
            print('取得済み: {datetime}まで'.format(datetime=next_endtime))
            time.sleep(1)

            next_starttime += requestable_duration
            next_endtime += requestable_duration

        return {'success': '[Client] APIリクエスト成功', 'candles': candles}

    def __minimize_period(self, start: datetime, end: datetime, requestable_duration) -> datetime:
        possible_end: datetime = start + requestable_duration
        next_end: datetime = possible_end if possible_end < end else end
        return next_end

    def load_candles_by_duration_for_hist(self, start, end, granularity):
        ''' Prepare candles with specifying the range of datetime '''
        # 1. DynamoDBからのデータ取得
        table_name = '{}_CANDLES'.format(granularity)
        dynamo = DynamodbAccessor(self.__instrument, table_name=table_name)
        records = dynamo.list_records(
            # INFO: 若干広めの時間をとっている
            #   休日やらタイミングやらで、start, endを割り込むデータしか取得できないことがありそうなため
            # TODO: 範囲は3日などでなく、granuralityに応じて可変にした方が良い
            (start - datetime.timedelta(days=3)).isoformat(),
            (end + datetime.timedelta(days=1)).isoformat()
        )
        candles = converter.to_candles_from_dynamo(records)
        if self.__oanda_client.accessable is False:
            print('[Manager] Skipped requesting candles from Oanda')
            return candles

        # 2. データが不足している期間を特定する
        missing_start, missing_end = self.__detect_missings(candles, start, end)
        if missing_end <= missing_start:
            return candles

        # 3. 不足があった場合は補う
        missed_candles = self.load_candles_by_duration(
            missing_start, missing_end, granularity=granularity
        )['candles']
        # INFO: start, endともに市場停止時間帯にだった場合、missed_candles は空配列になる
        #   その場合は insert, union をスキップ
        if len(missed_candles) > 0:
            dynamo.batch_insert(items=missed_candles.copy())
            candles = self.__union_candles_distinct(candles, missed_candles)

        return candles

    def __detect_missings(self, candles: pd.DataFrame,
                          required_start: datetime, required_end: datetime) -> List:
        '''
        Parameters
        ----------
        candles : pandas.DataFrame
            Columns :

        required_start : datetime
            Example : datetime.datetime(2020, 1, 2, 12, 34)
        required_end : datetime

        Returns
        -------
        Array: [missing_start, missing_end]
            missing_start : datetime
            missing_end : datetime
        '''
        if len(candles) == 0:
            return required_start, required_end

        # 1. DBから取得したデータの先頭と末尾の日時を取得
        stocked_first: datetime = converter.str_to_datetime(candles.iloc[0]['time'])
        stocked_last: datetime = converter.str_to_datetime(candles.iloc[-1]['time'])
        ealiest: datetime = min(required_start, required_end, stocked_first, stocked_last)
        latest: datetime = max(required_start, required_end, stocked_first, stocked_last)

        # 2. どの期間のデータが不足しているのかを判別
        missing_start: datetime = required_start if ealiest == required_start else stocked_last
        missing_end: datetime = required_end if latest == required_end else stocked_first
        return missing_start, missing_end

    def call_oanda(self, method, **kwargs):
        method_dict = {
            'is_tradeable': self.__oanda_client.request_is_tradeable,
            'open_trades': self.__oanda_client.request_open_trades,
            'transactions': self.__request_latest_transactions,
            'current_price': self.request_current_price,
        }
        return method_dict.get(method)(**kwargs)

    def order_oanda(self, method_type, **kwargs):
        method_dict = {
            'entry': self.__oanda_client.request_market_ordering,
            'trail': self.__oanda_client.request_trailing_stoploss,
            'exit': self.__oanda_client.request_closing
        }
        return method_dict.get(method_type)(**kwargs)

    def request_current_price(self):
        # INFO: .to_dictは、単にコンソールログの見やすさ向上のために使用中
        latest_candle = self.load_specify_length_candles(length=1, granularity='M1')['candles'] \
                            .iloc[-1].to_dict()
        return latest_candle

    def prepare_one_page_transactions(self):
        # INFO: lastTransactionIDを取得するために実行
        # self.__oanda_client.request_open_trades()
        self.call_oanda('open_trades')

        # preapre history_df: trade-history
        history_df = self.__request_latest_transactions()
        history_df.to_csv('./tmp/csvs/hist_positions.csv', index=False)
        return history_df

    def request_massive_transactions(self, from_str: str, to_str: str) -> pd.DataFrame:
        gained_transactions = []

        from_id: str
        to_id: str
        from_id, to_id = self.__oanda_client.request_transaction_ids(from_str, to_str)
        if from_id is None or to_id is None:
            return pd.DataFrame([])

        while True:
            print('[INFO] requesting {}..{}'.format(from_id, to_id))

            response = self.__oanda_client.request_transactions_once(from_id, to_id)
            tmp_transactons = response['transactions']
            gained_transactions += tmp_transactons

            # INFO: ループの終了条件
            #   'to' に指定した ID の transaction がない時が多々あり、
            #   その場合、transactions を取得できないので、ごくわずかな数になる。
            #   そこまで来たら処理終了
            if len(tmp_transactons) <= 10 or str(int(tmp_transactons[-1]['id']) + 1) >= to_id:
                break

            gained_last_transaction_id: str = tmp_transactons[-1]['id']
            print('[INFO] last_transaction_id {}'.format(gained_last_transaction_id))
            from_id: str = str(int(gained_last_transaction_id) + 1)

        filtered_df = prepro.filter_and_make_df(gained_transactions, self.__instrument)
        return filtered_df

    def __request_latest_transactions(self, count=999):
        # TODO: last_transaction_id は ClientManager のインスタンス変数にする
        to_id = int(self.__oanda_client.last_transaction_id)
        from_id = to_id - count
        from_id = max(from_id, 1)
        response = self.__oanda_client.request_transactions_once(from_id, to_id)
        filtered_df = prepro.filter_and_make_df(response['transactions'], self.__instrument)
        return filtered_df

    def __calc_requestable_max_days(self, granularity='M5'):
        candles_per_a_day = self.__calc_candles_wanted(days=1, granularity=granularity)

        # http://developer.oanda.com/rest-live-v20/instrument-ep/
        max_days = int(OandaClient.REQUESTABLE_COUNT / candles_per_a_day)
        return max_days

    def __calc_candles_wanted(self, days=1, granularity='M5'):
        time_unit = granularity[0]
        if time_unit == 'D':
            return int(days)

        time_span = int(granularity[1:])
        if time_unit == 'H':
            return int(days * 24 / time_span)

        if time_unit == 'M':
            return int(days * 24 * 60 / time_span)

    def __calc_requestable_time_duration(self, granularity):
        timedelta = converter.granularity_to_timedelta(granularity)
        requestable_duration = timedelta * (OandaClient.REQUESTABLE_COUNT - 1)

        return requestable_duration

    def __union_candles_distinct(self, old_candles, new_candles):
        if old_candles is None:
            return new_candles

        return pd.concat([old_candles, new_candles]) \
                 .drop_duplicates(subset='time') \
                 .sort_values(by='time', ascending=True) \
                 .reset_index(drop=True)
