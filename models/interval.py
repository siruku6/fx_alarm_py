import schedule
import time

class MethodTimer():
    def __init__(self, span_minutes=5, method):
        schedule.every(span_minutes).minutes.do(method)

    def wait_until_killed(self, report_span_sec=20):
        while True:
            schedule.run_pending()
            next_time = schedule.next_run().strftime('%Y-%m-%d %H:%M')
            print('')
            print(
                'next execution:', str(next_time),
                'interval:',       str(schedule.idle_seconds())
            )
            time.sleep(report_span_sec)

if __name__ == '__main__':
    def hoge():
        print('hoge')
    timer = MethodTimer(span_minutes=5, method=hoge)
    timer.wait_until_killed(report_span_sec=3)
