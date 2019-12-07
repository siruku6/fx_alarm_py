import datetime
import time
import logging
import os
import pandas as pd
import pprint

# For trading
from oandapyV20 import API
from oandapyV20.exceptions import V20Error
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.instruments as module_inst
import oandapyV20.endpoints.transactions as transactions

from models.interface import prompt_inputting_decimal
# from models.candles_csv_accessor import CandlesCsvAccessor
from models.mongodb_accessor import MongodbAccessor

logger = logging.getLogger()
logger.setLevel(logging.INFO)
# pd.set_option('display.max_rows', candles_count)  # 表示可能な最大行数を設定


class FXBase():
    __candles = None
    __latest_candle = None

    @classmethod
    def get_candles(cls, start=0, end=None):
        if cls.__candles is None:
            return pd.DataFrame(columns=[])
        return cls.__candles[start:end]

    @classmethod
    def set_time_id(cls):
        cls.__candles['time_id'] = cls.get_candles().index + 1

    @classmethod
    def union_candles_distinct(cls, old_candles, new_candles):
        if old_candles is None:
            return new_candles

        return pd.concat([old_candles, new_candles]) \
                 .drop_duplicates(subset='time') \
                 .reset_index(drop=True)

    @classmethod
    def set_candles(cls, candles):
        cls.__candles = candles

    @classmethod
    def replace_latest_price(cls, price_type, new_price):
        column_num = cls.__candles.columns.get_loc(price_type)
        cls.__candles.iat[-1, column_num] = new_price

    @classmethod
    def write_candles_on_csv(cls, filename='./tmp/candles.csv'):
        cls.__candles.to_csv(filename)


