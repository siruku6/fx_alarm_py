import logging, os
import datetime, time
import pandas as pd
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# For trading
from   oandapyV20 import API
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.instruments as inst
import oandapyV20.endpoints.transactions as transactions
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
    def replace_latest_price(cls, type, new_price):
        column_num = cls.__candles.columns.get_loc(type)
        cls.__candles.iat[-1, column_num] = new_price

    @classmethod
    def write_candles_on_csv(cls, filename='./tmp/candles.csv'):
        cls.__candles.to_csv(filename)


# granularity list
# http://developer.oanda.com/rest-live-v20/instrument-df/#CandlestickGranularity
class OandaPyClient():
    @classmethod
    def select_instrument(cls, inst_id=None):
        # TODO: 正しいspreadを後で確認して設定する
        instruments = [
            { 'name': 'USD_JPY', 'spread': 0.004 },
            { 'name': 'EUR_USD', 'spread': 0.00014 },
            { 'name': 'GBP_JPY', 'spread': 0.014 }
        ]
        if inst_id is not None: return instruments[inst_id]

        print('通貨ペアは？')
        prompt_message = ''
        for i, inst in enumerate(instruments):
            prompt_message += '[{i}]:{inst} '.format(i=i, inst=inst['name'])
        print(prompt_message + '(半角数字): ', end='')
        inst_id = int(input())
        return instruments[inst_id]

    def __init__(self, instrument=None, environment=None):
        ''' 固定パラメータの設定 '''
        self.__api_client = API(
            access_token=os.environ['OANDA_ACCESS_TOKEN'],
            # 'practice' or 'live' is valid
            environment=environment or os.environ.get('OANDA_ENVIRONMENT') or 'practice'
        )
        self.__instrument = instrument or 'USD_JPY'
        self.__units = os.environ.get('UNITS') or '1'
        self.__tradeIDs = []
        self.__lastTransactionID = None

    #
    # Public
    #
    def reload_chart(self, days=1, granularity='M5'):
        ''' チャート情報を更新 '''
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
            FXBase.set_candles(candles)
            return { 'success': '[Watcher] APIリクエスト成功' }
        else:
            return { 'error': '[Watcher] 処理中断' }

    def request_latest_candles(self, target_datetime, granularity='M10', period_of_time='D'):
        end_datetime = datetime.datetime.strptime(target_datetime, '%Y-%m-%d %H:%M:%S')
        time_unit = period_of_time[0]
        if time_unit is 'M':
            start_datetime = end_datetime - datetime.timedelta(minutes=int(period_of_time[1:]))
        elif time_unit is 'H':
            start_datetime = end_datetime - datetime.timedelta(hours=int(period_of_time[1:]))
        elif time_unit is 'D':
            start_datetime = end_datetime - datetime.timedelta(days=1)

        # try:
        response = self.__request_oanda_instruments(
            start=self.__format_dt_into_OandapyV20(start_datetime),
            end=  self.__format_dt_into_OandapyV20(end_datetime),
            granularity=granularity
        )
        # except V20Error as e:
        #     print("V20Error: ", e)
        #     # INFO: 保険として、1分前のデータの再取得を試みる
        #     start_datetime -= datetime.timedelta(minutes=1)
        #     end_datetime   -= datetime.timedelta(minutes=1)
        #     response = self.__request_oanda_instruments(
        #         start=self.__format_dt_into_OandapyV20(start_datetime),
        #         end=  self.__format_dt_into_OandapyV20(end_datetime),
        #         granularity=granularity
        #     )

        candles = self.__transform_to_candle_chart(response)
        return candles

    def request_specified_candles(self, start_datetime, granularity='M10', base_granurarity='D'):
        start_time = datetime.datetime.strptime(start_datetime, '%Y-%m-%d %H:%M:%S')
        time_unit = base_granurarity[0]
        if time_unit is 'M':
            end_time = start_time + datetime.timedelta(minutes=int(base_granurarity[1:]))
        elif time_unit is 'H':
            end_time = start_time + datetime.timedelta(hours=int(base_granurarity[1:]))
        elif time_unit is 'D':
            end_time = start_time + datetime.timedelta(days=1)
        if end_time > datetime.datetime.now(): end_time = datetime.datetime.now()

        response = self.__request_oanda_instruments(
            start=self.__format_dt_into_OandapyV20(start_time),
            end=  self.__format_dt_into_OandapyV20(end_time),
            granularity=granularity
        )
        candles = self.__transform_to_candle_chart(response)
        return candles

    def request_specified_period_candles(self, start_str, end_str, granularity):
        start_time = datetime.datetime.strptime(start_str, '%Y-%m-%d %H:%M:%S')
        end_time = datetime.datetime.strptime(end_str, '%Y-%m-%d %H:%M:%S')

        response = self.__request_oanda_instruments(
            start=self.__format_dt_into_OandapyV20(start_time),
            end=  self.__format_dt_into_OandapyV20(end_time),
            granularity=granularity
        )
        candles = self.__transform_to_candle_chart(response)
        return candles

    def request_is_tradeable(self):
        params = { 'instruments': self.__instrument } # 'USD_JPY,EUR_USD,EUR_JPY'
        request_obj = pricing.PricingInfo(
            accountID=os.environ['OANDA_ACCOUNT_ID'], params=params
        )
        response = self.__api_client.request(request_obj)
        tradeable = response['prices'][0]['tradeable']
        return {
            'instrument': self.__instrument,
            'tradeable': tradeable
        }

    def request_current_price(self):
        '''
        最新の値がgranurarity毎のpriceの上下限を抜いていたら、抜けた値で上書き
        '''
        now = datetime.datetime.now() - datetime.timedelta(hours=9)
        latest_candle = self.request_latest_candles(
            target_datetime=str(now)[:19],
            granularity='M1',
            period_of_time='M1',
        ).iloc[-1]

        candles = FXBase.get_candles()
        if candles.iloc[-1].high < latest_candle.high:
            FXBase.replace_latest_price('high', latest_candle.high)
        elif candles.iloc[-1].low > latest_candle.low:
            FXBase.replace_latest_price('low', latest_candle.low)
        print('[Client] 直前値')
        print(FXBase.get_candles().iloc[-1])
        print('[Client] 現在値')
        print(latest_candle)

    def request_open_trades(self):
        ''' OANDA上でopenなポジションの情報を取得 '''
        request_obj = trades.OpenTrades(accountID=os.environ['OANDA_ACCOUNT_ID'])
        response = self.__api_client.request(request_obj)
        self.__lastTransactionID = response['lastTransactionID']
        open_trades = response['trades']

        extracted_trades = [trade for trade in open_trades if
            # 'clientExtensions' not in trade.keys() and
            trade['instrument'] == self.__instrument
        ]
        print('[Client] open_trades: {}'.format(extracted_trades))
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
        response = self.__api_client.request(request_obj)
        logger.info('[Client] market-order: {}'.format(response))
        return response

    def request_closing_position(self):
        ''' ポジションをclose '''
        if self.__tradeIDs == []: return { 'error': '[Client] closeすべきポジションが見つかりませんでした。' }

        target_tradeID = self.__tradeIDs[0]
        # data = { 'units': self.__units }
        request_obj = trades.TradeClose(
            accountID=os.environ['OANDA_ACCOUNT_ID'], tradeID=target_tradeID # , data=data
        )
        response = self.__api_client.request(request_obj)
        logger.info('[Client] close-position: {}'.format(response))
        return response

    def request_trailing_stoploss(self, SL_price=None):
        ''' ポジションのstoplossを強気方向に修正 '''
        if self.__tradeIDs == []: return { 'error': '[Client] trailすべきポジションが見つかりませんでした。' }
        if SL_price is None: return { 'error': '[Client] StopLoss価格がなく、trailできませんでした。' }

        data = {
            # 'takeProfit': { 'timeInForce': 'GTC', 'price': '1.3'  },
            'stopLoss': { 'timeInForce': 'GTC', 'price': str(SL_price)[:7] }
        }
        request_obj = trades.TradeCRCDO(
            accountID=os.environ['OANDA_ACCOUNT_ID'],
            tradeID=self.__tradeIDs[0],
            data=data
        )
        response = self.__api_client.request(request_obj)
        logger.info('[Client] trail: {}'.format(response))
        return response

    def request_transactions(self):
        params = {
            # len(from ... to) <= 1000
            'to': int(self.__lastTransactionID),
            'from': int(self.__lastTransactionID) - 999,
            'type': ['ORDER'],
            # 消えるtype => TRADE_CLIENT_EXTENSIONS_MODIFY, DAILY_FINANCING
        }
        requset_obj = transactions.TransactionIDRange(
            accountID=os.environ['OANDA_ACCOUNT_ID'],
            params=params
        )
        response = self.__api_client.request(requset_obj)
        filtered_df = self.__filter_and_make_df(response['transactions'])
        return filtered_df

    #
    # Private
    #

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
        # HACK: 現在値を取得する際、誤差で将来の時間と扱われてエラーになることがある
        try:
            response = self.__api_client.request(request_obj)
        except V20Error as e:
            logger.error('[__request_oanda_instruments] V20Error: ', e)
            return { 'candles': [] }

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

    def __filter_and_make_df(self, response_transactions):
        ''' 必要なrecordのみ残してdataframeに変換する '''
        filtered_transactions = [
            row for row in response_transactions if (
                row['type']!='ORDER_CANCEL' and
                row['type']!='MARKET_ORDER' # and
                # row['type']!='MARKET_ORDER_REJECT'
            )
        ]

        df = pd.DataFrame.from_dict(filtered_transactions).fillna({ 'pl': 0 })
        df = df[[
            'batchID',
            'id',
            'tradeOpened',
            'tradesClosed',
            'type',
            'price',
            'units',
            'pl',
            'time',
            'reason',
            'instrument'
        ]]
        df['pl']   = df['pl'].astype({'pl': 'float'}).astype({'pl': 'int'})
        df['time'] = [row['time'][:19] for row in filtered_transactions]
        return df
