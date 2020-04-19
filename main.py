# from models import mailer
import json
from models.real_trader import RealTrader


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


# For local console
if __name__ == '__main__':
    lambda_handler(None, None)
