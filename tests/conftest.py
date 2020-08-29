import pytest


@pytest.fixture()
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


@pytest.fixture()
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


# TODO:
#   この辺の記事によると、 dummy_stoploss_price はここではなく、各testメソッド内に記載して簡略化できそう
#   そうすれば、 dummy_stoploss_price というメソッドその物がいらなくなる
#   ただ、みんな何言ってるのかよくわからない
# https://qastack.jp/programming/18011902/pass-a-parameter-to-a-fixture-function
# https://docs.pytest.org/en/latest/example/parametrize.html#indirect-parametrization
# https://www.366service.com/jp/qa/665a767bf116ce225233c4b9ef915165
@pytest.fixture()
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


@pytest.fixture()
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
