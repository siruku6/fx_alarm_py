import os
from typing import Dict, List, Union

from dotenv import load_dotenv
import pytest

from models.trader_config import TraderConfig


@pytest.fixture(scope='session', autouse=True)
def load_env() -> None:
    dotenv_path: str = os.path.join('./.env')
    load_dotenv(dotenv_path)
    yield


@pytest.fixture(name='instrument', scope='module')
def fixture_instrument():
    return 'DUMMY_JPY'


@pytest.fixture(name='stoploss_buffer', scope='module')
def fixture_stoploss_buffer():
    return 0.02


@pytest.fixture(name='set_envs', scope='module')
def fixture_set_envs(instrument, stoploss_buffer):
    os.environ['GRANULARITY'] = ''
    os.environ['INSTRUMENT'] = str(instrument)
    os.environ['STOPLOSS_BUFFER'] = str(stoploss_buffer)
    yield


@pytest.fixture(name='config', scope='function')
def fixture_config(set_envs) -> TraderConfig:
    set_envs
    yield TraderConfig(operation='unittest')


@pytest.fixture(scope='session')
def dummy_instruments():
    return {
        'candles': [{
            'complete': True,
            'mid': {'c': '111.576', 'h': '111.576', 'l': '111.566', 'o': '111.573'},
            'time': '2019-04-28T21:00:00.000000000Z',
            'volume': 5
        }, {
            'complete': True,
            'mid': {'c': '111.571', 'h': '111.571', 'l': '111.571', 'o': '111.571'},
            'time': '2019-04-28T21:05:00.000000000Z',
            'volume': 1
        }, {
            'complete': True,
            'mid': {'c': '111.568', 'h': '111.590', 'l': '111.568', 'o': '111.574'},
            'time': '2019-04-28T21:10:00.000000000Z',
            'volume': 24
        }],
        'granularity': 'M5',
        'instrument': 'USD_JPY'
    }


@pytest.fixture(scope='session')
def dummy_raw_open_trades():
    return {
        'trades': [
            {
                'instrument': 'DE30_EUR',
                'financing': '0.0000',
                'openTime': '2016-10-28T14:28:05.231759081Z',
                'initialUnits': '10',
                'currentUnits': '10',
                'price': '10678.3',
                'unrealizedPL': '136.0000',
                'realizedPL': '0.0000',
                'state': 'OPEN',
                'id': '2315'
            }
        ],
        'lastTransactionID': '2317'
    }


@pytest.fixture(scope='session')
def dummy_open_trades():
    return [{
        'currentUnits': '-1',
        'financing': '0.0000',
        'id': '699',
        'initialMarginRequired': '5.0332',
        'initialUnits': '-1',
        'instrument': 'EUR_USD',
        'marginUsed': '5.0333',
        'openTime': '2019-04-18T14:05:59.912794035Z',
        'price': '1.12488',
        'realizedPL': '0.0000',
        'state': 'OPEN',
        'stopLossOrder': {
            'createTime': '2019-04-18T14:05:59.912794035Z',
            'guaranteed': False,
            'id': '700',
            'price': '1.20000',
            'state': 'PENDING',
            'timeInForce': 'GTC',
            'tradeID': '699',
            'triggerCondition': 'DEFAULT',
            'type': 'STOP_LOSS'
        },
        'unrealizedPL': '-0.0090'
    }, {
        'clientExtensions': {'id': '200092793', 'tag': '0'},
        'currentUnits': '-100000',
        'financing': '0.0000',
        'id': '680',
        'initialMarginRequired': '503408.0000',
        'initialUnits': '-100000',
        'instrument': 'EUR_USD',
        'marginUsed': '503328.0000',
        'openTime': '2019-04-18T13:27:46.827746138Z',
        'price': '1.12450',
        'realizedPL': '0.0000',
        'state': 'OPEN',
        'stopLossOrder': {
            'createTime': '2019-04-18T13:29:18.501108427Z',
            'guaranteed': False,
            'id': '686',
            'price': '1.12952',
            'replacesOrderID': '684',
            'state': 'PENDING',
            'timeInForce': 'GTC',
            'tradeID': '680',
            'triggerCondition': 'DEFAULT',
            'type': 'STOP_LOSS'
        },
        'takeProfitOrder': {
            'createTime': '2019-04-18T13:29:42.489119645Z',
            'id': '687',
            'price': '1.11989',
            'state': 'PENDING',
            'timeInForce': 'GTC',
            'tradeID': '680',
            'triggerCondition': 'DEFAULT',
            'type': 'TAKE_PROFIT'
        },
        'unrealizedPL': '-5146.6640'
    }]


@pytest.fixture(scope='session')
def dummy_long_without_stoploss_trades():
    return [{
        'currentUnits': '1',
        'financing': '0.0000',
        'id': '699',
        'initialMarginRequired': '5.0332',
        'initialUnits': '1',
        'instrument': 'EUR_USD',
        'marginUsed': '5.0333',
        'openTime': '2019-04-18T14:05:59.912794035Z',
        'price': '1.12488',
        'realizedPL': '0.0000',
        'state': 'OPEN',
        'unrealizedPL': '0.0090'
    }]


# TODO:
#   この辺の記事によると、 dummy_stoploss_price はここではなく、各testメソッド内に記載して簡略化できそう
#   そうすれば、 dummy_stoploss_price というメソッドその物がいらなくなる
#   ただ、みんな何言ってるのかよくわからない
# https://qastack.jp/programming/18011902/pass-a-parameter-to-a-fixture-function
# https://docs.pytest.org/en/latest/example/parametrize.html#indirect-parametrization
# https://www.366service.com/jp/qa/665a767bf116ce225233c4b9ef915165
@pytest.fixture(scope='session')
def dummy_stoploss_price():
    return 111.111


@pytest.fixture()
def dummy_market_order_response(dummy_stoploss_price):
    return {
        'orderCreateTransaction': {
            'instrument': 'dummy_instrument',
            'units': '1000',
            'time': '2020-01-13T12:34:56.912794035Z',  # 2019-04-18T14:05:59.912794035Z
            'stopLossOnFill': str(dummy_stoploss_price)
        }
    }


