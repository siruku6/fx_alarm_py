import datetime
import time
import logging
import os
import pandas as pd
import pprint
import requests
from collections import OrderedDict

# For trading
from oandapyV20 import API
from oandapyV20.exceptions import V20Error
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.instruments as module_inst
import oandapyV20.endpoints.transactions as transactions

import models.tools.format_converter as converter
from models.tools.interface import select_from_dict
# from models.candles_csv_accessor import CandlesCsvAccessor
from models.mongodb_accessor import MongodbAccessor

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
# pd.set_option('display.max_rows', candles_count)  # 表示可能な最大行数を設定


class FXBase():
    __candles = None
    __d1_candles = None

    # candles
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

    # d1_candles
    @classmethod
    def get_d1_candles(cls):
        return cls.__d1_candles

    @classmethod
    def set_d1_candles(cls, d1_candles):
        cls.__d1_candles = d1_candles


# granularity list
# http://developer.oanda.com/rest-live-v20/instrument-df/#CandlestickGranularity
class OandaPyClient():
    REQUESTABLE_COUNT = 5000

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

    def __init__(self, instrument=None, environment=None, test=False):
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
        self.__test = test

    #
    # Public
    #

    # INFO: request-candles
    def load_specify_length_candles(self, length=60, granularity='M5'):
        ''' チャート情報を更新 '''
        response = self.__request_oanda_instruments(
            candles_count=length,
            granularity=granularity
        )

        candles = self.__transform_to_candle_chart(response)
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
                start=converter.to_oanda_format(start_datetime),
                end=converter.to_oanda_format(end_datetime),
                granularity=granularity
            )
            tmp_candles = self.__transform_to_candle_chart(response)
            candles = FXBase.union_candles_distinct(candles, tmp_candles)
            print('残り: {remaining_days}日分'.format(remaining_days=remaining_days))
            time.sleep(1)

        return {'success': '[Watcher] APIリクエスト成功', 'candles': candles}

    def load_or_query_candles(self, start_time, end_time, granularity):
        ''' (10分足用) 取得済みであれば mongodb から candles を取得してくれる '''
        # candles_accessor = CandlesCsvAccessor(granularity=granularity, currency_pare=self.__instrument)
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
            now = datetime.datetime.now() - datetime.timedelta(hours=9, minutes=1)
            if now < next_endtime: next_endtime = now
            response = self.__request_oanda_instruments(
                start=converter.to_oanda_format(next_starttime),
                end=converter.to_oanda_format(next_endtime),
                granularity=granularity
            )
            tmp_candles = self.__transform_to_candle_chart(response)
            candles = FXBase.union_candles_distinct(candles, tmp_candles)
            print('取得済み: {datetime}まで'.format(datetime=next_endtime))
            time.sleep(1)

            next_starttime += requestable_duration
            next_endtime += requestable_duration

        return {'success': '[Client] APIリクエスト成功', 'candles': candles}

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
        latest_candle = self.load_specify_length_candles(length=1, granularity='M1')['candles'] \
                            .iloc[-1].to_dict()

        candle_dict = FXBase.get_candles().iloc[-1].to_dict()
        FXBase.replace_latest_price('close', latest_candle['close'])
        if candle_dict['high'] < latest_candle['high']:
            FXBase.replace_latest_price('high', latest_candle['high'])
        elif candle_dict['low'] > latest_candle['low']:
            FXBase.replace_latest_price('low', latest_candle['low'])
        print('[Client] Last_H4: {}, Current_M1: {}'.format(candle_dict, latest_candle))
        print('[Client] New_H4: {}'.format(FXBase.get_candles().iloc[-1].to_dict()))

    def request_open_trades(self):
        ''' OANDA上でopenなポジションの情報を取得 '''
        request_obj = trades.OpenTrades(accountID=os.environ['OANDA_ACCOUNT_ID'])
        response = self.__api_client.request(request_obj)

        # INFO: lastTransactionID は最後に行った売買のID
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
                'stoploss': {
                    'createTime': trade['stopLossOrder']['createTime'],
                    'price': trade['stopLossOrder']['price'],
                    'timeInForce': trade['stopLossOrder']['timeInForce']
                }
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

        if self.__test:
            print('[Test] market_order: {}'.format(data))
            return data

        request_obj = orders.OrderCreate(
            accountID=os.environ['OANDA_ACCOUNT_ID'], data=data
        )
        try:
            response = self.__api_client.request(request_obj)['orderCreateTransaction']
        except V20Error as error:
            LOGGER.error('[request_market_ordering] V20Error: {}'.format(error))

        response_for_display = {
            'instrument': response.get('instrument'),
            # 'price': response.get('price'),  # market order に price はなかった
            'units': response.get('units'),
            'time': response.get('time'),
            'stopLossOnFill': response.get('stopLossOnFill')
        }
        LOGGER.info('[Client] market-order: %s', response_for_display)
        return response

    def request_closing_position(self, reason=''):
        ''' ポジションをclose '''
        if self.__trade_ids == []: return {'error': '[Client] closeすべきポジションが見つかりませんでした。'}
        if self.__test:
            print('[Test] close_order')
            return

        target_trade_id = self.__trade_ids[0]
        # data = {'units': self.__units}
        request_obj = trades.TradeClose(
            accountID=os.environ['OANDA_ACCOUNT_ID'], tradeID=target_trade_id  # , data=data
        )
        response = self.__api_client.request(request_obj)
        LOGGER.info('[Client] close-position: %s \n REASON: %s', response, reason)
        if response.get('orderFillTransaction') is None and response.get('orderCancelTransaction') is not None:
            return 'The exit order was canceled because of {}'.format(
                response.get('orderCancelTransaction').get('reason')
            )

        response_for_display = {
            'price': response['orderFillTransaction'].get('price'),
            'profit': response['orderFillTransaction'].get('pl'),
            'units': response['orderFillTransaction'].get('units'),
            'reason': response['orderFillTransaction'].get('reason')
        }
        return response_for_display

    def request_trailing_stoploss(self, stoploss_price=None):
        ''' ポジションのstoplossを強気方向に修正 '''
        if self.__trade_ids == []: return {'error': '[Client] trailすべきポジションが見つかりませんでした。'}
        if stoploss_price is None: return {'error': '[Client] StopLoss価格がなく、trailできませんでした。'}

        data = {
            # 'takeProfit': {'timeInForce': 'GTC', 'price': '1.3'},
            'stopLoss': {'timeInForce': 'GTC', 'price': str(stoploss_price)[:7]}
        }
        if self.__test:
            print('[Test] trailing: {}'.format(data))
            return

        request_obj = trades.TradeCRCDO(
            accountID=os.environ['OANDA_ACCOUNT_ID'],
            tradeID=self.__trade_ids[0],
            data=data
        )
        response = self.__api_client.request(request_obj)
        LOGGER.info('[Client] trail: %s', response)
        return response

    def request_transactions(self, count=999):
        start = int(self.__last_transaction_id) - count
        if start < 1:
            start = 1
        params = {
            # len(from ... to) <= 1000
            'to': int(self.__last_transaction_id),
            'from': start,
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
            LOGGER.error('[__request_oanda_instruments] V20Error: {}'.format(error))
            return {'candles': []}
        except requests.exceptions.ConnectionError as error:
            LOGGER.error('[__request_oanda_instruments] requests.exceptions.ConnectionError: {}'.format(error))
            return {'candles': []}

        return response

    def __transform_to_candle_chart(self, response):
        ''' APIレスポンスをチャートデータに整形 '''
        if response['candles'] == []: return pd.DataFrame(columns=[])

        candle = pd.DataFrame.from_dict([row['mid'] for row in response['candles']])
        candle = candle.astype({
            # INFO: 'float32' の方が速度は早くなるが、不要な小数点4桁目以下が出現するので64を使用
            'c': 'float64', 'h': 'float64', 'l': 'float64', 'o': 'float64'
        })
        candle.rename(columns={'c': 'close', 'h': 'high', 'l': 'low', 'o': 'open'}, inplace=True)
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
        days = hours = minutes = 0

        def max_multiply(number):
            return int(OandaPyClient.REQUESTABLE_COUNT * int(number)) - 1

        time_unit = granularity[0]
        if time_unit == 'M':
            minutes = max_multiply(granularity[1:])
        elif time_unit == 'H':
            hours = max_multiply(granularity[1:])
        elif time_unit == 'D':
            days = OandaPyClient.REQUESTABLE_COUNT

        return datetime.timedelta(days=days, hours=hours, minutes=minutes)

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
        hist_df = self.__fill_instrument_for_history(hist_df.copy())
        # INFO: transaction が一切なかった場合の warning 回避のため
        hist_df['instrument'] = hist_df['instrument'].astype(str, copy=False)
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
