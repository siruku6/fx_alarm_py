import os
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from aws_lambda_powertools import Logger
import requests

# For trading
from oandapyV20 import API
from oandapyV20.exceptions import V20Error
from oandapyV20.endpoints.apirequest import APIRequest
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.instruments as module_inst
import oandapyV20.endpoints.transactions as transactions

import src.tools.preprocessor as prepro


ISO_DATETIME_STR = str

LOGGER = Logger()


# granularity list
# http://developer.oanda.com/rest-live-v20/instrument-df/#CandlestickGranularity
class OandaClient():
    REQUESTABLE_COUNT = 5000

    def __init__(self, instrument: str, environment: str = None, test: bool = False):
        self.__api_client = API(
            access_token=os.environ['OANDA_ACCESS_TOKEN'],
            # 'practice' or 'live' is valid
            environment=environment or os.environ.get('OANDA_ENVIRONMENT') or 'practice'
        )
        self.last_transaction_id: Optional[str] = None
        self.__accessable: bool = True
        self.__instrument: str = instrument
        self.__units: str = os.environ.get('UNITS') or '1'
        self.__trade_ids: List[Optional[str]] = []
        self.__test: bool = test

    @property
    def accessable(self) -> bool:
        return self.__accessable

    def __stop_request(self) -> None:
        self.__accessable = False

    #
    # Public
    #
    # INFO: request-something (excluding candles)
    def request_is_tradeable(self) -> Dict[str, Union[str, bool]]:
        params = {'instruments': self.__instrument}  # 'USD_JPY,EUR_USD,EUR_JPY'
        request_obj: APIRequest = pricing.PricingInfo(
            accountID=os.environ['OANDA_ACCOUNT_ID'], params=params
        )
        response = self.__request(request_obj)
        tradeable = response['prices'][0]['tradeable']
        return {
            'instrument': self.__instrument,
            'tradeable': tradeable
        }

    def request_open_trades(self) -> List[dict]:
        ''' OANDA上でopenなポジションの情報を取得 '''
        request_obj: APIRequest = trades.OpenTrades(accountID=os.environ['OANDA_ACCOUNT_ID'])
        response = self.__request(request_obj)

        # INFO: lastTransactionID is ID of the last trade transaction.
        self.last_transaction_id = response['lastTransactionID']
        open_trades = response['trades']

        extracted_trades: List[dict] = [
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
        LOGGER.info({'[Client] position': open_position_for_diplay})
        return extracted_trades

    def request_market_ordering(
        self, posi_nega_sign: str = '', stoploss_price: Optional[float] = None
    ) -> Dict[str, Any]:
        ''' market order '''
        if stoploss_price is None: return {'error': '[Client] StopLoss注文なしでの成り行き注文を禁止します。'}

        data = {
            'order': {
                'stopLossOnFill': {
                    'timeInForce': 'GTC',
                    'price': str(stoploss_price)[:7]  # TODO: consider currrency pairs whose digits are too small
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

        request_obj: APIRequest = orders.OrderCreate(
            accountID=os.environ['OANDA_ACCOUNT_ID'], data=data
        )
        res: Dict[str, Any] = self.__request(request_obj)
        LOGGER.info({'[Client] market-order': res})

        response: Dict[str, Any] = res['orderCreateTransaction']
        if response == {}:
            return {'messsage': 'Market order is failed.', 'result': res}

        response_for_display = {
            'instrument': response.get('instrument'),
            # 'price': response.get('price'),  # There isn't 'price' in result of market order
            'units': response.get('units'),
            'time': response.get('time'),
            'stopLossOnFill': response.get('stopLossOnFill')
        }

        return {
            'messsage': 'Market order is done !',
            'order': response_for_display
        }

    def request_closing(self, reason: str = '') -> Dict[str, Any]:
        ''' close position '''
        if self.__trade_ids == []: return {'error': '[Client] The position to be closed was missing.'}
        if self.__test:
            print('[Test] close_order')
            return {}

        target_trade_id = self.__trade_ids[0]
        # data = {'units': self.__units}
        request_obj: APIRequest = trades.TradeClose(
            accountID=os.environ['OANDA_ACCOUNT_ID'], tradeID=target_trade_id  # , data=data
        )
        response: Dict[str, Any] = self.__request(request_obj)

        if response.get('orderFillTransaction') is None and response.get('orderCancelTransaction') is not None:
            reason = response.get('orderCancelTransaction').get('reason')  # type: ignore
            LOGGER.warn({
                'message': 'The exit order was canceled because of {}'.format(reason)
            })
            return {'[Client] message': 'Close order is failed', 'reason': reason}

        dict_close_notification: Dict[str, Any] = {
            '[Client] message': 'Position is closed',
            'reason': reason, 'result': response
        }
        LOGGER.info(dict_close_notification)
        return dict_close_notification

    def request_trailing_stoploss(self, stoploss_price: float) -> Dict[str, Any]:
        ''' change stoploss price toward the direction helping us get revenue '''
        if self.__trade_ids == []:
            return {'error': '[Client] There is no position'}

        data = {
            # 'takeProfit': {'timeInForce': 'GTC', 'price': '1.3'},
            'stopLoss': {'timeInForce': 'GTC', 'price': str(stoploss_price)[:7]}
        }

        request_obj: APIRequest = trades.TradeCRCDO(
            accountID=os.environ['OANDA_ACCOUNT_ID'],
            tradeID=self.__trade_ids[0],
            data=data
        )
        response: Dict[str, Any] = self.__request(request_obj)
        LOGGER.info({'[Client] trail': response})
        return response

    def request_transactions_once(self, from_id: str, to_id: str) -> Dict[str, Any]:
        params = {
            # len(from ... to) < 500 くらいっぽい
            'from': from_id,
            'to': to_id,
            'type': ['ORDER'],
            # 消えるtype => TRADE_CLIENT_EXTENSIONS_MODIFY, DAILY_FINANCING
        }
        request_obj: APIRequest = transactions.TransactionIDRange(
            accountID=os.environ['OANDA_ACCOUNT_ID'], params=params
        )
        response: Dict[str, Any] = self.__request(request_obj)

        return response

    # TODO: from_str の扱いを決める必要あり
    def request_transaction_ids(self, from_str: str, to_str: str) -> Tuple[str, str]:
        params: Dict[str, Union[str, int]] = {'from': from_str, 'pageSize': 1000, 'to': to_str}
        request_obj: APIRequest = transactions.TransactionList(accountID=os.environ['OANDA_ACCOUNT_ID'], params=params)
        response: Dict[str, Any] = self.__request(request_obj)
        if 'error' in response:
            self.__stop_request()
            return None, None  # type: ignore

        ids: Dict[str, str] = prepro.extract_transaction_ids(response)
        return ids['old_id'], ids['last_id']

    #
    # Private
    #
    def __request(self, obj: APIRequest) -> Dict[str, Any]:
        try:
            response: Dict[str, Any] = self.__api_client.request(obj)
        except V20Error as error:
            LOGGER.error({f'[{sys._getframe().f_back.f_code.co_name}] V20Error': error})  # type: ignore
            LOGGER.info({f'[{sys._getframe().f_back.f_code.co_name}] dir(error)': dir(error)})  # type: ignore
            # error.msg
            return {'error': error.code}
        except requests.exceptions.ConnectionError as error:
            LOGGER.error({f'[{sys._getframe().f_code.co_name}] requests.exceptions.ConnectionError': error})
            return {'error': 500}
        else:
            return response

    def query_instruments(
        self,
        start: Optional[ISO_DATETIME_STR] = None,
        end: Optional[ISO_DATETIME_STR] = None,
        candles_count: Optional[int] = None,
        granularity: str = 'M5'
    ) -> Dict[str, Any]:
        ''' request price data against OandaAPI '''
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

        request_obj: APIRequest = module_inst.InstrumentsCandles(
            instrument=self.__instrument,
            params=params
        )
        # HACK: 現在値を取得する際、誤差で将来の時間と扱われてエラーになることがある
        response: Dict[str, Any] = self.__request(request_obj)
        if 'error' in response:
            return {'candles': [], 'error': response['error']}

        return response