@pytest.fixture(scope='session')
def dummy_trades_list():
    return {
        'lastTransactionID': '700',
        'trades': [{
            'currentUnits': '-1',
            'financing': '0.0000',
            'id': '699',
            'initialMarginRequired': '5.0332',
            'initialUnits': '-1',
            'instrument': 'EUR_USD',
            'marginUsed': '5.0333',
            'openTime': '2019-04-18T14:05:59.912794035Z',
            'price': '1.12488',
            'realizedPL': '0.0000',
            'state': 'OPEN',
            'stopLossOrder': {
                'createTime': '2019-04-18T14:05:59.912794035Z',
                'guaranteed': False,
                'id': '700',
                'price': '1.20000',
                'state': 'PENDING',
                'timeInForce': 'GTC',
                'tradeID': '699',
                'triggerCondition': 'DEFAULT',
                'type': 'STOP_LOSS'
            },
            'unrealizedPL': '-0.0090'
        }, {
            'averageClosePrice': '1.13024',
            'closeTime': '2019-04-16T14:28:10.296990535Z',
            'closingTransactionIDs': ['669'],
            'currentUnits': '0',
            'financing': '0.0000',
            'id': '665',
            'initialMarginRequired': '5.0623',
            'initialUnits': '1',
            'instrument': 'EUR_USD',
            'openTime': '2019-04-16T14:25:32.494525071Z',
            'price': '1.13025',
            'realizedPL': '-0.0011',
            'state': 'CLOSED',
            'stopLossOrder': {
                'cancelledTime': '2019-04-16T14:28:10.296990535Z',
                'cancellingTransactionID': '670',
                'createTime': '2019-04-16T14:25:32.494525071Z',
                'guaranteed': False,
                'id': '666',
                'price': '1.11000',
                'state': 'CANCELLED',
                'timeInForce': 'GTC',
                'tradeID': '665',
                'triggerCondition': 'DEFAULT',
                'type': 'STOP_LOSS'
            }
        }, {
            'averageClosePrice': '1.12448',
            'clientExtensions': {'id': '199996501', 'tag': '0'},
            'closeTime': '2019-04-18T13:27:37.640052514Z',
            'closingTransactionIDs': ['678'],
            'currentUnits': '0',
            'financing': '-2318.0583',
            'id': '643',
            'initialMarginRequired': '49812.0000',
            'initialUnits': '10000',
            'instrument': 'EUR_USD',
            'openTime': '2019-03-31T22:51:55.285661036Z',
            'price': '1.12237',
            'realizedPL': '2361.6386',
            'state': 'CLOSED'
        }, {
            'averageClosePrice': '1.12490',
            'closeTime': '2019-04-18T14:00:48.397205325Z',
            'closingTransactionIDs': ['693'],
            'currentUnits': '0',
            'financing': '-0.2320',
            'id': '640',
            'initialMarginRequired': '4.9825',
            'initialUnits': '1',
            'instrument': 'EUR_USD',
            'openTime': '2019-03-31T22:44:14.772072696Z',
            'price': '1.12237',
            'realizedPL': '0.2830',
            'state': 'CLOSED',
            'stopLossOrder': {
                'cancelledTime': '2019-04-18T14:00:48.397205325Z',
                'cancellingTransactionID': '695',
                'createTime': '2019-04-18T13:44:14.358586969Z',
                'guaranteed': False,
                'id': '691',
                'price': '1.11000',
                'replacesOrderID': '675',
                'state': 'CANCELLED',
                'timeInForce': 'GTC',
                'tradeID': '640',
                'triggerCondition': 'DEFAULT',
                'type': 'STOP_LOSS'
            },
            'takeProfitOrder': {
                'cancelledTime': '2019-04-18T14:00:48.397205325Z',
                'cancellingTransactionID': '694',
                'createTime': '2019-04-18T13:44:14.358586969Z',
                'id': '689',
                'price': '1.30000',
                'replacesOrderID': '673',
                'state': 'CANCELLED',
                'timeInForce': 'GTC',
                'tradeID': '640',
                'triggerCondition': 'DEFAULT',
                'type': 'TAKE_PROFIT'
            }
        }, {
            'averageClosePrice': '1.14645',
            'clientExtensions': {'id': '199364199', 'tag': '0'},
            'closeTime': '2019-02-01T12:15:02.436718568Z',
            'closingTransactionIDs': ['488'],
            'currentUnits': '0',
            'financing': '-114.1038',
            'id': '458',
            'initialMarginRequired': '998920.0000',
            'initialUnits': '200000',
            'instrument': 'EUR_USD',
            'openTime': '2019-02-01T11:10:08.819655064Z',
            'price': '1.14671',
            'realizedPL': '-5663.4240',
            'state': 'CLOSED',
            'stopLossOrder': {
                'createTime': '2019-02-01T11:23:59.473255831Z',
                'filledTime': '2019-02-01T12:15:02.436718568Z',
                'fillingTransactionID': '488',
                'guaranteed': False,
                'id': '487',
                'price': '1.14646',
                'replacesOrderID': '485',
                'state': 'FILLED',
                'timeInForce': 'GTC',
                'tradeClosedIDs': ['458'],
                'tradeID': '458',
                'triggerCondition': 'DEFAULT',
                'type': 'STOP_LOSS'
            }
        }]
    }


