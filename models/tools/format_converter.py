import datetime
from typing import Any, Dict, List
import pandas as pd


TIME_STRING_FMT = '%Y-%m-%d %H:%M:%S'


def str_to_datetime(time_string):
    result_dt = datetime.datetime.strptime(time_string, TIME_STRING_FMT)
    return result_dt


def granularity_to_timedelta(granularity):
    time_unit = granularity[0]
    if time_unit == 'M':
        candle_duration = datetime.timedelta(minutes=int(granularity[1:]))
    elif time_unit == 'H':
        candle_duration = datetime.timedelta(hours=int(granularity[1:]))
    elif time_unit == 'D':
        candle_duration = datetime.timedelta(days=1)

    return candle_duration


def to_oanda_format(target_datetime):
    # datetime.datetime(2020,10,1).isoformat(timespec='microseconds') + 'Z'
    return target_datetime.strftime('%Y-%m-%dT%H:%M:00.000000Z')


def to_candles_from_dynamo(records: List[Dict[str, Any]]) -> pd.DataFrame:
    result: pd.DataFrame = pd.json_normalize(records)
    if records == []:
        return result

    time_series: pd.DataFrame = result['time'].copy()
    result.drop(['time', 'pareName'], axis=1, inplace=True)
    result: pd.DataFrame = result.applymap(float)
    result['time']: pd.Series = time_series.map(convert_to_m10)
    return result


def convert_to_m10(oanda_time):
    m1_pos = 15
    m10_str = oanda_time[:m1_pos] + '0' + oanda_time[m1_pos + 1:]
    m10_str = __truncate_sec(m10_str).replace('T', ' ')
    return m10_str


def __truncate_sec(oanda_time_str):
    sec_start = 17
    truncated_str = oanda_time_str[:sec_start] + '00'
    return truncated_str
