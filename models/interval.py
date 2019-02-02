import schedule
import time

class MethodTimer():
    def __init__(self, span_minutes, method):
        schedule.every(span_minutes).minutes.do(method)

if __name__ == '__main__':
    def hoge():
        print('hoge')
    timer = MethodTimer(span_minutes=5, method=hoge)

    while True:
        schedule.run_pending()
        next_time = schedule.next_run().strftime('%Y-%m-%d %H:%M')
        print(
            'next execution:', str(next_time),
            'interval:',       str(schedule.idle_seconds())
        )
        time.sleep(3)