@pytest.fixture(scope='session')
def past_transactions():
    return {
        'lastTransactionID': '2317',
        'transactions': [
            {
                # 売却注文
                'type': 'MARKET_ORDER',
                'instrument': 'GBP_JPY',
                'units': '-10000',
                'timeInForce': 'FOK',
                'positionFill': 'REDUCE_ONLY',
                'reason': 'TRADE_CLOSE',
                'tradeClose': {
                    'units': 'ALL',
                    'tradeID': '24210',
                    'clientTradeID': '246780152'
                },
                'id': '24213',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24213',
                'requestID': '24700198084428794',
                'time': '2020-07-06T07:00:34.825077737Z'
            }, {
                'type': 'ORDER_FILL',
                'orderID': '24213',
                'instrument': 'GBP_JPY',
                'units': '-10000',
                'requestedUnits': '-10000',
                'price': '134.578',
                'pl': '2360.0000',
                'financing': '0.0000',
                'commission': '0.0000',
                'accountBalance': '3165198.0551',
                'gainQuoteHomeConversionFactor': '1',
                'lossQuoteHomeConversionFactor': '1',
                'guaranteedExecutionFee': '0.0000',
                'halfSpreadCost': '70.0000',
                'fullVWAP': '134.578',
                'reason': 'MARKET_ORDER_TRADE_CLOSE',
                'tradesClosed': [{
                    'tradeID': '24210',
                    'clientTradeID': '246780152',
                    'units': '-10000',
                    'realizedPL': '2360.0000',
                    'financing': '0.0000',
                    'price': '134.578',
                    'guaranteedExecutionFee': '0.0000',
                    'halfSpreadCost': '70.0000'
                }],
                'fullPrice': {
                    'closeoutBid': '134.573',
                    'closeoutAsk': '134.598',
                    'timestamp': '2020-07-06T07:00:34.337107847Z',
                    'bids': [{'price': '134.578', 'liquidity': '250000'}],
                    'asks': [{'price': '134.592', 'liquidity': '250000'}]
                },
                'id': '24214',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24213',
                'requestID': '24700198084428794',
                'time': '2020-07-06T07:00:34.825077737Z'
            }, {
                'type': 'ORDER_CANCEL',
                'orderID': '24211',
                'reason': 'LINKED_TRADE_CLOSED',
                'closedTradeID': '24210',
                'tradeCloseTransactionID': '24214',
                'id': '24215',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24213',
                'requestID': '24700198084428794',
                'time': '2020-07-06T07:00:34.825077737Z'
            }, {
                # 買付注文
                'type': 'MARKET_ORDER',
                'instrument': 'USD_JPY',
                'units': '-10000',
                'timeInForce': 'FOK',
                'positionFill': 'DEFAULT',
                'stopLossOnFill': {'price': '107.773', 'timeInForce': 'GTC'},
                'reason': 'CLIENT_ORDER',
                'id': '24216',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24216',
                'requestID': '60729081923267625',
                'time': '2020-07-06T12:45:34.897898440Z'
            }, {
                'type': 'ORDER_FILL',
                'orderID': '24216',
                'instrument': 'USD_JPY',
                'units': '-10000',
                'requestedUnits': '-10000',
                'price': '107.483',
                'pl': '0.0000',
                'financing': '0.0000',
                'commission': '0.0000',
                'accountBalance': '3165198.0551',
                'gainQuoteHomeConversionFactor': '1',
                'lossQuoteHomeConversionFactor': '1',
                'guaranteedExecutionFee': '0.0000',
                'halfSpreadCost': '20.0000',
                'fullVWAP': '107.483',
                'reason': 'MARKET_ORDER',
                'tradeOpened': {
                    'price': '107.483',
                    'tradeID': '24217',
                    'units': '-10000',
                    'guaranteedExecutionFee': '0.0000',
                    'halfSpreadCost': '20.0000',
                    'initialMarginRequired': '42994.0000'
                },
                'fullPrice': {
                    'closeoutBid': '107.479',
                    'closeoutAsk': '107.491',
                    'timestamp': '2020-07-06T12:45:30.874034544Z',
                    'bids': [{'price': '107.483', 'liquidity': '250000'}],
                    'asks': [{'price': '107.487', 'liquidity': '250000'}]
                },
                'id': '24217',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24216',
                'requestID': '60729081923267625',
                'time': '2020-07-06T12:45:34.897898440Z'
            }, {
                'type': 'STOP_LOSS_ORDER',
                'tradeID': '24217',
                'timeInForce': 'GTC',
                'triggerCondition': 'DEFAULT',
                'price': '107.773',
                'reason': 'ON_FILL',
                'id': '24218',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24216',
                'requestID': '60729081923267625',
                'time': '2020-07-06T12:45:34.897898440Z'
            }, {
                'type': 'ORDER_CANCEL',
                'orderID': '24218',
                'replacedByOrderID': '24222',
                'reason': 'CLIENT_REQUEST_REPLACED',
                'id': '24221',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24221',
                'requestID': '42714898585905152',
                'time': '2020-07-07T03:00:35.180556979Z'
            }, {
                'type': 'STOP_LOSS_ORDER',
                'tradeID': '24217',
                'clientTradeID': '246849601',
                'timeInForce': 'GTC',
                'triggerCondition': 'DEFAULT',
                'price': '107.410',
                'reason': 'REPLACEMENT',
                'replacesOrderID': '24218',
                'cancellingTransactionID': '24221',
                'id': '24222',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24221',
                'requestID': '42714898585905152',
                'time': '2020-07-07T03:00:35.180556979Z'
            }, {
                # STOPLOSS_ORDER による自動ポジション解消
                'type': 'ORDER_FILL',
                'orderID': '24222',
                'instrument': 'USD_JPY',
                'units': '10000',
                'requestedUnits': '10000',
                'price': '107.410',
                'pl': '730.0000',
                'financing': '0.0000',
                'commission': '0.0000',
                'accountBalance': '3165830.6320',
                'gainQuoteHomeConversionFactor': '1',
                'lossQuoteHomeConversionFactor': '1',
                'guaranteedExecutionFee': '0.0000',
                'halfSpreadCost': '20.0000',
                'fullVWAP': '107.410',
                'reason': 'STOP_LOSS_ORDER',
                'tradesClosed': [{
                    'tradeID': '24217',
                    'clientTradeID': '246849601',
                    'units': '10000',
                    'realizedPL': '730.0000',
                    'financing': '0.0000',
                    'price': '107.410',
                    'guaranteedExecutionFee': '0.0000',
                    'halfSpreadCost': '20.0000'
                }],
                'fullPrice': {
                    'closeoutBid': '107.401',
                    'closeoutAsk': '107.414',
                    'timestamp': '2020-07-07T03:53:08.182928102Z',
                    'bids': [{'price': '107.406', 'liquidity': '250000'}],
                    'asks': [{'price': '107.410', 'liquidity': '250000'}]
                },
                'id': '24223',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24223',
                'time': '2020-07-07T03:53:08.182928102Z'
            }, {
                'type': 'MARKET_ORDER',
                'instrument': 'USD_JPY',
                'units': '10000',
                'timeInForce': 'FOK',
                'positionFill': 'DEFAULT',
                'stopLossOnFill': {'price': '107.246', 'timeInForce': 'GTC'},
                'reason': 'CLIENT_ORDER',
                'id': '24224',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24224',
                'requestID': '78743756005341972',
                'time': '2020-07-07T07:00:35.043355625Z'
            }, {
                'type': 'ORDER_FILL',
                'orderID': '24224',
                'instrument': 'USD_JPY',
                'units': '10000',
                'requestedUnits': '10000',
                'price': '107.579',
                'pl': '0.0000',
                'financing': '0.0000',
                'commission': '0.0000',
                'accountBalance': '3165830.6320',
                'gainQuoteHomeConversionFactor': '1',
                'lossQuoteHomeConversionFactor': '1',
                'guaranteedExecutionFee': '0.0000',
                'halfSpreadCost': '20.0000',
                'fullVWAP': '107.579',
                'reason': 'MARKET_ORDER',
                'tradeOpened': {
                    'price': '107.579',
                    'tradeID': '24225',
                    'units': '10000',
                    'guaranteedExecutionFee': '0.0000',
                    'halfSpreadCost': '20.0000',
                    'initialMarginRequired': '43030.8000'
                },
                'fullPrice': {
                    'closeoutBid': '107.571',
                    'closeoutAsk': '107.583',
                    'timestamp': '2020-07-07T07:00:34.635171292Z',
                    'bids': [{'price': '107.575', 'liquidity': '250000'}],
                    'asks': [{'price': '107.579', 'liquidity': '250000'}]
                },
                'id': '24225',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24224',
                'requestID': '78743756005341972',
                'time': '2020-07-07T07:00:35.043355625Z'
            }, {
                'type': 'STOP_LOSS_ORDER',
                'tradeID': '24225',
                'timeInForce': 'GTC',
                'triggerCondition': 'DEFAULT',
                'price': '107.246',
                'reason': 'ON_FILL',
                'id': '24226',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24224',
                'requestID': '78743756005341972',
                'time': '2020-07-07T07:00:35.043355625Z'
            }, {
                'type': 'ORDER_CANCEL',
                'orderID': '24186',
                'replacedByOrderID': '24229',
                'reason': 'CLIENT_REQUEST_REPLACED',
                'id': '24228',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24228',
                'requestID': '42714989179604071',
                'time': '2020-07-07T09:00:34.885185417Z'
            }, {
                'type': 'STOP_LOSS_ORDER',
                'tradeID': '24130',
                'clientTradeID': '246490102',
                'timeInForce': 'GTC',
                'triggerCondition': 'DEFAULT',
                'price': '1.12632',
                'reason': 'REPLACEMENT',
                'replacesOrderID': '24186',
                'cancellingTransactionID': '24228',
                'id': '24229',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24228',
                'requestID': '42714989179604071',
                'time': '2020-07-07T09:00:34.885185417Z'
            }, {
                'type': 'ORDER_FILL',
                'orderID': '24229',
                'instrument': 'EUR_USD',
                'units': '-10000',
                'requestedUnits': '-10000',
                'price': '1.12632',
                'pl': '-679.8544',
                'financing': '0.0000',
                'commission': '0.0000',
                'accountBalance': '3165150.7776',
                'gainQuoteHomeConversionFactor': '107.482604',
                'lossQuoteHomeConversionFactor': '107.913396',
                'guaranteedExecutionFee': '0.0000',
                'halfSpreadCost': '26.9245',
                'fullVWAP': '1.12632',
                'reason': 'STOP_LOSS_ORDER',
                'tradesClosed': [{
                    'tradeID': '24130',
                    'clientTradeID': '246490102',
                    'units': '-10000',
                    'realizedPL': '-679.8544',
                    'financing': '0.0000',
                    'price': '1.12632',
                    'guaranteedExecutionFee': '0.0000',
                    'halfSpreadCost': '26.9245'
                }],
                'fullPrice': {
                    'closeoutBid': '1.12628',
                    'closeoutAsk': '1.12642',
                    'timestamp': '2020-07-07T09:02:00.638978156Z',
                    'bids': [{'price': '1.12632', 'liquidity': '250000'}],
                    'asks': [{'price': '1.12637', 'liquidity': '250000'}]
                },
                'id': '24230',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24230',
                'time': '2020-07-07T09:02:00.638978156Z'
            }, {
                'type': 'MARKET_ORDER',
                'instrument': 'USD_JPY',
                'units': '-10000',
                'timeInForce': 'FOK',
                'positionFill': 'REDUCE_ONLY',
                'reason': 'TRADE_CLOSE',
                'tradeClose': {
                    'units': 'ALL',
                    'tradeID': '24225',
                    'clientTradeID': '246967877'
                },
                'id': '24231',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24231',
                'requestID': '24700605771755676',
                'time': '2020-07-07T10:00:35.094414243Z'
            }, {
                'type': 'ORDER_FILL',
                'orderID': '24231',
                'instrument': 'USD_JPY',
                'units': '-10000',
                'requestedUnits': '-10000',
                'price': '107.733',
                'pl': '1540.0000',
                'financing': '0.0000',
                'commission': '0.0000',
                'accountBalance': '3166690.7776',
                'gainQuoteHomeConversionFactor': '1',
                'lossQuoteHomeConversionFactor': '1',
                'guaranteedExecutionFee': '0.0000',
                'halfSpreadCost': '20.0000',
                'fullVWAP': '107.733',
                'reason': 'MARKET_ORDER_TRADE_CLOSE',
                'tradesClosed': [{
                    'tradeID': '24225',
                    'clientTradeID': '246967877',
                    'units': '-10000',
                    'realizedPL': '1540.0000',
                    'financing': '0.0000',
                    'price': '107.733',
                    'guaranteedExecutionFee': '0.0000',
                    'halfSpreadCost': '20.0000'
                }],
                'fullPrice': {
                    'closeoutBid': '107.729',
                    'closeoutAsk': '107.741',
                    'timestamp': '2020-07-07T10:00:34.829499170Z',
                    'bids': [{'price': '107.733', 'liquidity': '250000'}],
                    'asks': [{'price': '107.737', 'liquidity': '250000'}]
                },
                'id': '24232',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24231',
                'requestID': '24700605771755676',
                'time': '2020-07-07T10:00:35.094414243Z'
            }, {
                'type': 'ORDER_CANCEL',
                'orderID': '24226',
                'reason': 'LINKED_TRADE_CLOSED',
                'closedTradeID': '24225',
                'tradeCloseTransactionID': '24232',
                'id': '24233',
                'accountID': '101-009-8694527-001',
                'userID': 8694527,
                'batchID': '24231',
                'requestID': '24700605771755676',
                'time': '2020-07-07T10:00:35.094414243Z'
            }
        ]
    }


