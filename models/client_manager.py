import datetime
import time
from collections import OrderedDict

from models.oanda_py_client import OandaPyClient
import models.tools.format_converter as converter
import models.tools.preprocessor as prepro
from models.mongodb_accessor import MongodbAccessor
from models.tools.interface import select_from_dict

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

        instrument = select_from_dict(instruments, menumsg='通貨ペアは？\n')
        return instrument, instruments[instrument]

    def __init__(self, instrument):
        self.__instrument = instrument
        self.__oanda_client = OandaPyClient(instrument=self.__instrument)

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

    def load_or_query_candles(self, start_time, end_time, granularity):
        ''' (10分足用) 取得済みであれば mongodb から candles を取得してくれる '''
        candles_accessor = MongodbAccessor(db_name='candles')
        stocked_first_time, stocked_last_time = candles_accessor.edge_datetimes_of(currency_pare=self.__instrument)

        print('[MongoDB] slide用10分足の不足分を解析・request中....')
        if start_time < stocked_first_time:
            candles_supplement = self.load_candles_by_duration(
                start=start_time, end=stocked_first_time - datetime.timedelta(minutes=10),
                granularity=granularity
            )['candles'].rename(columns={'time': '_id'})
            candles_supplement['_id'] = pd.to_datetime(candles_supplement._id)
            candles_dict = candles_supplement.to_dict('records')
            candles_accessor.bulk_insert(currency_pare=self.__instrument, dict_array=candles_dict)

        if stocked_last_time < end_time:
            candles_supplement = self.load_candles_by_duration(
                start=stocked_last_time + datetime.timedelta(minutes=10), end=end_time,
                granularity=granularity
            )['candles'].rename(columns={'time': '_id'})
            candles_supplement['_id'] = pd.to_datetime(candles_supplement._id)
            candles_dict = candles_supplement.to_dict('records')
            candles_accessor.bulk_insert(currency_pare=self.__instrument, dict_array=candles_dict)

        print('[MongoDB] querying m10_candles ...')
        stocked_candles = candles_accessor.query_candles(
            currency_pare=self.__instrument,
            start_dt=start_time, end_dt=end_time
        )
        del candles_accessor
        print('[MongoDB] m10_candles are loaded !')

        return stocked_candles

    def load_candles_by_duration(self, start, end, granularity='M5'):
        ''' 広範囲期間チャート取得用の複数回リクエスト '''
        candles = None
        requestable_duration = self.__calc_requestable_time_duration(granularity)
        next_starttime = start
        # INFO: start から end まで1回のリクエストで取得できる場合は、取れるだけたくさん取得してしまう
        next_endtime = start + requestable_duration

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

    def prepare_one_page_transactions(self):
        # INFO: lastTransactionIDを取得するために実行
        self.__oanda_client.request_open_trades()

        # preapre history_df: trade-history
        history_df = self.__request_latest_transactions()
        history_df.to_csv('./tmp/csvs/hist_positions.csv', index=False)
        return history_df

    def request_massive_transactions(self, from_datetime):
        gained_transactions = []
        from_id, to_id = self.__oanda_client.request_transaction_ids(from_str=from_datetime)

        while True:
            print('[INFO] requesting {}..{}'.format(from_id, to_id))

            response = self.__oanda_client.request_transactions_once(from_id, to_id)
            tmp_transactons = response['transactions']
            gained_transactions += tmp_transactons
            # INFO: ループの終了条件
            #   'to' に指定した ID の transaction がない時が多々あり、
            #   その場合、transactions を取得できないので、ごくわずかな数になる。
            #   そこまで来たら処理終了
            if len(tmp_transactons) <= 10 or tmp_transactons[-1]['id'] == to_id:
                break

            print('[INFO] last_transaction_id {}'.format(tmp_transactons[-1]['id']))
            gained_last_transaction_id = tmp_transactons[-1]['id']
            from_id = str(int(gained_last_transaction_id) + 1)

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
        max_days = int(OandaPyClient.REQUESTABLE_COUNT / candles_per_a_day)
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
        requestable_duration = timedelta * (OandaPyClient.REQUESTABLE_COUNT - 1)

        return requestable_duration

    def __union_candles_distinct(self, old_candles, new_candles):
        if old_candles is None:
            return new_candles

        return pd.concat([old_candles, new_candles]) \
                 .drop_duplicates(subset='time') \
                 .reset_index(drop=True)
