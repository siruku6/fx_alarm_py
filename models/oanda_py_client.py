import os
import datetime, time
import pandas as pd

# For trading
from   oandapyV20 import API
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.instruments as inst
from   oandapyV20.exceptions import V20Error

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

# granularity list
# http://developer.oanda.com/rest-live-v20/instrument-df/#CandlestickGranularity
class OandaPyClient():
    def __init__(self, instrument=None, environment='practice'):
        ''' 固定パラメータの設定 '''
        print('initing ...')
        self.__api_client = API(
            access_token=os.environ['OANDA_ACCESS_TOKEN'],
            environment=environment # or 'live' is valid
        )
        self.__instrument = instrument or 'USD_JPY'
        self.__units = os.environ.get('UNITS') or '1'
        self.__tradeIDs = []

    #
    # Public
    #
    def reload_chart(self, days=1, granularity='M5'):
        ''' チャート情報を更新 '''
        # if self.__is_uptime() == False:
        #     return { 'error': '[Watcher] 休日のためAPIへのrequestをcancelしました' }
        start_time    = self.__calc_start_time(days=days)
        candles_count = self.__calc_candles_wanted(days=days, granularity=granularity)
        # pd.set_option('display.max_rows', candles_count) # 表示可能な最大行数を設定
        response = self.__request_oanda_instruments(
            start=start_time,
            candles_count=candles_count,
            granularity=granularity
        )
        if response['candles'] == []:
            return { 'error': '[Watcher] request結果、データがありませんでした' }
        else:
            candles = self.__transform_to_candle_chart(response)
            FXBase.set_candles(
                candles=FXBase.union_candles_distinct(FXBase.get_candles(), candles)
            )
            return { 'success': '[Watcher] Oandaからのレート取得に成功' }

    def load_long_chart(self, days=1, granularity='M5'):
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

            response = self.__request_oanda_instruments(
                start=self.__format_dt_into_OandapyV20(start_datetime),
                end=self.__format_dt_into_OandapyV20(end_datetime),
                granularity=granularity
            )
            tmp_candles = self.__transform_to_candle_chart(response)
            candles = FXBase.union_candles_distinct(candles, tmp_candles)
            print('残り: {remaining_days}日分'.format(remaining_days=remaining_days))
            time.sleep(1)

        if remaining_days is 0:
            return { 'success': '[Watcher] APIリクエスト成功',
                     'candles': candles }
        else:
            return { 'error': '[Watcher] 処理中断' }

    def request_latest_candles(self, target_datetime, granularity='M10', base_granurarity='D'):
        end_datetime = datetime.datetime.strptime(target_datetime, '%Y-%m-%d %H:%M:%S')
        time_unit = base_granurarity[0]
        if time_unit is 'M':
            start_datetime = end_datetime - datetime.timedelta(minutes=int(base_granurarity[1:]))
        elif time_unit is 'H':
            start_datetime = end_datetime - datetime.timedelta(hours=int(base_granurarity[1:]))
        elif time_unit is 'D':
            start_datetime = end_datetime - datetime.timedelta(days=1)

        try:
            response = self.__request_oanda_instruments(
                start=self.__format_dt_into_OandapyV20(start_datetime),
                end=  self.__format_dt_into_OandapyV20(end_datetime),
                granularity=granularity
            )
        # HACK: 現在値を取得する際、誤差で将の来時間と扱われてエラーになることがある
        except V20Error as e:
            print(e['errorMessage'])
            # INFO: 保険として、1分前のデータの再取得を試みる
            start_datetime -= datetime.timedelta(minutes=1)
            end_datetime   -= datetime.timedelta(minutes=1)
            response = self.__request_oanda_instruments(
                start=self.__format_dt_into_OandapyV20(start_datetime),
                end=  self.__format_dt_into_OandapyV20(end_datetime),
                granularity=granularity
            )

        candles = self.__transform_to_candle_chart(response)
        return candles

    def request_is_tradable(self):
        params = { 'instruments': self.__instrument } # 'USD_JPY,EUR_USD,EUR_JPY'
        request_obj = pricing.PricingInfo(
            accountID=os.environ['OANDA_ACCOUNT_ID'], params=params
        )
        response = self.__api_client.request(request_obj)
        return {
            'instrument': self.__instrument,
            'tradeable': response['prices'][0]['tradeable']
        }

    def request_current_price(self):
        now = datetime.datetime.now() - datetime.timedelta(hours=9)
        result = self.request_latest_candles(
            target_datetime=str(now)[:19],
            granularity='M1',
            base_granurarity='M1',
        )
        return result

    def request_open_trades(self):
        ''' OANDA上でopenなポジションの情報を取得 '''
        request_obj = trades.OpenTrades(accountID=os.environ['OANDA_ACCOUNT_ID'])
        self.__api_client.request(request_obj)
        open_trades = request_obj.response['trades']

        extracted_trades = [trade for trade in open_trades if
            'clientExtensions' not in trade.keys() and
            trade['instrument'] == self.__instrument
        ]
        self.__tradeIDs = [trade['id'] for trade in extracted_trades]
        return extracted_trades

    def request_market_ordering(self, posi_nega_sign='', stoploss_price=None):
        ''' 成行注文を実施 '''
        if stoploss_price is None: return { 'error': '[Client] StopLoss注文なしでの成り行き注文を禁止します。' }

        data = {
          'order': {
            'stopLossOnFill': {
              'timeInForce': 'GTC',
              'price': str(stoploss_price)[:7] # TODO: 桁数が少ない通貨ペアも考慮する
            },
            'instrument': self.__instrument,
            'units': '{sign}{units}'.format(sign=posi_nega_sign, units=self.__units),
            'type': 'MARKET',
            'positionFill': 'DEFAULT'
          }
        }

        request_obj = orders.OrderCreate(
            accountID=os.environ['OANDA_ACCOUNT_ID'], data=data
        )
        self.__api_client.request(request_obj)
        return request_obj.response

    def request_closing_position(self):
        ''' ポジションをclose '''
        if self.__tradeIDs == []: return { 'error': '[Client] closeすべきポジションが見つかりませんでした。' }

        target_tradeID = self.__tradeIDs[0]
        # data = { 'units': self.__units }
        request_obj = trades.TradeClose(
            accountID=os.environ['OANDA_ACCOUNT_ID'], tradeID=target_tradeID # , data=data
        )
        self.__api_client.request(request_obj)
        return request_obj.response

    def request_trailing_stoploss(self, stoploss_price=None):
        ''' ポジションのstoplossを強気方向に修正 '''
        if self.__tradeIDs == []: return { 'error': '[Client] trailすべきポジションが見つかりませんでした。' }
        if stoploss_price is None: return { 'error': '[Client] StopLoss価格がなく、trailできませんでした。' }

        data = {
            'stopLoss': { 'timeInForce': 'GTC', 'price': str(stoploss_price) }
        }
        request_obj = trades.TradeCRCDO(
            accountID=os.environ['OANDA_ACCOUNT_ID'],
            tradeID=self.__tradeIDs[0],
            data=data
        )
        self.__api_client.request(request_obj)
        return request_obj.response

    def request_trades_history(self):
        ''' OANDAのトレード履歴を取得 '''
        params ={
            'instrument': self.__instrument,
            'state': 'ALL' # 全過去分を取得
        }
        request_obj = trades.TradesList(accountID=os.environ['OANDA_ACCOUNT_ID'], params=params)
        self.__api_client.request(request_obj)

        past_trades = [
            trade for trade in request_obj.response['trades'] if
                'clientExtensions' not in trade.keys() and
                trade['state'] != 'OPEN'
        ]
        return self.__pack_pastTrades_in_df(past_trades=past_trades)

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
        candles_count=None, granularity='M5'):
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
            instrument=self.__instrument,
            params=time_params
        )
        response = self.__api_client.request(request_obj)
        return response

    def __transform_to_candle_chart(self, response):
        ''' APIレスポンスをチャートデータに整形 '''
        if response['candles'] == []: return pd.DataFrame(columns=[])

        candle = pd.DataFrame.from_dict([ row['mid'] for row in response['candles'] ])
        candle = candle.astype({
            'c': 'float64',
            'l': 'float64',
            'h': 'float64',
            'o': 'float64'
        })
        candle.columns = ['close', 'high', 'low', 'open']
        candle['time'] = [ row['time'] for row in response['candles'] ]
        # 冗長な日時データを短縮
        # https://note.nkmk.me/python-pandas-datetime-timestamp/
        candle['time'] = pd.to_datetime(candle['time']).astype(str) # '2018-06-03 21:00:00'
        return candle

    def __calc_requestable_max_days(self, granularity='M5'):
        candles_per_a_day = self.__calc_candles_wanted(days=1, granularity=granularity)

        # http://developer.oanda.com/rest-live-v20/instrument-ep/
        max_days = int(5000 / candles_per_a_day) # 1 requestにつき5000本まで
        return max_days

    def __format_dt_into_OandapyV20(self, dt):
        return dt.strftime('%Y-%m-%dT%H:%M:00.000000Z')

    def __pack_pastTrades_in_df(self, past_trades=None):
        gain_df = pd.DataFrame(columns=[
            'openTime', 'closeTime', 'position_type',
            'open', 'close', 'units',
            'gain', 'realizedPL'
        ])

        for trade in past_trades:
            # INFO: preparing　values
            if trade['initialUnits'][0] == '-':
                minus = -1
                position_type = 'short'
            else:
                minus = 1
                position_type = 'long'
            open_price = float(trade['price'])
            close_price = float(trade['averageClosePrice'])

            # INFO: set values in dataframe
            tmp_series = pd.Series([
                trade['openTime'][0:16], trade['closeTime'][0:16], position_type,
                open_price, close_price, trade['initialUnits'],
                round(close_price - open_price, 5) * minus, trade['realizedPL']
            ],index=gain_df.columns)
            gain_df = gain_df.append( tmp_series, ignore_index=True )

        return gain_df