@pytest.fixture(scope='session')
def no_pl_transactions():
    return [
        {
            'type': 'STOP_LOSS_ORDER',
            'tradeID': '24225',
            'timeInForce': 'GTC',
            'triggerCondition': 'DEFAULT',
            'price': '107.246',
            'reason': 'ON_FILL',
            'id': '24226',
            'accountID': '101-009-8694527-001',
            'userID': 8694527,
            'batchID': '24224',
            'requestID': '78743756005341972',
            'time': '2020-07-07T07:00:35.043355625Z'
        }, {
            'type': 'ORDER_CANCEL',
            'orderID': '24186',
            'replacedByOrderID': '24229',
            'reason': 'CLIENT_REQUEST_REPLACED',
            'id': '24228',
            'accountID': '101-009-8694527-001',
            'userID': 8694527,
            'batchID': '24228',
            'requestID': '42714989179604071',
            'time': '2020-07-07T09:00:34.885185417Z'
        }, {
            'type': 'STOP_LOSS_ORDER',
            'tradeID': '24130',
            'clientTradeID': '246490102',
            'timeInForce': 'GTC',
            'triggerCondition': 'DEFAULT',
            'price': '1.12632',
            'reason': 'REPLACEMENT',
            'replacesOrderID': '24186',
            'cancellingTransactionID': '24228',
            'id': '24229',
            'accountID': '101-009-8694527-001',
            'userID': 8694527,
            'batchID': '24228',
            'requestID': '42714989179604071',
            'time': '2020-07-07T09:00:34.885185417Z'
        }
    ]


