import logging
import os
import pprint
import sys
from typing import Any, Dict, List, Tuple, Union

import requests

# For trading
from oandapyV20 import API
from oandapyV20.exceptions import V20Error
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.instruments as module_inst
import oandapyV20.endpoints.transactions as transactions

import models.tools.preprocessor as prepro

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


# granularity list
# http://developer.oanda.com/rest-live-v20/instrument-df/#CandlestickGranularity
class OandaClient():
    REQUESTABLE_COUNT = 5000

    def __init__(self, instrument: str, environment: str=None, test: bool=False):
        ''' 固定パラメータの設定 '''
        self.__api_client = API(
            access_token=os.environ['OANDA_ACCESS_TOKEN'],
            # 'practice' or 'live' is valid
            environment=environment or os.environ.get('OANDA_ENVIRONMENT') or 'practice'
        )
        self.last_transaction_id: str = None
        self.__accessable: bool = True
        self.__instrument: str = instrument
        self.__units: str = os.environ.get('UNITS') or '1'
        self.__trade_ids: List = []
        self.__test: bool = test

    @property
    def accessable(self):
        return self.__accessable

    def __stop_request(self):
        self.__accessable: bool = False

    #
    # Public
    #
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

    def request_open_trades(self):
        ''' OANDA上でopenなポジションの情報を取得 '''
        request_obj = trades.OpenTrades(accountID=os.environ['OANDA_ACCOUNT_ID'])
        response = self.__api_client.request(request_obj)

        # INFO: lastTransactionID は最後に行った売買のID
        self.last_transaction_id = response['lastTransactionID']
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

    def request_transactions_once(self, from_id: str, to_id: str) -> Dict[str, Any]:
        params = {
            # len(from ... to) < 500 くらいっぽい
            'from': from_id,
            'to': to_id,
            'type': ['ORDER'],
            # 消えるtype => TRADE_CLIENT_EXTENSIONS_MODIFY, DAILY_FINANCING
        }
        request_obj = transactions.TransactionIDRange(accountID=os.environ['OANDA_ACCOUNT_ID'], params=params)
        response: Dict[str, Any] = self.__request(request_obj)

        return response

    # TODO: from_str の扱いを決める必要あり
    def request_transaction_ids(self, from_str: str, to_str: str) -> Tuple[str, str]:
        params: Dict[str, Union[str, int]] = {'from': from_str, 'pageSize': 1000, 'to': to_str}
        request_obj = transactions.TransactionList(accountID=os.environ['OANDA_ACCOUNT_ID'], params=params)
        response: Dict[str, Any] = self.__request(request_obj)
        if 'error' in response:
            self.__stop_request()
            return None, None

        ids: Dict[str, str] = prepro.extract_transaction_ids(response)
        return ids['old_id'], ids['last_id']

    #
    # Private
    #
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

    def query_instruments(
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
