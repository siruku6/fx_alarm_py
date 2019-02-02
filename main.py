import models.mail          as mail
import models.interval      as interval
import models.chart_watcher as watcher
import models.analyzer      as analyzer

class Main():
    def __init__(self):
        self.gmailer   = mail.GmailAPI()
        self.c_watcher = watcher.ChartWatcher()
        self.ana       = analyzer.Analyzer()

    def periodic_processes(self):
        result = self.c_watcher.request_chart()
        if 'success' in result:
            print(result['success'])
            print(watcher.FXBase.candles.tail())
        else:
            print(result['error'])
            exit()

        watcher.FXBase.candles['time_id']= watcher.FXBase.candles.index + 1
        result = self.ana.perform()
        num = len(watcher.FXBase.candles)
        if self.ana.jump_trendbreaks[-1] == num or self.ana.fall_trendbreaks[-1] == num:
            self.gmailer.send()

if __name__ == '__main__':
    main = Main()
    main.periodic_processes()

    # 2回目以降の定期処理
    timer = interval.MethodTimer(method=main.periodic_processes, span_minutes=5)
    timer.wait_until_killed(report_span_sec=20)
