import datetime
from typing import Any, Dict, List

import pandas as pd

from src.clients.oanda_accessor_pyv20.definitions import ISO_DATETIME_STR

TIME_STRING_FMT = "%Y-%m-%d %H:%M:%S"


def str_to_datetime(time_string: str) -> datetime.datetime:
    result_dt = datetime.datetime.strptime(time_string, TIME_STRING_FMT)
    return result_dt


def granularity_to_timedelta(granularity: str) -> datetime.timedelta:
    time_unit: str = granularity[0]
    if time_unit == "M":
        candle_duration: datetime.timedelta = datetime.timedelta(minutes=int(granularity[1:]))
    elif time_unit == "H":
        candle_duration = datetime.timedelta(hours=int(granularity[1:]))
    elif time_unit == "D":
        candle_duration = datetime.timedelta(days=1)

    return candle_duration


def to_timestamp(oanda_str: str) -> pd.Timestamp:
    return pd.to_datetime(oanda_str[:19], format="%Y-%m-%dT%H:%M:%S")


def to_candles_from_dynamo(records: List[Dict[str, Any]]) -> pd.DataFrame:
    result: pd.DataFrame = pd.json_normalize(records)
    if records == []:
        return result

    time_series: pd.Series = result["time"].copy()
    result.drop(["time", "pareName"], axis=1, inplace=True)
    result = result.applymap(float)
    result["time"] = time_series.map(convert_to_m10)
    return result


def convert_to_m10(oanda_time: ISO_DATETIME_STR) -> str:
    m1_pos: int = 15
    m10_str: str = oanda_time[:m1_pos] + "0" + oanda_time[m1_pos + 1 :]
    m10_str = __truncate_sec(m10_str).replace("T", " ")
    return m10_str


def __truncate_sec(oanda_time_str: str) -> str:
    sec_start: int = 17
    truncated_str: str = oanda_time_str[:sec_start] + "00"
    return truncated_str
