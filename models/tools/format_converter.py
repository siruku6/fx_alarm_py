import datetime


def str_to_datetime(time_string):
    result_dt = datetime.datetime.strptime(time_string, '%Y-%m-%d %H:%M:%S')
    return result_dt


def to_oanda_format(target_datetime):
    return target_datetime.strftime('%Y-%m-%dT%H:%M:00.000000Z')