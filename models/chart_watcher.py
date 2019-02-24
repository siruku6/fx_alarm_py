import os # load access_token
import datetime, math, time
import pandas as pd

# For trading
from   oandapyV20 import API
import oandapyV20.endpoints.instruments as oandapy

class FXBase():
    __candles = None

    @classmethod
    def get_candles(cls):
        return cls.__candles

    @classmethod
    def set_timeID(cls):
        cls.__candles['time_id'] = cls.get_candles().index + 1

    @classmethod
    def union_candles_distinct(cls, candles):
        # pandas_df == None という比較はできない
        # https://stackoverflow.com/questions/36217969/how-to-compare-pandas-dataframe-against-none-in-python
        if cls.__candles is None:
            cls.__candles = candles
        else:
            cls.__candles = pd.concat([cls.get_candles(), candles]) \
                              .drop_duplicates(subset='time') \
                              .reset_index(drop=True)

class ChartWatcher():
    def __init__(self):
        ''' 固定パラメータの設定 '''
        print('initing ...')
        self.__access_token  = os.environ['OANDA_ACCESS_TOKEN']

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

    def __calc_candles_wanted(self, days=1, granularity='M5'):
        # http://developer.oanda.com/rest-live-v20/instrument-ep/
        # 5000本まで許容されることを確認した
        time_unit = granularity[0]
        time_span = int(granularity[1:])
        candles_count = days
        if time_unit == 'D':
            return int(candles_count)

        candles_count = candles_count * 24
        if time_unit == 'H':
            return int(candles_count / time_span)

        candles_count = candles_count * 60
        if time_unit == 'M':
            return int(candles_count / time_span)

    def __reset_time_params(self, days=1, granularity='M5'):
        ''' 時間に関係するparamsをリセット(現在時含む) '''
        now        = datetime.datetime.now() - datetime.timedelta(hours=9) # 標準時に合わせる
        start_time = now - datetime.timedelta(days=days)
        start_time = start_time.strftime('%Y-%m-%dT%H:%M:00.000000Z')
        candles_count = self.__calc_candles_wanted(days=days, granularity=granularity)
        # 表示可能な最大行数を設定
        # pd.set_option("display.max_rows", self.__candles_count)

        return {
            'alignmentTimezone': 'Asia/Tokyo',
            'from':               start_time,
            'count':              candles_count,
            'granularity':        granularity
        }

    def __request_oanda_instruments(self, time_params):
        ''' OandaAPIと直接通信し、為替データを取得 '''
        api = API(
            access_token = self.__access_token,
            environment  = 'practice'
        )
        request_obj = oandapy.InstrumentsCandles(
            instrument = 'USD_JPY',
            params     = time_params
        )
        api.request(request_obj)
        return request_obj

    def __transform_to_candle_chart(self, response):
        ''' APIレスポンスをチャートデータに整形 '''
        candle         = pd.DataFrame.from_dict([ row['mid'] for row in response['candles'] ])
        # astype: 複数列まとめてcast https://qiita.com/driller/items/af1369a5c0fc2ec61af3
        candle         = candle.astype({'c': 'float64', 'l': 'float64', 'h': 'float64', 'o': 'float64'})
        candle.columns = ['close', 'high', 'low', 'open']
        candle['time'] = [ row['time'] for row in response['candles'] ]
        # 冗長な日時データを短縮 https://note.nkmk.me/python-pandas-datetime-timestamp/
        candle['time'] = pd.to_datetime(candle['time']).astype(str) # TODO .astype(str) これでいいのか？
        return candle

    def reload_chart(self, days=1):
        ''' チャート情報を更新 '''
        if self.__is_uptime() == False: return { 'error': '休日のためAPIへのrequestをcancelしました' }
        time_params = self.__reset_time_params(days=days)
        request     = self.__request_oanda_instruments(time_params=time_params)
        if request.response['candles'] == []: return { 'error': 'request結果、データがありませんでした' }

        candles = self.__transform_to_candle_chart(request.response)
        FXBase.union_candles_distinct(candles=candles)
        return { 'success': 'Oandaからのレート取得に成功' }

    def load_long_chart(self):
        ''' 長期間のチャート取得のために複数回APIリクエスト '''
        print('何日分のデータを取得する？(半角数字): ', end='')
        days    = int(input())
        minutes = days * 24 * 60
        # times   = math.ceil(minutes / self.__granularity_minutes / 5000)
        # st_time = minutes
        for i in range(1, times):
            print(i, ': hoge 残り {times}request'.format(times=times-i-1))
            time.sleep(1)

if __name__ == '__main__':
    watcher = ChartWatcher()
    watcher.load_long_chart()
