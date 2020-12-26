import datetime
import time
import logging
import os
import pprint
import sys
from collections import OrderedDict

import pandas as pd
import requests

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
import models.tools.preprocessor as prepro
from models.mongodb_accessor import MongodbAccessor

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
# pd.set_option('display.max_rows', candles_count)  # 表示可能な最大行数を設定


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

        candles = prepro.to_candle_df(response)
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
            now = datetime.datetime.now() - datetime.timedelta(hours=9, minutes=1)
            if now < next_endtime: next_endtime = now
            response = self.__request_oanda_instruments(
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
        # INFO: .to_dictは、単にコンソールログの見やすさ向上のために使用中
        latest_candle = self.load_specify_length_candles(length=1, granularity='M1')['candles'] \
                            .iloc[-1].to_dict()
        return latest_candle

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
        LOGGER.info('[Client] close-reason: %s', reason)
        LOGGER.info('[Client] close-position: %s', response)
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

    def request_latest_transactions(self, count=999):
        to_id = int(self.__last_transaction_id)
        from_id = to_id - count
        from_id = max(from_id, 1)
        response = self.request_transactions_once(from_id, to_id)
        filtered_df = prepro.filter_and_make_df(response['transactions'], self.__instrument)
        return filtered_df

    def request_transactions_once(self, from_id, to_id):
        params = {
            # len(from ... to) < 500 くらいっぽい
            'from': from_id,
            'to': to_id,
            'type': ['ORDER'],
            # 消えるtype => TRADE_CLIENT_EXTENSIONS_MODIFY, DAILY_FINANCING
        }
        request_obj = transactions.TransactionIDRange(accountID=os.environ['OANDA_ACCOUNT_ID'], params=params)
        response = self.__request(request_obj)

        return response

    # TODO: from_str の扱いを決める必要あり
    def request_transaction_ids(self, from_str='2020-01-01T04:58:09.460556567Z'):
        params = {'from': from_str, 'pageSize': 1000}
        request_obj = transactions.TransactionList(accountID=os.environ['OANDA_ACCOUNT_ID'], params=params)
        response = self.__request(request_obj)
        if 'error' in response:
            return response, None

        ids = prepro.extract_transaction_ids(response)
        return ids['old_id'], ids['last_id']

    def __request(self, obj):
        try:
            response = self.__api_client.request(obj)
        except V20Error as error:
            LOGGER.error('[%s] V20Error: %s', sys._getframe().f_back.f_code.co_name, error)
            # error.msg
            return {'error': error.code}
        except requests.exceptions.ConnectionError as error:
            LOGGER.error('[%s] requests.exceptions.ConnectionError: %s', sys._getframe().f_code.co_name, error)
            return {'error': 500}
        else:
            return response

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
        params = {
            'alignmentTimezone': 'Etc/GMT',
            'dailyAlignment': 0,
            'granularity': granularity
        }
        if start is None and end is None:
            params.update({'count': candles_count})
        elif candles_count is not None:
            params.update({'from': start, 'count': candles_count})
        else:
            params.update({'from': start, 'to': end})

        request_obj = module_inst.InstrumentsCandles(
            instrument=self.__instrument,
            params=params
        )
        # HACK: 現在値を取得する際、誤差で将来の時間と扱われてエラーになることがある
        response = self.__request(request_obj)
        if 'error' in response:
            return {'candles': [], 'error': response['error']}

        return response

    def __calc_requestable_max_days(self, granularity='M5'):
        candles_per_a_day = self.__calc_candles_wanted(days=1, granularity=granularity)

        # http://developer.oanda.com/rest-live-v20/instrument-ep/
        max_days = int(OandaPyClient.REQUESTABLE_COUNT / candles_per_a_day)
        return max_days

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
