from datetime import datetime

def update_log():
    hist_file_path = 'log/heroku_scheduler.hist'
    enum_weekday   = {
        0: 'Mon', 1: 'Tue', 2: 'Wed', 3:'Thu',
        4: 'Fri', 5: 'Sat', 6: 'Sun'
    }

    now_delta = datetime.now()
    now       = now_delta.strftime("%Y/%m/%d %H:%M:%S")
    weekday   = enum_weekday[now_delta.weekday()]
    action    = 'now sleeping ...' if weekday in ['Sat', 'Sun'] else 'updated ...'
    line      = '{now}({weekday}) {action} \n'.format(now=now, weekday=weekday, action=action)
    with open(hist_file_path, mode='a', encoding='utf-8') as file:
        file.write(line)

if __name__ == '__main__':
    update_log()