# INFO: past_transactions と一緒に使いやすい： time が一致するデータになっている
@pytest.fixture(scope='session')
def past_usd_candles() -> List[Dict[str, Union[float, str, int]]]:
    return [
        {'close': 107.662, 'high': 107.678, 'low': 107.574, 'open': 107.59, 'time': '2020-07-06 00:00:00', 'volume': 2705},
        {'close': 107.722, 'high': 107.742, 'low': 107.66, 'open': 107.661, 'time': '2020-07-06 01:00:00', 'volume': 3089},
        {'close': 107.696, 'high': 107.773, 'low': 107.682, 'open': 107.721, 'time': '2020-07-06 02:00:00', 'volume': 1685},
        {'close': 107.688, 'high': 107.724, 'low': 107.662, 'open': 107.697, 'time': '2020-07-06 03:00:00', 'volume': 1729},
        {'close': 107.65, 'high': 107.72, 'low': 107.646, 'open': 107.689, 'time': '2020-07-06 04:00:00', 'volume': 1188},
        {'close': 107.69, 'high': 107.707, 'low': 107.65, 'open': 107.651, 'time': '2020-07-06 05:00:00', 'volume': 1548},
        {'close': 107.62, 'high': 107.706, 'low': 107.602, 'open': 107.688, 'time': '2020-07-06 06:00:00', 'volume': 2095},
        {'close': 107.594, 'high': 107.632, 'low': 107.55, 'open': 107.621, 'time': '2020-07-06 07:00:00', 'volume': 2736},
        {'close': 107.574, 'high': 107.612, 'low': 107.544, 'open': 107.592, 'time': '2020-07-06 08:00:00', 'volume': 1958},
        {'close': 107.541, 'high': 107.586, 'low': 107.523, 'open': 107.573, 'time': '2020-07-06 09:00:00', 'volume': 2129},
        {'close': 107.565, 'high': 107.598, 'low': 107.537, 'open': 107.54, 'time': '2020-07-06 10:00:00', 'volume': 1953},
        {'close': 107.526, 'high': 107.564, 'low': 107.498, 'open': 107.564, 'time': '2020-07-06 11:00:00', 'volume': 2019},
        {'close': 107.493, 'high': 107.54, 'low': 107.457, 'open': 107.525, 'time': '2020-07-06 12:00:00', 'volume': 2174},
        {'close': 107.538, 'high': 107.538, 'low': 107.438, 'open': 107.494, 'time': '2020-07-06 13:00:00', 'volume': 2952},
        {'close': 107.462, 'high': 107.596, 'low': 107.448, 'open': 107.535, 'time': '2020-07-06 14:00:00', 'volume': 4547},
        {'close': 107.504, 'high': 107.52, 'low': 107.45, 'open': 107.464, 'time': '2020-07-06 15:00:00', 'volume': 2554},
        {'close': 107.439, 'high': 107.506, 'low': 107.438, 'open': 107.502, 'time': '2020-07-06 16:00:00', 'volume': 1230},
        {'close': 107.406, 'high': 107.442, 'low': 107.378, 'open': 107.437, 'time': '2020-07-06 17:00:00', 'volume': 1068},
        {'close': 107.293, 'high': 107.406, 'low': 107.258, 'open': 107.405, 'time': '2020-07-06 18:00:00', 'volume': 1417},
        {'close': 107.378, 'high': 107.381, 'low': 107.287, 'open': 107.292, 'time': '2020-07-06 19:00:00', 'volume': 1483},
        {'close': 107.388, 'high': 107.407, 'low': 107.358, 'open': 107.376, 'time': '2020-07-06 20:00:00', 'volume': 837},
        {'close': 107.372, 'high': 107.379, 'low': 107.352, 'open': 107.37, 'time': '2020-07-06 21:00:00', 'volume': 39},
        {'close': 107.376, 'high': 107.4, 'low': 107.353, 'open': 107.374, 'time': '2020-07-06 22:00:00', 'volume': 395},
        {'close': 107.36, 'high': 107.38, 'low': 107.342, 'open': 107.374, 'time': '2020-07-06 23:00:00', 'volume': 430},
        {'close': 107.288, 'high': 107.37, 'low': 107.26, 'open': 107.358, 'time': '2020-07-07 00:00:00', 'volume': 3141},
        {'close': 107.352, 'high': 107.355, 'low': 107.246, 'open': 107.29, 'time': '2020-07-07 01:00:00', 'volume': 2349},
        {'close': 107.396, 'high': 107.41, 'low': 107.343, 'open': 107.353, 'time': '2020-07-07 02:00:00', 'volume': 2283},
        {'close': 107.397, 'high': 107.412, 'low': 107.357, 'open': 107.396, 'time': '2020-07-07 03:00:00', 'volume': 1556},
        {'close': 107.364, 'high': 107.396, 'low': 107.353, 'open': 107.396, 'time': '2020-07-07 04:00:00', 'volume': 1393},
        {'close': 107.526, 'high': 107.532, 'low': 107.361, 'open': 107.363, 'time': '2020-07-07 05:00:00', 'volume': 2234},
        {'close': 107.576, 'high': 107.579, 'low': 107.502, 'open': 107.524, 'time': '2020-07-07 06:00:00', 'volume': 2420},
        {'close': 107.632, 'high': 107.638, 'low': 107.535, 'open': 107.578, 'time': '2020-07-07 07:00:00', 'volume': 2883},
        {'close': 107.686, 'high': 107.692, 'low': 107.602, 'open': 107.634, 'time': '2020-07-07 08:00:00', 'volume': 3070},
        {'close': 107.736, 'high': 107.792, 'low': 107.682, 'open': 107.686, 'time': '2020-07-07 09:00:00', 'volume': 3117},
        {'close': 107.707, 'high': 107.742, 'low': 107.665, 'open': 107.736, 'time': '2020-07-07 10:00:00', 'volume': 2732},
        {'close': 107.714, 'high': 107.718, 'low': 107.672, 'open': 107.708, 'time': '2020-07-07 11:00:00', 'volume': 2042},
        {'close': 107.611, 'high': 107.718, 'low': 107.599, 'open': 107.715, 'time': '2020-07-07 12:00:00', 'volume': 1507},
        {'close': 107.658, 'high': 107.674, 'low': 107.599, 'open': 107.612, 'time': '2020-07-07 13:00:00', 'volume': 3058},
        {'close': 107.55, 'high': 107.658, 'low': 107.498, 'open': 107.656, 'time': '2020-07-07 14:00:00', 'volume': 5027},
        {'close': 107.532, 'high': 107.592, 'low': 107.511, 'open': 107.55, 'time': '2020-07-07 15:00:00', 'volume': 3091},
        {'close': 107.516, 'high': 107.535, 'low': 107.498, 'open': 107.534, 'time': '2020-07-07 16:00:00', 'volume': 1770},
        {'close': 107.542, 'high': 107.552, 'low': 107.505, 'open': 107.518, 'time': '2020-07-07 17:00:00', 'volume': 1547},
        {'close': 107.52, 'high': 107.568, 'low': 107.504, 'open': 107.541, 'time': '2020-07-07 18:00:00', 'volume': 1668},
        {'close': 107.561, 'high': 107.567, 'low': 107.512, 'open': 107.519, 'time': '2020-07-07 19:00:00', 'volume': 1324},
        {'close': 107.52, 'high': 107.562, 'low': 107.516, 'open': 107.56, 'time': '2020-07-07 20:00:00', 'volume': 805},
        {'close': 107.551, 'high': 107.599, 'low': 107.523, 'open': 107.552, 'time': '2020-07-07 21:00:00', 'volume': 136},
        {'close': 107.56, 'high': 107.566, 'low': 107.528, 'open': 107.547, 'time': '2020-07-07 22:00:00', 'volume': 182},
        {'close': 107.574, 'high': 107.606, 'low': 107.562, 'open': 107.562, 'time': '2020-07-07 23:00:00', 'volume': 419},
        {'close': 107.7, 'high': 107.708, 'low': 107.572, 'open': 107.573, 'time': '2020-07-08 00:00:00', 'volume': 1730},
        {'close': 107.668, 'high': 107.71, 'low': 107.642, 'open': 107.702, 'time': '2020-07-08 01:00:00', 'volume': 1212},
        {'close': 107.629, 'high': 107.675, 'low': 107.627, 'open': 107.669, 'time': '2020-07-08 02:00:00', 'volume': 954},
        {'close': 107.618, 'high': 107.642, 'low': 107.608, 'open': 107.63, 'time': '2020-07-08 03:00:00', 'volume': 819},
        {'close': 107.522, 'high': 107.621, 'low': 107.512, 'open': 107.62, 'time': '2020-07-08 04:00:00', 'volume': 990},
        {'close': 107.568, 'high': 107.57, 'low': 107.518, 'open': 107.523, 'time': '2020-07-08 05:00:00', 'volume': 895},
        {'close': 107.544, 'high': 107.57, 'low': 107.516, 'open': 107.566, 'time': '2020-07-08 06:00:00', 'volume': 1583},
        {'close': 107.482, 'high': 107.545, 'low': 107.428, 'open': 107.545, 'time': '2020-07-08 07:00:00', 'volume': 2347},
        {'close': 107.576, 'high': 107.584, 'low': 107.473, 'open': 107.48, 'time': '2020-07-08 08:00:00', 'volume': 2259},
        {'close': 107.566, 'high': 107.604, 'low': 107.544, 'open': 107.575, 'time': '2020-07-08 09:00:00', 'volume': 2423},
        {'close': 107.562, 'high': 107.592, 'low': 107.529, 'open': 107.567, 'time': '2020-07-08 10:00:00', 'volume': 1058},
        {'close': 107.516, 'high': 107.576, 'low': 107.5, 'open': 107.564, 'time': '2020-07-08 11:00:00', 'volume': 1286}
    ]


