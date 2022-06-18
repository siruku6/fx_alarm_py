from enum import Enum
from datetime import datetime


class Weekday(Enum):
    Mon = 0
    Tue = 1
    Wed = 2
    Thu = 3
    Fri = 4
    Sat = 5
    Sun = 6


def is_reasonable() -> bool:
    now: datetime = datetime.utcnow()
    return _is_open(now) and _is_reasonable_hour(now.hour)


def _is_reasonable_hour(hour: int) -> bool:
    """
    - UTC        +00:00 ... It is not reasonable on 20 ~ 22
    - Asia/Tokyo +09:00 ... It is not reasonable on 05 ~ 07 o'clock.
    because spread is going to be wide and trade volume is little.
    """
    if 20 <= hour < 22:
        print(f'[INFO] isn\'t reasonable hour: {hour} (UTC)')
        return False

    return True


def _is_open(now: datetime) -> bool:
    """
    It must be closed on 24 o'clock Fri ~ 18 o'clock Sun (UTC).
    """
    weekday_id: int = now.weekday()
    hour: int = now.hour
    if Weekday.Mon.value <= weekday_id < Weekday.Fri.value:
        return True
    elif Weekday.Fri.value == weekday_id and hour < 23:
        return True
    elif Weekday.Sun.value == weekday_id and 19 <= hour:
        return True

    print(f'[INFO] isn\'t open: {now}')
    return False
