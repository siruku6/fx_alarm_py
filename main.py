# from models import mailer
import json
from models.trader import RealTrader


# For AWS Lambda
def lambda_handler(event, context):
    tr = RealTrader(operation='live')
    if not tr.tradeable:
        msg = 'lambda function is correctly finished, but now the market is closed.'
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

# class Main():
#     def __init__(self):
#         # self.gmailer   = mailer.GmailAPI()
#         self.client = OandaPyClient()
#
#     def periodic_processes(self):
#         result = self.client.reload_chart(days=2)
#         if 'success' in result:
#             print(result['success'])
#             print(FXBase.get_candles().tail())
#         else:
#             print(result['error'])
#             exit()
#
#         tr = Trader()
#         tr.auto_verify_trading_rule()
#         result = tr.draw_chart()
#
#         if 'success' in result:
#             print(result['success'])
#             if result['alart_necessary']:
#                 print('ALART MAIL 送信')
#                 # self.gmailer.send()
#         else:
#             print(result['error'])
#
# if __name__ == '__main__':
#     main = Main()
#     main.periodic_processes()
