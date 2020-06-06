import datetime


TIME_STRING_FMT = '%Y-%m-%d %H:%M:%S'


def str_to_datetime(time_string):
    result_dt = datetime.datetime.strptime(time_string, TIME_STRING_FMT)
    return result_dt


def to_oanda_format(target_datetime):
    return target_datetime.strftime('%Y-%m-%dT%H:%M:00.000000Z')


def convert_to_m10(oanda_time):
    m1_pos = 15
    m10_str = oanda_time[:m1_pos] + '0' + oanda_time[m1_pos + 1:]
    m10_str = __truncate_sec(m10_str).replace('T', ' ')
    return m10_str


def __truncate_sec(oanda_time_str):
    sec_start = 17
    truncated_str = oanda_time_str[:sec_start] + '00'
    return truncated_str