@pytest.fixture(scope='session')
def d1_stoc_dummy():
    return [
        {'open': 140.091, 'high': 140.829, 'low': 139.354, 'close': 140.789, 'long_stoD': None, 'long_stoSD': None, 'stoD_over_stoSD': False},
        {'open': 140.797, 'high': 140.797, 'low': 140.797, 'close': 140.797, 'long_stoD': None, 'long_stoSD': None, 'stoD_over_stoSD': False},
        {'open': 140.797, 'high': 141.364, 'low': 139.791, 'close': 140.761, 'long_stoD': None, 'long_stoSD': None, 'stoD_over_stoSD': False},
        {'open': 140.726, 'high': 141.128, 'low': 139.522, 'close': 139.65, 'long_stoD': None, 'long_stoSD': None, 'stoD_over_stoSD': False},
        {'open': 139.661, 'high': 140.432, 'low': 139.09, 'close': 140.374, 'long_stoD': None, 'long_stoSD': None, 'stoD_over_stoSD': False},
        {'open': 140.352, 'high': 140.745, 'low': 138.878, 'close': 139.596, 'long_stoD': None, 'long_stoSD': None, 'stoD_over_stoSD': False},
        {'open': 139.588, 'high': 139.804, 'low': 139.032, 'close': 139.412, 'long_stoD': 35.60880243346937, 'long_stoSD': None, 'stoD_over_stoSD': False},
        {'open': 139.346, 'high': 140.259, 'low': 139.335, 'close': 140.125, 'long_stoD': 35.26141652513394, 'long_stoSD': None, 'stoD_over_stoSD': False},
        {'open': 140.11, 'high': 140.538, 'low': 139.472, 'close': 140.136, 'long_stoD': 48.0944455656036, 'long_stoSD': 39.65488817473564, 'stoD_over_stoSD': True},
        {'open': 140.098, 'high': 140.514, 'low': 139.964, 'close': 140.383, 'long_stoD': 67.80455077466358, 'long_stoSD': 50.38680428846704, 'stoD_over_stoSD': True},
        {'open': 140.427, 'high': 140.69, 'low': 139.61, 'close': 139.814, 'long_stoD': 65.05222981679334, 'long_stoSD': 60.31707538568685, 'stoD_over_stoSD': True},
        {'open': 139.846, 'high': 140.168, 'low': 139.65, 'close': 139.988, 'long_stoD': 58.65591550549808, 'long_stoSD': 63.83756536565168, 'stoD_over_stoSD': False},
        {'open': 139.951, 'high': 140.24, 'low': 139.848, 'close': 139.872, 'long_stoD': 42.73262125444224, 'long_stoSD': 55.48025552557791, 'stoD_over_stoSD': False},
        {'open': 139.9, 'high': 140.754, 'low': 139.854, 'close': 140.636, 'long_stoD': 56.90597303334318, 'long_stoSD': 52.76483659776119, 'stoD_over_stoSD': True},
        {'open': 140.674, 'high': 140.699, 'low': 139.878, 'close': 140.095, 'long_stoD': 54.97371402543836, 'long_stoSD': 51.53743610440795, 'stoD_over_stoSD': True},
        {'open': 140.069, 'high': 140.534, 'low': 139.496, 'close': 140.042, 'long_stoD': 58.494215111862125, 'long_stoSD': 56.79130072354791, 'stoD_over_stoSD': True},
        {'open': 140.079, 'high': 140.212, 'low': 139.423, 'close': 139.578, 'long_stoD': 32.4809033547487, 'long_stoSD': 48.64961083068309, 'stoD_over_stoSD': False},
        {'open': 139.799, 'high': 140.49, 'low': 139.373, 'close': 140.192, 'long_stoD': 38.117485575328566, 'long_stoSD': 43.03086801397982, 'stoD_over_stoSD': False},
        {'open': 140.172, 'high': 140.59, 'low': 139.948, 'close': 140.047, 'long_stoD': 40.59326452169562, 'long_stoSD': 37.06388448392432, 'stoD_over_stoSD': True},
        {'open': 140.126, 'high': 140.261, 'low': 139.446, 'close': 139.842, 'long_stoD': 49.55726705612307, 'long_stoSD': 42.75600571771577, 'stoD_over_stoSD': True},
        {'open': 139.847, 'high': 139.89, 'low': 139.404, 'close': 139.65, 'long_stoD': 37.37594567987601, 'long_stoSD': 42.508825752564924, 'stoD_over_stoSD': False},
        {'open': 139.626, 'high': 140.465, 'low': 139.624, 'close': 140.378, 'long_stoD': 47.95946316077828, 'long_stoSD': 44.96422529892581, 'stoD_over_stoSD': True},
        {'open': 140.613, 'high': 141.576, 'low': 140.366, 'close': 140.768, 'long_stoD': 56.046755272275895, 'long_stoSD': 47.12738803764342, 'stoD_over_stoSD': True},
        {'open': 140.782, 'high': 140.937, 'low': 140.112, 'close': 140.301, 'long_stoD': 62.225906976720296, 'long_stoSD': 55.41070846992485, 'stoD_over_stoSD': True},
        {'open': 140.306, 'high': 140.49, 'low': 139.683, 'close': 140.36, 'long_stoD': 49.37077961939868, 'long_stoSD': 55.881147289464984, 'stoD_over_stoSD': False},
        {'open': 140.328, 'high': 140.928, 'low': 139.978, 'close': 140.194, 'long_stoD': 38.17129839285901, 'long_stoSD': 49.92266166299268, 'stoD_over_stoSD': False},
        {'open': 140.231, 'high': 140.515, 'low': 139.325, 'close': 139.443, 'long_stoD': 26.152555750956093, 'long_stoSD': 37.89821125440461, 'stoD_over_stoSD': False},
        {'open': 139.735, 'high': 140.627, 'low': 139.608, 'close': 140.516, 'long_stoD': 36.10876965922787, 'long_stoSD': 33.477541267681005, 'stoD_over_stoSD': True},
        {'open': 140.54, 'high': 140.904, 'low': 139.988, 'close': 140.304, 'long_stoD': 46.73282581759241, 'long_stoSD': 36.331383742592145, 'stoD_over_stoSD': True},
        {'open': 140.289, 'high': 141.543, 'low': 140.05, 'close': 141.459, 'long_stoD': 77.05638905509113, 'long_stoSD': 53.29932817730383, 'stoD_over_stoSD': True},
        {'open': 141.568, 'high': 141.858, 'low': 141.254, 'close': 141.395, 'long_stoD': 79.66902386370715, 'long_stoSD': 67.81941291213026, 'stoD_over_stoSD': True},
        {'open': 141.41, 'high': 141.744, 'low': 141.116, 'close': 141.643, 'long_stoD': 89.45950929611377, 'long_stoSD': 82.06164073830404, 'stoD_over_stoSD': True},
        {'open': 141.402, 'high': 141.822, 'low': 140.947, 'close': 141.038, 'long_stoD': 76.10515206014638, 'long_stoSD': 81.74456173998912, 'stoD_over_stoSD': False},
        {'open': 141.047, 'high': 141.716, 'low': 140.924, 'close': 141.184, 'long_stoD': 69.77180533427274, 'long_stoSD': 78.44548889684432, 'stoD_over_stoSD': False},
        {'open': 141.169, 'high': 142.794, 'low': 140.838, 'close': 142.665, 'long_stoD': 70.75862651127773, 'long_stoSD': 72.21186130189898, 'stoD_over_stoSD': False},
        {'open': 142.659, 'high': 143.252, 'low': 142.615, 'close': 143.124, 'long_stoD': 83.60791475410333, 'long_stoSD': 74.71278219988461, 'stoD_over_stoSD': True},
        {'open': 143.108, 'high': 143.158, 'low': 142.371, 'close': 142.661, 'long_stoD': 87.87343936105454, 'long_stoSD': 80.74666020881187, 'stoD_over_stoSD': True},
        {'open': 142.661, 'high': 143.114, 'low': 142.566, 'close': 142.662, 'long_stoD': 81.92488262910778, 'long_stoSD': 84.4687455814219, 'stoD_over_stoSD': False},
        {'open': 142.676, 'high': 143.67, 'low': 142.631, 'close': 143.043, 'long_stoD': 76.31240667668375, 'long_stoSD': 82.03690955561537, 'stoD_over_stoSD': False},
        {'open': 143.038, 'high': 143.38, 'low': 142.562, 'close': 143.245, 'long_stoD': 73.56731076346381, 'long_stoSD': 77.26820002308513, 'stoD_over_stoSD': False},
        {'open': 143.26, 'high': 144.156, 'low': 142.482, 'close': 143.944, 'long_stoD': 77.75531460349714, 'long_stoSD': 75.87834401454825, 'stoD_over_stoSD': True},
        {'open': 145.39, 'high': 147.958, 'low': 143.87, 'close': 145.8, 'long_stoD': 71.99914902426684, 'long_stoSD': 74.44059146374262, 'stoD_over_stoSD': False},
        {'open': 145.808, 'high': 146.814, 'low': 145.785, 'close': 146.08, 'long_stoD': 71.47327204560897, 'long_stoSD': 73.74257855779099, 'stoD_over_stoSD': False},
        {'open': 146.059, 'high': 146.161, 'low': 143.481, 'close': 143.766, 'long_stoD': 49.914779644509544, 'long_stoSD': 64.46240023812847, 'stoD_over_stoSD': False},
        {'open': 143.747, 'high': 143.866, 'low': 143.076, 'close': 143.31, 'long_stoD': 34.75773070367676, 'long_stoSD': 52.04859413126511, 'stoD_over_stoSD': False},
        {'open': 143.337, 'high': 143.87, 'low': 141.984, 'close': 142.247, 'long_stoD': 14.323569491006822, 'long_stoSD': 32.998693279731064, 'stoD_over_stoSD': False},
        {'open': 142.278, 'high': 143.057, 'low': 142.09, 'close': 142.279, 'long_stoD': 8.543532277362056, 'long_stoSD': 19.208277490681905, 'stoD_over_stoSD': False},
        {'open': 142.306, 'high': 142.541, 'low': 141.17, 'close': 141.492, 'long_stoD': 5.653894601325071, 'long_stoSD': 9.506998789898008, 'stoD_over_stoSD': False},
        {'open': 141.468, 'high': 141.866, 'low': 141.251, 'close': 141.562, 'long_stoD': 9.02593062574388, 'long_stoSD': 7.741119168143695, 'stoD_over_stoSD': True},
        {'open': 141.55, 'high': 142.73, 'low': 141.55, 'close': 142.496, 'long_stoD': 23.36041417761898, 'long_stoSD': 12.680079801562671, 'stoD_over_stoSD': True},
        {'open': 142.411, 'high': 143.653, 'low': 142.047, 'close': 143.295, 'long_stoD': 49.73719564644565, 'long_stoSD': 27.374513483269528, 'stoD_over_stoSD': True},
        {'open': 143.32, 'high': 143.43, 'low': 142.598, 'close': 142.772, 'long_stoD': 66.40393192225672, 'long_stoSD': 46.50051391544047, 'stoD_over_stoSD': True},
        {'open': 142.8, 'high': 144.368, 'low': 142.436, 'close': 144.117, 'long_stoD': 80.68268998734756, 'long_stoSD': 65.60793918534999, 'stoD_over_stoSD': True},
        {'open': 144.107, 'high': 144.212, 'low': 142.272, 'close': 142.618, 'long_stoD': 64.78844398560257, 'long_stoSD': 70.62502196506897, 'stoD_over_stoSD': False},
        {'open': 142.636, 'high': 142.786, 'low': 141.003, 'close': 141.39, 'long_stoD': 47.11578251763523, 'long_stoSD': 64.19563883019514, 'stoD_over_stoSD': False},
        {'open': 141.196, 'high': 142.79, 'low': 140.838, 'close': 142.737, 'long_stoD': 34.39866541361861, 'long_stoSD': 48.76763063895214, 'stoD_over_stoSD': False},
        {'open': 142.718, 'high': 143.296, 'low': 142.024, 'close': 142.318, 'long_stoD': 35.74104084848352, 'long_stoSD': 39.08516292657912, 'stoD_over_stoSD': False},
        {'open': 142.359, 'high': 143.11, 'low': 141.127, 'close': 142.92, 'long_stoD': 52.47651736631807, 'long_stoSD': 40.872074542806736, 'stoD_over_stoSD': True},
        {'open': 142.87, 'high': 143.46, 'low': 142.429, 'close': 143.126, 'long_stoD': 63.63171681544792, 'long_stoSD': 50.616425010083184, 'stoD_over_stoSD': True},
        {'open': 143.105, 'high': 143.497, 'low': 142.892, 'close': 143.022, 'long_stoD': 77.03498208127372, 'long_stoSD': 64.38107208767991, 'stoD_over_stoSD': True},
        {'open': 142.804, 'high': 142.97, 'low': 142.368, 'close': 142.77, 'long_stoD': 79.57422275434496, 'long_stoSD': 73.41364055035554, 'stoD_over_stoSD': True},
        {'open': 142.779, 'high': 143.437, 'low': 142.452, 'close': 143.212, 'long_stoD': 79.81190648853794, 'long_stoSD': 78.80703710805221, 'stoD_over_stoSD': True},
        {'open': 143.204, 'high': 143.39, 'low': 142.662, 'close': 143.298, 'long_stoD': 79.89112005571006, 'long_stoSD': 79.759083099531, 'stoD_over_stoSD': True},
        {'open': 143.29, 'high': 144.142, 'low': 143.228, 'close': 144.077, 'long_stoD': 88.89480985856653, 'long_stoSD': 82.86594546760486, 'stoD_over_stoSD': True},
        {'open': 144.072, 'high': 144.533, 'low': 143.278, 'close': 143.292, 'long_stoD': 73.79624328837184, 'long_stoSD': 80.86072440088283, 'stoD_over_stoSD': False},
        {'open': 143.046, 'high': 143.37, 'low': 142.806, 'close': 143.356, 'long_stoD': 60.81853376300396, 'long_stoSD': 74.50319563664748, 'stoD_over_stoSD': False},
        {'open': 143.36, 'high': 143.976, 'low': 142.868, 'close': 143.383, 'long_stoD': 41.55172661877399, 'long_stoSD': 58.72216789004997, 'stoD_over_stoSD': False},
        {'open': 143.376, 'high': 144.61, 'low': 143.31, 'close': 144.349, 'long_stoD': 55.83611559955171, 'long_stoSD': 52.73545866044325, 'stoD_over_stoSD': True},
        {'open': 144.336, 'high': 144.424, 'low': 143.212, 'close': 143.716, 'long_stoD': 58.1703840822478, 'long_stoSD': 51.8527421001912, 'stoD_over_stoSD': True},
        {'open': 143.711, 'high': 144.433, 'low': 142.722, 'close': 142.863, 'long_stoD': 47.81461003169287, 'long_stoSD': 53.940369904497494, 'stoD_over_stoSD': False},
        {'open': 142.484, 'high': 142.748, 'low': 142.06, 'close': 142.194, 'long_stoD': 21.055527093270157, 'long_stoSD': 42.34684040240364, 'stoD_over_stoSD': False},
        {'open': 142.185, 'high': 142.458, 'low': 141.484, 'close': 142.194, 'long_stoD': 11.811951408516478, 'long_stoSD': 26.894029511159868, 'stoD_over_stoSD': False},
        {'open': 142.189, 'high': 142.352, 'low': 141.714, 'close': 141.96, 'long_stoD': 14.702899551428267, 'long_stoSD': 15.856792684404995, 'stoD_over_stoSD': False},
        {'open': 141.953, 'high': 142.712, 'low': 141.265, 'close': 142.652, 'long_stoD': 27.545120783355546, 'long_stoSD': 18.019990581100128, 'stoD_over_stoSD': True},
        {'open': 142.621, 'high': 143.29, 'low': 142.466, 'close': 143.099, 'long_stoD': 50.16351055295046, 'long_stoSD': 30.803843629244785, 'stoD_over_stoSD': True},
        {'open': 142.897, 'high': 143.112, 'low': 141.073, 'close': 141.263, 'long_stoD': 47.63986890657687, 'long_stoSD': 41.78283341429432, 'stoD_over_stoSD': True},
        {'open': 141.232, 'high': 142.846, 'low': 140.928, 'close': 142.731, 'long_stoD': 58.490552214394, 'long_stoSD': 52.09797722464048, 'stoD_over_stoSD': True},
        {'open': 142.709, 'high': 143.379, 'low': 142.228, 'close': 142.79, 'long_stoD': 53.62424921889207, 'long_stoSD': 53.25155677995434, 'stoD_over_stoSD': True},
        {'open': 142.782, 'high': 142.822, 'low': 142.094, 'close': 142.2, 'long_stoD': 68.06659755020009, 'long_stoSD': 60.06046632782874, 'stoD_over_stoSD': True},
        {'open': 142.186, 'high': 142.378, 'low': 141.409, 'close': 141.432, 'long_stoD': 49.47640418876634, 'long_stoSD': 57.05575031928618, 'stoD_over_stoSD': False},
        {'open': 141.419, 'high': 142.094, 'low': 141.246, 'close': 141.766, 'long_stoD': 35.550115599075, 'long_stoSD': 51.031039112680496, 'stoD_over_stoSD': False},
        {'open': 141.758, 'high': 142.464, 'low': 141.701, 'close': 142.198, 'long_stoD': 33.12837857353396, 'long_stoSD': 39.38496612045845, 'stoD_over_stoSD': False},
        {'open': 142.204, 'high': 142.889, 'low': 142.175, 'close': 142.674, 'long_stoD': 55.24542720013951, 'long_stoSD': 41.30797379091617, 'stoD_over_stoSD': True},
        {'open': 142.662, 'high': 143.478, 'low': 142.148, 'close': 143.23, 'long_stoD': 73.47834800343952, 'long_stoSD': 53.95071792570434, 'stoD_over_stoSD': True},
        {'open': 143.235, 'high': 143.409, 'low': 142.768, 'close': 143.221, 'long_stoD': 88.0962444489525, 'long_stoSD': 72.27333988417719, 'stoD_over_stoSD': True},
        {'open': 143.271, 'high': 143.374, 'low': 142.85, 'close': 142.898, 'long_stoD': 81.57842409548752, 'long_stoSD': 81.05100551595986, 'stoD_over_stoSD': True},
        {'open': 142.909, 'high': 143.234, 'low': 142.322, 'close': 142.81, 'long_stoD': 68.54027316260003, 'long_stoSD': 79.40498056901335, 'stoD_over_stoSD': False},
        {'open': 142.804, 'high': 144.17, 'low': 142.804, 'close': 143.906, 'long_stoD': 68.02625886113516, 'long_stoSD': 72.71498537307423, 'stoD_over_stoSD': False},
        {'open': 143.851, 'high': 144.609, 'low': 143.606, 'close': 144.432, 'long_stoD': 76.32621989294957, 'long_stoSD': 70.96425063889491, 'stoD_over_stoSD': True},
        {'open': 144.426, 'high': 144.961, 'low': 143.726, 'close': 144.576, 'long_stoD': 88.20512139072564, 'long_stoSD': 77.5192000482701, 'stoD_over_stoSD': True},
        {'open': 144.046, 'high': 144.627, 'low': 142.638, 'close': 143.162, 'long_stoD': 69.83399424030831, 'long_stoSD': 78.12177850799448, 'stoD_over_stoSD': False},
        {'open': 143.135, 'high': 143.649, 'low': 142.967, 'close': 143.312, 'long_stoD': 48.7518616929158, 'long_stoSD': 68.93032577464989, 'stoD_over_stoSD': False},
        {'open': 143.329, 'high': 143.726, 'low': 142.24, 'close': 142.438, 'long_stoD': 22.707060329709662, 'long_stoSD': 47.09763875431124, 'stoD_over_stoSD': False},
        {'open': 142.454, 'high': 142.554, 'low': 141.181, 'close': 141.208, 'long_stoD': 12.335075992207964, 'long_stoSD': 27.931332671611127, 'stoD_over_stoSD': False},
        {'open': 141.234, 'high': 141.411, 'low': 137.533, 'close': 138.533, 'long_stoD': 7.3624805725551115, 'long_stoSD': 14.134872298157562, 'stoD_over_stoSD': False},
        {'open': 139.017, 'high': 139.188, 'low': 137.16, 'close': 138.136, 'long_stoD': 9.891719489238065, 'long_stoSD': 9.863092018000364, 'stoD_over_stoSD': True},
        {'open': 138.123, 'high': 138.572, 'low': 136.946, 'close': 137.255, 'long_stoD': 11.172798292440866, 'long_stoSD': 9.475666118077998, 'stoD_over_stoSD': True},
        {'open': 137.221, 'high': 138.44, 'low': 137.049, 'close': 138.426, 'long_stoD': 15.27094851777573, 'long_stoSD': 12.111822099818204, 'stoD_over_stoSD': True},
        {'open': 138.432, 'high': 138.684, 'low': 137.38, 'close': 137.52, 'long_stoD': 14.601311807481741, 'long_stoSD': 13.68168620589943, 'stoD_over_stoSD': True},
        {'open': 137.514, 'high': 137.74, 'low': 136.442, 'close': 137.481, 'long_stoD': 25.69442230126508, 'long_stoSD': 18.522227542174168, 'stoD_over_stoSD': True}
    ]
