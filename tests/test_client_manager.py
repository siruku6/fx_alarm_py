import datetime
import pytest

import models.client_manager as manager
from models.clients.oanda_client import OandaClient


@pytest.fixture(name='client', scope='module', autouse=True)
def oanda_client():
    client = manager.ClientManager(instrument='USD_JPY')
    yield client

# - - - - - - - - - - -
#    Private methods
# - - - - - - - - - - -
def test___calc_requestable_max_days(client):
    correction = {
        'D': 5000, 'M12': int(5000 / 120), 'H12': int(5000 / 2)
    }
    for key, expected_count in correction.items():
        cnt = client._ClientManager__calc_requestable_max_days(granularity=key)
        assert cnt == expected_count


def test___calc_requestable_time_duration(client):
    max_count = OandaClient.REQUESTABLE_COUNT - 1
    granularties = ('M1', 'M5', 'M10', 'M15', 'M30', 'H1', 'H4', 'D')
    durations = [
        datetime.timedelta(minutes=time_int * max_count) for time_int in [1, 5, 10, 15, 30]
    ] + [
        datetime.timedelta(minutes=time_int * max_count * 60) for time_int in [1, 4]
    ]
    durations.append(datetime.timedelta(minutes=1 * max_count * 60 * 24))

    for granularity, expected_duration in zip(granularties, durations):
        requestable_time_duration = client._ClientManager__calc_requestable_time_duration(
            granularity=granularity
        )
        assert requestable_time_duration == expected_duration
