from models import analyzer, interval, mailer
from models.chart_watcher import FXBase
import models.chart_watcher as watcher

class Main():
    def __init__(self):
        self.gmailer   = mailer.GmailAPI()
        self.c_watcher = watcher.ChartWatcher()
        self.ana       = analyzer.Analyzer()

    def periodic_processes(self):
        result = self.c_watcher.reload_chart()
        if 'success' in result:
            print(result['success'])
            print(FXBase.get_candles().tail())
        else:
            print(result['error'])
            exit()

        if 'success' in self.ana.perform():
            result = self.ana.draw_chart()
        else:
            exit()

        if 'success' in result:
            if result['success']['alart_necessary']:
                print('ALART MAIL 送信')
                self.gmailer.send()
        else:
            print(result['error'])


if __name__ == '__main__':
    main = Main()
    main.periodic_processes()

    # 2回目以降の定期処理
    interval.periodically_exec(method=main.periodic_processes, span_minutes=5)
    interval.wait_until_killed(report_span_sec=20)
