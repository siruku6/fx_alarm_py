import datetime
import json
from typing import Dict
import pandas as pd

from models.real_trader import RealTrader
from models.history_librarian import Librarian


# For auto trader
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


# For tradehist
def api_handler(event: Dict[str, Dict], _context: Dict) -> Dict:
    # TODO: oandaとの通信失敗時などは、500 エラーレスポンスを返せるようにする
    params: Dict[str, str] = event['queryStringParameters']
    pare_name: str = params['pareName']
    from_str: str = params['from']
    to_str: str = params['to']

    requested_period: int = __period_between_from_to(from_str, to_str)
    if requested_period >= 60:
        msg: str = 'Maximum days between FROM and TO is 60 days. You requested {} days!'.format(requested_period)
        body: str = json.dumps({'message': msg})
        status: int = 400
    else:
        body: str = __drive_generating_tradehist(pare_name, from_str, to_str)
        status: int = 200

    headers: Dict[str, str] = {
        # 'Access-Control-Allow-Origin': 'https://www.example.com',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'OPTIONS,GET',
        'Access-Control-Allow-Credentials': 'true'
    }
    return {
        'statusCode': status,
        'headers': headers,
        'body': body
    }


def __drive_generating_tradehist(pare_name: str, from_str: str, to_str: str) -> str:
    libra: Librarian = Librarian(instrument=pare_name)
    tradehist: pd.DataFrame = libra.serve_analysis_object(from_str, to_str)
    result: str = json.dumps({
        # HACK: Nan は json では認識できないので None に書き換えてから to_dict している
        #   to_json ならこの問題は起きないが、dumps と組み合わせると文字列になってしまうのでしない
        'history': tradehist.where((pd.notnull(tradehist)), None) \
                            .to_dict(orient='records')
    })
    print('lambda function is correctly finished.')
    return result


def __period_between_from_to(from_str: str, to_str: str) -> int:
    start: datetime = datetime.datetime.fromisoformat(from_str[:26].rstrip('Z'))
    end: datetime = datetime.datetime.fromisoformat(to_str[:26].rstrip('Z'))
    result: int = (end - start).days
    return result


# For local console
if __name__ == '__main__':
    # lambda_handler(None, None)

    DUMMY_EVENT = {
        'queryStringParameters': {
            'pareName': 'USD_JPY',
            'from': '2020-12-30T04:58:09.460556567Z',
            'to': '2021-01-07T04:58:09.460556567Z'
        }
    }
    api_handler(DUMMY_EVENT, None)
