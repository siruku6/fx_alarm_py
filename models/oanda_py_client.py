import os
import datetime, time
import pandas as pd

# For trading
from   oandapyV20 import API
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.instruments as inst

class FXBase():
    __candles = None
    __latest_candle = None

    @classmethod
    def get_candles(cls):
        return cls.__candles

    @classmethod
    def set_timeID(cls):
        cls.__candles['time_id'] = cls.get_candles().index + 1

    @classmethod
    def union_candles_distinct(cls, old_candles, new_candles):
        # pandas_df == None という比較はできない
        if old_candles is None:
            return new_candles
        else:
            return pd.concat([old_candles, new_candles]) \
                     .drop_duplicates(subset='time') \
                     .reset_index(drop=True)

    @classmethod
    def set_candles(cls, candles):
        cls.__candles = candles

    @classmethod
    def write_candles_on_csv(cls, filename='./candles.csv'):
        cls.__candles.to_csv(filename)

    # @classmethod
    # def get_latest_candle(cls):
    #     return cls.__latest_candle
    #
    # @classmethod
    # def set_latest_candle(cls, df_candle):
    #     cls.__latest_candle = df_candle

# granularity list
# http://developer.oanda.com/rest-live-v20/instrument-df/#CandlestickGranularity
class OandaPyClient():
    def __init__(self, instrument='USD_JPY'):
        ''' 固定パラメータの設定 '''
        print('initing ...')
        self.__api = API(
            access_token=os.environ['OANDA_ACCESS_TOKEN'],
            environment ='practice'
        )
        self.__instrument = instrument

    #
    # Public
    #
    def reload_chart(self, days=1, granularity='M5', instrument=None):
        ''' チャート情報を更新 '''
        # if self.__is_uptime() == False: return { 'error': '[Watcher] 休日のためAPIへのrequestをcancelしました' }
        start_time    = self.__calc_start_time(days=days)
        candles_count = self.__calc_candles_wanted(days=days, granularity=granularity)
        # pd.set_option("display.max_rows", candles_count) # 表示可能な最大行数を設定
        request = self.__request_oanda_instruments(
            start=start_time,
            candles_count=candles_count,
            instrument=instrument or self.__instrument,
            granularity=granularity
        )
        if request.response['candles'] == []:
            return { 'error': '[Watcher] request結果、データがありませんでした' }
        else:
            candles = self.__transform_to_candle_chart(request.response)
            FXBase.set_candles(
                candles=FXBase.union_candles_distinct(FXBase.get_candles(), candles)
            )
            return { 'success': '[Watcher] Oandaからのレート取得に成功' }

    def load_long_chart(self, days=1, granularity='M5', instrument=None):
        ''' 長期間のチャート取得のために複数回APIリクエスト '''
        remaining_days = days
        candles = None
        requestable_max_days = self.__calc_requestable_max_days(granularity=granularity)

        now  = datetime.datetime.now() - datetime.timedelta(hours=9) # UTC化
        while remaining_days > 0:
            start_datetime = now - datetime.timedelta(days=remaining_days)
            remaining_days -= requestable_max_days
            if remaining_days < 0: remaining_days = 0
            end_datetime = now - datetime.timedelta(days=remaining_days)
            request = self.__request_oanda_instruments(
                start=self.__format_dt_into_OandapyV20(start_datetime),
                end=self.__format_dt_into_OandapyV20(end_datetime),
                instrument=instrument or self.__instrument, granularity=granularity
            )
            tmp_candles = self.__transform_to_candle_chart(request.response)
            candles = FXBase.union_candles_distinct(candles, tmp_candles)
            print('残り: {remaining_days}日分'.format(remaining_days=remaining_days))
            time.sleep(1)

        if remaining_days is 0:
            return { 'success': '[Watcher] APIリクエスト成功',
                     'candles': candles }
        else:
            return { 'error': '[Watcher] 処理中断' }

    def request_latest_candles(self, target_datetime,
        granularity='M10', instrument=None, period_m=1440
    ):
        start_datetime = datetime.datetime.strptime(target_datetime, '%Y-%m-%d %H:%M:%S')
        end_datetime   = start_datetime + datetime.timedelta(minutes=period_m)
        request = self.__request_oanda_instruments(
            start=self.__format_dt_into_OandapyV20(start_datetime),
            end=  self.__format_dt_into_OandapyV20(end_datetime),
            instrument=instrument or self.__instrument,
            granularity=granularity
        )
        candles = self.__transform_to_candle_chart(request.response)
        return candles

    def request_open_trades(self, instrument=None):
        ''' OANDA上でopenなポジションの情報を取得 '''
        request_obj = trades.OpenTrades(accountID=os.environ['OANDA_ACCOUNT_ID'])
        self.__api.request(request_obj)
        all_trades = request_obj.response['trades']

        extracted_trades = [trade for trade in all_trades if
            'clientExtensions' not in trade.keys() and
            trade['instrument'] == instrument or self.__instrument
        ]
        return extracted_trades

    def request_trades_history(self):
        ''' OANDAのトレード履歴を取得 '''
        params ={
            'instrument': self.__instrument,
            'state': 'ALL' # 全過去分を取得
        }
        request_obj = trades.TradesList(accountID=os.environ['OANDA_ACCOUNT_ID'], params=params)
        self.__api.request(request_obj)

        past_trades = [
            trade for trade in request_obj.response['trades'] if
                'clientExtensions' not in trade.keys() and
                trade['state'] != 'OPEN'
        ]
        return past_trades

    #
    # Private
    #
    def __is_uptime(self):
        ''' 市場が動いている（営業中）か否か(bool型)を返す '''
        now_delta       = datetime.datetime.now()
        six_hours_delta = datetime.timedelta(hours=6) # 大体このくらいずらすと、ちょうど動いてる（気がする）
        weekday_num     = (now_delta - six_hours_delta).weekday()

        # weekday_num
        # 0:Mon, 1:Tue, 2:Wed, 3:Thu, 4:Fri, 5:Sat, 6:Sun
        if weekday_num < 5: # 平日なら
            return True
        else:
            return False

    # TODO: このメソッドいらないかも
    def __calc_start_time(self, days, end_datetime=datetime.datetime.now()):
        end_datetime -= datetime.timedelta(hours=9) # UTC化
        start_time    = end_datetime - datetime.timedelta(days=days)
        start_time    = self.__format_dt_into_OandapyV20(start_time)
        return start_time

    def __calc_candles_wanted(self, days=1, granularity='M5'):
        time_unit = granularity[0]
        if time_unit == 'D':
            return int(days)

        time_span = int(granularity[1:])
        if time_unit == 'H':
            return int(days * 24 / time_span)
        if time_unit == 'M':
            return int(days * 24 * 60 / time_span)

    def __request_oanda_instruments(self, start, end=None,
        candles_count=None, instrument=None, granularity='M5'):
        ''' OandaAPIと直接通信し、為替データを取得 '''
        if candles_count is not None:
            time_params = {
                # INFO: つけない方が一般的なレートに近くなる
                # 'alignmentTimezone':   'Asia/Tokyo',
                'from': start, 'count': candles_count,
                'granularity': granularity
            }
        else:
            time_params = {
                # 'alignmentTimezone': 'Asia/Tokyo',
                'from': start, 'to':  end,
                'granularity': granularity
            }

        request_obj = inst.InstrumentsCandles(
            instrument=instrument or self.__instrument,
            params=time_params
        )
        self.__api.request(request_obj)
        return request_obj

    def __transform_to_candle_chart(self, response):
        ''' APIレスポンスをチャートデータに整形 '''
        candle         = pd.DataFrame.from_dict([ row['mid'] for row in response['candles'] ])
        candle         = candle.astype({'c': 'float64', 'l': 'float64', 'h': 'float64', 'o': 'float64'})
        candle.columns = ['close', 'high', 'low', 'open']
        candle['time'] = [ row['time'] for row in response['candles'] ]
        # 冗長な日時データを短縮
        # https://note.nkmk.me/python-pandas-datetime-timestamp/
        candle['time'] = pd.to_datetime(candle['time']).astype(str) # '2018-06-03 21:00:00'
        return candle

    def __calc_requestable_max_days(self, granularity='M5'):
        time_unit = granularity[0]

        # 1日当たりのローソク足本数を計算
        if time_unit == 'D':
            candles_per_a_day = 1
        elif time_unit == 'H':
            time_span = int(granularity[1:])
            candles_per_a_day = 1 * 24 / time_span
        elif time_unit == 'M':
            time_span = int(granularity[1:])
            candles_per_a_day = 1 * 24 * 60 / time_span

        # http://developer.oanda.com/rest-live-v20/instrument-ep/
        # 1 requestにつき5000本まで許容される
        max_days = int(5000 / candles_per_a_day)
        return max_days

    def __format_dt_into_OandapyV20(self, dt):
        return dt.strftime('%Y-%m-%dT%H:%M:00.000000Z')

if __name__ == '__main__':
    print('何日分のデータを取得する？(半角数字): ', end='')
    days = int(input())
    if days > 300:
        print('[ALERT] 現在は300日までに制限しています')
        exit()
    print('取得スパンは？(ex: M5): ', end='')
    granularity = str(input())

    watcher = OandaPyClient()
    result = watcher.load_long_chart(days=days, granularity=granularity)
    if 'error' in result:
        print(result['error'])
        exit()
    FXBase.set_candles(FXBase.union_candles_distinct(candles=result['candles']))
    FXBase.write_candles_on_csv()
