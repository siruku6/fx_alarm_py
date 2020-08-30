# from models import mailer
import json
from models.real_trader import RealTrader
from models.history_librarian import Librarian


# For AWS Lambda
def lambda_handler(event, context):
    tr = RealTrader(operation='live')
    if not tr.tradeable:
        msg = '1. lambda function is correctly finished, but now the market is closed.'
        return {
            'statusCode': 204,
            'body': json.dumps(msg)
        }

    tr.apply_trading_rule()
    msg = 'lambda function is correctly finished.'
    return {
        'statusCode': 200,
        'body': json.dumps(msg)
    }


# For tradehist of AWS Lambda
# TODO: Now, next lines are prototype of tradehist
def hist_handler(event, context):
    libra = Librarian(instrument='GBP_JPY')
    transactions = libra.request_massive_transactions()

    # TODO: oandaとの通信失敗時などは、500 エラーレスポンスを返せるようにする

    result = libra.merge_history_and_instruments(transactions, granularity='H1')
    msg = 'lambda function is correctly finished.'
    return {
        'statusCode': 200,
        'headers': {
            # 'Access-Control-Allow-Origin': 'https://www.example.com',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'OPTIONS,GET',
            'Access-Control-Allow-Credentials': 'true'
        },
        'body': result.to_json(orient='records')
    }


# For local console
if __name__ == '__main__':
    lambda_handler(None, None)
