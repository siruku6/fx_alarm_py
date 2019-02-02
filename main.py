import models.mail          as mail
import models.interval      as intrvl
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
    timer = intrvl.MethodTimer(span_minutes=5, method=main.periodic_processes)
    while True:
        intrvl.schedule.run_pending()
        next_time = intrvl.schedule.next_run().strftime('%Y-%m-%d %H:%M')
        print('')
        print(
            'next execution:', str(next_time),
            'intrvl:',       str(intrvl.schedule.idle_seconds())
        )
        intrvl.time.sleep(20)
        print(watcher.FXBase.candles.tail())
