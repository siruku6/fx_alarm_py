from models import interval, mailer
from models.trader import Trader
from models.oanda_py_client import FXBase
from models.oanda_py_client import OandaPyClient

# For AWS Lambda
def lambda_handler(event, context):
    # Real trade
    tr = trader.RealTrader(operation='live')
    result = tr.apply_trading_rule()
    return {
        'statusCode': 200,
        'body': json.dumps(result)
    }

# For local console
class Main():
    def __init__(self):
        # self.gmailer   = mailer.GmailAPI()
        self.client = OandaPyClient()

    def periodic_processes(self):
        result = self.client.reload_chart(days=2)
        if 'success' in result:
            print(result['success'])
            print(FXBase.get_candles().tail())
        else:
            print(result['error'])
            exit()

        tr = Trader()
        tr.auto_verify_trading_rule()
        result = tr.draw_chart()

        if 'success' in result:
            print(result['success'])
            if result['alart_necessary']:
                print('ALART MAIL 送信')
                # self.gmailer.send()
        else:
            print(result['error'])

if __name__ == '__main__':
    main = Main()
    main.periodic_processes()

    # 2回目以降の定期処理
    interval.periodically_exec(method=main.periodic_processes, span_minutes=5)
    interval.wait_until_killed(report_span_sec=20)
