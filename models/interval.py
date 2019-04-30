import schedule
import time

def periodically_exec(method, span_minutes=5):
    schedule.every(span_minutes).minutes.do(method)

def wait_until_killed(report_span_sec=20):
    while True:
        schedule.run_pending()
        next_time = schedule.next_run().strftime('%Y-%m-%d %H:%M')
        print('')
        print(
            'next execution:', str(next_time),
            'interval:',       str(schedule.idle_seconds())
        )
        time.sleep(report_span_sec)
