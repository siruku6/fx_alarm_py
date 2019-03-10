from models import interval, mailer, trader
from models.chart_watcher import FXBase
import models.chart_watcher as watcher

class Main():
    def __init__(self):
        # self.gmailer   = mailer.GmailAPI()
        self.c_watcher = watcher.ChartWatcher()

    def periodic_processes(self):
        result = self.c_watcher.reload_chart(days=2)
        if 'success' in result:
            print(result['success'])
            print(FXBase.get_candles().tail())
        else:
            print(result['error'])
            exit()

        tr = trader.Trader()
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
