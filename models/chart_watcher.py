import os # load access_token
import datetime
import pandas as pd

# For trading
from   oandapyV20 import API
import oandapyV20.endpoints.instruments as oandapy

class FXBase():
    __candles = None

    # クラスメソッドのルール
    # https://www.st-hakky-blog.com/entry/2017/11/15/155523
    @classmethod
    def get_candles(cls):
        return cls.__candles

    @classmethod
    def set_timeID(cls):
        cls.__candles['time_id'] = cls.get_candles().index + 1

    @classmethod
    def union_candles_distinct(cls, candle):
        # pandas_df == None という比較はできない
        # https://stackoverflow.com/questions/36217969/how-to-compare-pandas-dataframe-against-none-in-python
        if cls.__candles is None:
            cls.__candles = candle
        else:
            cls.__candles = pd.concat([cls.get_candles(), candle]) \
                            .drop_duplicates(subset='time') \
                            .reset_index(drop=True)

class ChartWatcher():
    def __init__(self, days=1):
        ''' 固定パラメータの設定 '''
        print('initing ...')
        self.__a_step_time  = 5
        self.__num_candles  = int(days * 24 * 60 / self.__a_step_time) # 24h * 60min / 5分刻み
        self.__minutes      = self.__num_candles * self.__a_step_time  # 60 = 12 * 5 分
        self.__access_token = os.environ['OANDA_ACCESS_TOKEN']
        # 表示可能な最大行数を設定
        pd.set_option("display.max_rows", self.__num_candles)

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

    def __reset_params(self):
        ''' チャート取得の起点(from)を変更してparamsを返す '''
        now        = datetime.datetime.now() - datetime.timedelta(hours=9) # 標準時に合わせる
        start_time = now - datetime.timedelta(minutes=self.__minutes - self.__a_step_time)
        start_time = start_time.strftime("%Y-%m-%dT%H:%M:00.000000Z")

        params = {
            "alignmentTimezone": "Japan",
            "from":  start_time,
            "count": self.__num_candles,
            "granularity": "M5" # per 5 Minute
        }
        return params

    def __request_oanda_instruments(self):
        ''' OandaAPIと直接通信し、為替データを取得 '''
        api = API(
            access_token = self.__access_token,
            environment  = "practice"
        )
        request_obj = oandapy.InstrumentsCandles(
            instrument = "USD_JPY",
            params     = self.__reset_params()
        )
        api.request(request_obj)
        return request_obj

    def reload_chart(self):
        ''' チャートを更新 '''
        if self.__is_uptime() == False: return { 'error': '休日のためAPIへのrequestをcancelしました' }
        request = self.__request_oanda_instruments()
        if request.response['candles'] == []: return { 'error': 'request結果、データがありませんでした' }

        # 為替データの整形
        candle         = pd.DataFrame.from_dict([ row['mid'] for row in request.response['candles'] ])
        # astype: 複数列まとめてcast https://qiita.com/driller/items/af1369a5c0fc2ec61af3
        candle         = candle.astype({'c': 'float64', 'l': 'float64', 'h': 'float64', 'o': 'float64'})
        candle.columns = ['close', 'high', 'low', 'open']
        candle['time'] = [ row['time'] for row in request.response['candles'] ]
        # 冗長な日時データを短縮 https://note.nkmk.me/python-pandas-datetime-timestamp/
        candle['time'] = pd.to_datetime(candle['time']).astype(str) # TODO .astype(str) これでいいのか？

        FXBase.union_candles_distinct(candle=candle)
        return { 'success': 'Oandaからのレート取得に成功' }

if __name__ == '__main__':
    watcher = ChartWatcher()
    result  = watcher.reload_chart()
    if 'success' in result:
        print(result['success'])
        FXBase.set_timeID()
        print(FXBase.get_candles().head())
    else:
        print(result['error'])
        exit()
