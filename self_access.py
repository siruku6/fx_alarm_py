import requests
from datetime import datetime
import models.interval as interval

# http://docs.python-requests.org/en/master/
def request_hoge():
    response = requests.get('https://fx-alarm-py.herokuapp.com/')
    status   = response.status_code
    print('status: {status_code}'.format(status_code=status))
    # print(response.headers['content-type'])
    # print(response.encoding)
    print(response.text[:100])

    with open('sleep_test.txt', mode='a', encoding='utf-8') as file:
        now = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        if int(status) < 300:
            msg = '{now} updated ...\n'.format(now=now)
            file.write(msg)
        else:
            msg = '{now} server closed !\n'.format(now=now)
            file.write(msg)
            exit()

if __name__ == '__main__':
    access_timer = interval.MethodTimer(
        method=request_hoge,
        span_minutes=1
    )
    access_timer.wait_until_killed(report_span_sec=5)
