from unittest.mock import patch
import pytest

import main


@pytest.fixture(name='tradehist_event', scope='module', autouse=True)
def fixture_tradehist_event():
    event = {
        'queryStringParameters': {
            'pareName': 'USD_JPY',
            'from': '2020-12-30T04:58:09.460556567Z',
            'to': '2021-01-28T04:58:09.460556567Z'
        },
        'multiValueQueryStringParameters': {
            'indicator_names': [
                'sigma*-2_band', 'sigma*2_band', 'sigma*-1_band', 'sigma*1_band',
                '60EMA', '10EMA', 'SAR', '20SMA', 'stoD', 'stoSD', 'support', 'regist'
            ]
        }
    }
    yield event


@pytest.fixture(name='invalid_tradehist_event', scope='module', autouse=True)
def fixture_invalid_tradehist_event():
    event = {
        'queryStringParameters': {
            'pareName': 'USD_JPY',
            'from': '2020-10-30T04:58:09.460556567Z',
            'to': '2020-12-31T04:58:09.460556567Z'
        },
        'multiValueQueryStringParameters': {
            'indicator_names': [
                'sigma*-2_band', 'sigma*2_band', 'sigma*-1_band', 'sigma*1_band',
                '60EMA', '10EMA', 'SAR', '20SMA', 'stoD', 'stoSD', 'support', 'regist'
            ]
        }
    }
    yield event


def test___headers():
    method = 'POST'
    result = main.__headers(method=method)
    assert result['Access-Control-Allow-Methods'] == 'OPTIONS,{}'.format(method)


def test___tradehist_params_valid(tradehist_event, invalid_tradehist_event):
    params: Dict[str, str] = tradehist_event['queryStringParameters']
    multi_value_params: Dict[str, List] = tradehist_event['multiValueQueryStringParameters']
    valid, body, status = main.__tradehist_params_valid(params, multi_value_params)
    assert valid
    assert body is None
    assert status is None

    params: Dict[str, str] = invalid_tradehist_event['queryStringParameters']
    multi_value_params: Dict[str, List] = invalid_tradehist_event['multiValueQueryStringParameters']
    valid, body, status = main.__tradehist_params_valid(params, multi_value_params)
    assert not valid
    assert isinstance(body, str)
    assert status == 400


def test___period_between_from_to():
    result = main.__period_between_from_to(
        from_str='2020-12-30T04:58:09.460556567Z',
        to_str='2021-01-28T04:58:09.460556567Z'
    )
    assert result == 29
