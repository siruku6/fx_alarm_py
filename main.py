import models.mail          as mail
import models.interval      as intrvl
import models.chart_watcher as watcher

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

    # 定期処理
    timer = intrvl.MethodTimer(span_minutes=5, method=c_watcher.request_chart)
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
