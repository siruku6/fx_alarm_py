import models.mail          as mail
import models.interval      as intrvl
import models.chart_watcher as watcher
import models.analyzer      as analyzer

if __name__ == '__main__':
    gmail_test = mail.GmailAPI()
    print(type(gmail_test))

    # 1回目のリクエスト
    c_watcher = watcher.ChartWatcher()
    result    = c_watcher.request_chart()
    if 'success' in result:
        print(result['success'])
        print(watcher.FXBase.candles.tail())
    else:
        print(result['error'])
        exit()

    watcher.FXBase.candles['time_id']= watcher.FXBase.candles.index + 1
    ana    = analyzer.Analyzer()
    result = ana.perform()


    # 2回目以降の定期処理
    # timer = intrvl.MethodTimer(c_watcher.request_chart)
    # while True:
    #     intrvl.schedule.run_pending()
    #     next_time = intrvl.schedule.next_run().strftime('%Y-%m-%d %H:%M')
    #     print('')
    #     print(
    #         'next execution:', str(next_time),
    #         'intrvl:',       str(intrvl.schedule.idle_seconds())
    #     )
    #     intrvl.time.sleep(20)
    #     print(watcher.FXBase.candles.tail())
