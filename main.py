import datetime
import json
import pandas as pd

from models.real_trader import RealTrader
from models.history_librarian import Librarian


# For AWS Lambda
def lambda_handler(_event, _context):
    trader = RealTrader(operation='live')
    if not trader.tradeable:
        msg = '1. lambda function is correctly finished, but now the market is closed.'
        return {
            'statusCode': 204,
            'body': json.dumps(msg)
        }

    trader.apply_trading_rule()
    msg = 'lambda function is correctly finished.'
    return {
        'statusCode': 200,
        'body': json.dumps(msg)
    }


# For tradehist of AWS Lambda
def api_handler(event, _context):
    # TODO: oandaとの通信失敗時などは、500 エラーレスポンスを返せるようにする
    # TODO: params不足の際は、422 エラーレスポンスを返せるようにする
    params = event['queryStringParameters']
    from_datetime = params['fromDatetime'] or (datetime.datetime.today() - datetime.timedelta(days=30))
    pare_name = params['pareName']

    libra = Librarian(instrument=pare_name)
    result = libra.serve_analysis_object(from_datetime)

    body = json.dumps({
        # HACK: Nan は json では認識できないので None に書き換えてから to_dict している
        #   to_json ならこの問題は起きないが、dumps と組み合わせると文字列になってしまうのでしない
        'history': result.where((pd.notnull(result)), None) \
                         .to_dict(orient='records')
    })
    headers = {
        # 'Access-Control-Allow-Origin': 'https://www.example.com',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'OPTIONS,GET',
        'Access-Control-Allow-Credentials': 'true'
    }
    print('lambda function is correctly finished.')
    return {
        'statusCode': 200,
        'headers': headers,
        'body': body
    }


# For local console
if __name__ == '__main__':
    # lambda_handler(None, None)

    DUMMY_EVENT = {
        'queryStringParameters': {
            'pareName': 'USD_JPY', 'fromDatetime': '2020-11-15T04:58:09.460556567Z'
        }
    }
    api_handler(DUMMY_EVENT, None)