# granularity list
# http://developer.oanda.com/rest-live-v20/instrument-df/#CandlestickGranularity
class OandaPyClient():
    REQUESTABLE_COUNT = 5000

    @classmethod
    def select_instrument(cls, inst_id=None):
        # TODO: 正しいspreadを後で確認して設定する
        instruments = [
            {'name': 'USD_JPY', 'spread': 0.004},
            {'name': 'EUR_USD', 'spread': 0.00014},
            {'name': 'GBP_JPY', 'spread': 0.014},
            {'name': 'USD_CHF', 'spread': 0.00014}
        ]
        if inst_id is not None:
            return instruments[inst_id]

        while True:
            print('通貨ペアは？')
            prompt_message = ''
            for i, inst in enumerate(instruments):
                prompt_message += '[{i}]:{inst} '.format(i=i, inst=inst['name'])
            print(prompt_message + '(半角数字): ', end='')

            inst_id = prompt_inputting_decimal()
            if inst_id < len(instruments):
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
        self.__trade_ids = []
        self.__last_transaction_id = None

    #
    # Public
    #

    # INFO: request-candles
    def specify_count_and_load_candles(self, count=60, granularity='M5', set_candles=False):
        ''' チャート情報を更新 '''
        response = self.__request_oanda_instruments(
            candles_count=count,
            granularity=granularity
        )

        candles = self.__transform_to_candle_chart(response)
        if set_candles:
            FXBase.set_candles(
                candles=FXBase.union_candles_distinct(FXBase.get_candles(), candles)
            )
        return {'success': '[Watcher] Oandaからのレート取得に成功', 'candles': candles}

    def load_long_chart(self, days=0, granularity='M5'):
        ''' 長期間のチャート取得のために複数回APIリクエスト '''
        remaining_days = days
        candles = None
        requestable_max_days = self.__calc_requestable_max_days(granularity=granularity)

        last_datetime = datetime.datetime.now() - datetime.timedelta(hours=9)
        while remaining_days > 0:
            start_datetime = last_datetime - datetime.timedelta(days=remaining_days)
            remaining_days -= requestable_max_days
            if remaining_days < 0: remaining_days = 0
            end_datetime = last_datetime - datetime.timedelta(days=remaining_days)

            response = self.__request_oanda_instruments(
                start=self.__convert_datetime_into_oanda_format(start_datetime),
                end=self.__convert_datetime_into_oanda_format(end_datetime),
                granularity=granularity
            )
            tmp_candles = self.__transform_to_candle_chart(response)
            candles = FXBase.union_candles_distinct(candles, tmp_candles)
            print('残り: {remaining_days}日分'.format(remaining_days=remaining_days))
            time.sleep(1)

        return {'success': '[Watcher] APIリクエスト成功', 'candles': candles}

    def load_or_query_candles(self, start_time, end_time, granularity):
        # candles_accessor = CandlesCsvAccessor(granularity=granularity, currency_pare=self.__instrument)
        candles_accessor = MongodbAccessor(db_name='candles')
        stocked_first_time, stocked_last_time = candles_accessor.edge_datetimes_of(currency_pare=self.__instrument)

        if start_time < stocked_first_time:
            candles_supplement = self.load_candles_by_duration(
                start=start_time, end=stocked_first_time,
                granularity=granularity
            )['candles'].rename(columns={'time': '_id'})
            candles_supplement['_id'] = pd.to_datetime(candles_supplement._id)
            candles_dict = candles_supplement.to_dict('records')
            candles_accessor.bulk_insert(currency_pare=self.__instrument, dict_array=candles_dict)

        if stocked_last_time < end_time:
            candles_supplement = self.load_candles_by_duration(
                start=stocked_last_time, end=end_time,
                granularity=granularity
            )['candles'].rename(columns={'time': '_id'})
            candles_supplement['_id'] = pd.to_datetime(candles_supplement._id)
            candles_dict = candles_supplement.to_dict('records')
            candles_accessor.bulk_insert(currency_pare=self.__instrument, dict_array=candles_dict)

        stocked_candles = candles_accessor.query_candles(
            currency_pare=self.__instrument,
            start_dt=start_time, end_dt=end_time
        )
        del candles_accessor

        return stocked_candles

    def load_candles_by_duration(self, start, end, granularity='M5'):
        ''' 広範囲期間チャート取得用の複数回リクエスト '''
        candles = None
        requestable_duration = self.__calc_requestable_time_duration(granularity)
        next_starttime = start
        # INFO: start から end まで1回のリクエストで取得できる場合は、取れるだけたくさん取得してしまう
        next_endtime = start + requestable_duration

        while next_starttime < end:
            now = datetime.datetime.now() - datetime.timedelta(hours=9, minutes=1)
            if now < next_endtime: next_endtime = now
            response = self.__request_oanda_instruments(
                start=self.__convert_datetime_into_oanda_format(next_starttime),
                end=self.__convert_datetime_into_oanda_format(next_endtime),
                granularity=granularity
            )
            tmp_candles = self.__transform_to_candle_chart(response)
            candles = FXBase.union_candles_distinct(candles, tmp_candles)
            print('取得済み: {datetime}まで'.format(datetime=next_endtime))
            time.sleep(1)

            next_starttime += requestable_duration
            next_endtime += requestable_duration

        return {'success': '[Client] APIリクエスト成功', 'candles': candles}

    def request_latest_candles(self, target_datetime, granularity='M10', period_of_time='D'):
        end_datetime = self.__str_to_datetime(target_datetime)
        time_unit = period_of_time[0]
        if time_unit == 'M':
            start_datetime = end_datetime - datetime.timedelta(minutes=int(period_of_time[1:]))
        elif time_unit == 'H':
            start_datetime = end_datetime - datetime.timedelta(hours=int(period_of_time[1:]))
        elif time_unit == 'D':
            start_datetime = end_datetime - datetime.timedelta(days=1)

        try:
            response = self.__request_oanda_instruments(
                start=self.__convert_datetime_into_oanda_format(start_datetime),
                end=self.__convert_datetime_into_oanda_format(end_datetime),
                granularity=granularity
            )
        except V20Error as error:
            print('[request_latest_candles] V20Error: {},\nstart: {},\nend: {}'.format(
                error, start_datetime, end_datetime
            ))
            # INFO: 保険として、1分前のデータの再取得を試みる
            start_datetime -= datetime.timedelta(minutes=1)
            end_datetime -= datetime.timedelta(minutes=1)
            response = self.__request_oanda_instruments(
                start=self.__convert_datetime_into_oanda_format(start_datetime),
                end=self.__convert_datetime_into_oanda_format(end_datetime),
                granularity=granularity
            )

        candles = self.__transform_to_candle_chart(response)
        return candles

    # INFO: request-something (excluding candles)
    def request_is_tradeable(self):
        params = {'instruments': self.__instrument}  # 'USD_JPY,EUR_USD,EUR_JPY'
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
        # INFO: .to_dictは、単にコンソールログの見やすさ向上のために使用中
        latest_candle = self.specify_count_and_load_candles(
            count=1, granularity='M1'
        )['candles'].iloc[-1].to_dict()

        candle_dict = FXBase.get_candles().iloc[-1].to_dict()
        FXBase.replace_latest_price('close', latest_candle['close'])
        if candle_dict['high'] < latest_candle['high']:
            FXBase.replace_latest_price('high', latest_candle['high'])
        elif candle_dict['low'] > latest_candle['low']:
            FXBase.replace_latest_price('low', latest_candle['low'])
        print('[Client] 直前値', candle_dict)
        print('[Client] 現在値', latest_candle)

    def request_open_trades(self):
        ''' OANDA上でopenなポジションの情報を取得 '''
        request_obj = trades.OpenTrades(accountID=os.environ['OANDA_ACCOUNT_ID'])
        response = self.__api_client.request(request_obj)

        # TODO: last_transactionID は 対象 instrument のlast transaction の ID が望ましい
        self.__last_transaction_id = response['lastTransactionID']
        open_trades = response['trades']

        extracted_trades = [
            trade for trade in open_trades if (
                # 'clientExtensions' not in trade.keys() and
                trade['instrument'] == self.__instrument
            )
        ]
        self.__trade_ids = [trade['id'] for trade in extracted_trades]

        open_position_for_diplay = [
            {
                'instrument': trade['instrument'],
                'price': trade['price'],
                'units': trade['initialUnits'],
                'openTime': trade['openTime'],
                'stoploss': trade['stopLossOrder']
            } for trade in extracted_trades
        ]
        print('[Client] open_trades: {}'.format(open_position_for_diplay != []))
        pprint.pprint(open_position_for_diplay, compact=True)
        return extracted_trades

    def request_market_ordering(self, posi_nega_sign='', stoploss_price=None):
        ''' 成行注文を実施 '''
        if stoploss_price is None: return {'error': '[Client] StopLoss注文なしでの成り行き注文を禁止します。'}

        data = {
            'order': {
                'stopLossOnFill': {
                    'timeInForce': 'GTC',
                    'price': str(stoploss_price)[:7]  # TODO: 桁数が少ない通貨ペアも考慮する
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
        try:
            response = self.__api_client.request(request_obj)['orderCreateTransaction']
        except V20Error as error:
            logger.error('[request_market_ordering] V20Error: {}'.format(error))

        response_for_display = {
            'instrument': response['instrument'],
            'price': response['price'],
            'units': response['units'],
            'time': response['time'],
            'stoploss': response['stopLossOnFill']
        }
        logger.info('[Client] market-order: %s', response_for_display)
        return response

    def request_closing_position(self):
        ''' ポジションをclose '''
        if self.__trade_ids == []: return {'error': '[Client] closeすべきポジションが見つかりませんでした。'}

        target_trade_id = self.__trade_ids[0]
        # data = {'units': self.__units}
        request_obj = trades.TradeClose(
            accountID=os.environ['OANDA_ACCOUNT_ID'], tradeID=target_trade_id  # , data=data
        )
        response = self.__api_client.request(request_obj)
        logger.info('[Client] close-position: %s', response)
        return response

    def request_trailing_stoploss(self, stoploss_price=None):
        ''' ポジションのstoplossを強気方向に修正 '''
        if self.__trade_ids == []: return {'error': '[Client] trailすべきポジションが見つかりませんでした。'}
        if stoploss_price is None: return {'error': '[Client] StopLoss価格がなく、trailできませんでした。'}

        data = {
            # 'takeProfit': {'timeInForce': 'GTC', 'price': '1.3'},
            'stopLoss': {'timeInForce': 'GTC', 'price': str(stoploss_price)[:7]}
        }
        request_obj = trades.TradeCRCDO(
            accountID=os.environ['OANDA_ACCOUNT_ID'],
            tradeID=self.__trade_ids[0],
            data=data
        )
        response = self.__api_client.request(request_obj)
        logger.info('[Client] trail: %s', response)
        return response

    def request_transactions(self):
        params = {
            # len(from ... to) <= 1000
            'to': int(self.__last_transaction_id),
            'from': int(self.__last_transaction_id) - 999,
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

    def __calc_candles_wanted(self, days=1, granularity='M5'):
        time_unit = granularity[0]
        if time_unit == 'D':
            return int(days)

        time_span = int(granularity[1:])
        if time_unit == 'H':
            return int(days * 24 / time_span)

        if time_unit == 'M':
            return int(days * 24 * 60 / time_span)

    def __request_oanda_instruments(
            self, start=None, end=None, candles_count=None, granularity='M5'
    ):
        ''' OandaAPIと直接通信し、為替データを取得 '''
        if start is None and end is None:
            params = {'count': candles_count, 'granularity': granularity}
        elif candles_count is not None:
            params = {
                # INFO: つけない方が一般的なレートに近くなる
                # 'alignmentTimezone':   'Asia/Tokyo',
                'from': start, 'count': candles_count,
                'granularity': granularity
            }
        else:
            params = {
                'from': start, 'to': end,
                'granularity': granularity
            }

        request_obj = module_inst.InstrumentsCandles(
            instrument=self.__instrument,
            params=params
        )
        # HACK: 現在値を取得する際、誤差で将来の時間と扱われてエラーになることがある
        try:
            response = self.__api_client.request(request_obj)
        except V20Error as error:
            logger.error('[__request_oanda_instruments] V20Error: {}'.format(error))
            return {'candles': []}

        return response

    def __transform_to_candle_chart(self, response):
        ''' APIレスポンスをチャートデータに整形 '''
        if response['candles'] == []: return pd.DataFrame(columns=[])

        candle = pd.DataFrame.from_dict([row['mid'] for row in response['candles']])
        candle = candle.astype({
            # INFO: 'float32' の方が速度は早くなるが、不要な小数点4桁目以下が出現するので64を使用
            'c': 'float64',
            'l': 'float64',
            'h': 'float64',
            'o': 'float64'
        })
        candle.columns = ['close', 'high', 'low', 'open']
        candle['time'] = [row['time'] for row in response['candles']]
        # 冗長な日時データを短縮
        # https://note.nkmk.me/python-pandas-datetime-timestamp/
        candle['time'] = pd.to_datetime(candle['time']).astype(str)
        # INFO: time ... '2018-06-03 21:00:00'
        candle['time'] = [time[:19] for time in candle.time]

        return candle

    def __calc_requestable_max_days(self, granularity='M5'):
        candles_per_a_day = self.__calc_candles_wanted(days=1, granularity=granularity)

        # http://developer.oanda.com/rest-live-v20/instrument-ep/
        max_days = int(OandaPyClient.REQUESTABLE_COUNT / candles_per_a_day)
        return max_days

    def __calc_requestable_time_duration(self, granularity):
        time_unit = granularity[0]
        if time_unit == 'M':
            minutes = int(OandaPyClient.REQUESTABLE_COUNT * int(granularity[1:])) - 1
            requestable_duration = datetime.timedelta(minutes=minutes)
        elif time_unit == 'H':
            hours = int(OandaPyClient.REQUESTABLE_COUNT * int(granularity[1:])) - 1
            requestable_duration = datetime.timedelta(hours=hours)
        elif time_unit == 'D':
            days = OandaPyClient.REQUESTABLE_COUNT
            requestable_duration = datetime.timedelta(days=days)

        return requestable_duration

    def __str_to_datetime(self, time_string):
        result_dt = datetime.datetime.strptime(time_string, '%Y-%m-%d %H:%M:%S')
        return result_dt

    def __convert_datetime_into_oanda_format(self, target_datetime):
        return target_datetime.strftime('%Y-%m-%dT%H:%M:00.000000Z')

    def __filter_and_make_df(self, response_transactions):
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
        # INFO: filtering by column
        hist_df = hist_df[[
            'id',
            'batchID',
            'tradeID',
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
        hist_df['pl'] = hist_df['pl'].astype({'pl': 'float'}).astype({'pl': 'int'})
        hist_df['time'] = [row['time'][:19] for row in filtered_transactions]

        # INFO: filtering by instrument
        hist_df = self.__fill_instrument_for_history(hist_df.copy())
        hist_df = hist_df[
            (hist_df.instrument == self.__instrument)
            | (hist_df.instrument_parent == self.__instrument)
        ]
        return hist_df

    def __fill_instrument_for_history(self, hist_df):
        hist_df_parent = hist_df.set_index(hist_df.id)['instrument']
        result_df = hist_df.merge(
            hist_df_parent, how='left',
            left_on='tradeID', right_index=True, suffixes=['', '_parent']
        )
        return result_df
