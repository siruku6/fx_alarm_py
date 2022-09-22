import json

from typing import Dict, List
import pytest

from aws_lambda_powertools.utilities.data_classes import (
    APIGatewayProxyEvent,
)

from src.handlers import api_util, trade_hist


@pytest.fixture(name="tradehist_event", scope="module", autouse=True)
def fixture_tradehist_event() -> APIGatewayProxyEvent:
    event: APIGatewayProxyEvent = {  # type: ignore
        "queryStringParameters": {
            "pareName": "USD_JPY",
            "from": "2020-12-30T04:58:09.460556567Z",
            "to": "2021-01-28T04:58:09.460556567Z",
        },
        "multiValueQueryStringParameters": {
            "indicator_names": [
                "sigma*-2_band",
                "sigma*2_band",
                "sigma*-1_band",
                "sigma*1_band",
                "60EMA",
                "10EMA",
                "SAR",
                "20SMA",
                "stoD",
                "stoSD",
                "support",
                "regist",
            ]
        },
    }
    return event


@pytest.fixture(name="invalid_tradehist_event", scope="module", autouse=True)
def fixture_invalid_tradehist_event() -> APIGatewayProxyEvent:
    event: APIGatewayProxyEvent = {  # type: ignore
        "queryStringParameters": {
            "pareName": "USD_JPY",
            "from": "2020-10-30T04:58:09.460556567Z",
            "to": "2020-12-31T04:58:09.460556567Z",
        },
        "multiValueQueryStringParameters": {
            "indicator_names": [
                "sigma*-2_band",
                "sigma*2_band",
                "sigma*-1_band",
                "sigma*1_band",
                "60EMA",
                "10EMA",
                "SAR",
                "20SMA",
                "stoD",
                "stoSD",
                "support",
                "regist",
            ]
        },
    }
    return event


class TestApiHandler:
    def test_fails_api_handler(self, invalid_tradehist_event: APIGatewayProxyEvent):
        result: Dict = trade_hist.api_handler(invalid_tradehist_event, None)

        assert result["statusCode"] == 400
        assert result["headers"] == api_util.headers(method="GET", allow_credentials="true")
        assert result["body"] == json.dumps(
            {"message": "Maximum days between FROM and TO is 60 days. You requested 62 days!"}
        )


# class TestTradehistParamsValid:
def test_params_valid(tradehist_event: APIGatewayProxyEvent):
    params: Dict[str, str] = tradehist_event["queryStringParameters"]
    multi_value_params: Dict[str, List] = tradehist_event["multiValueQueryStringParameters"]

    valid, body, status = trade_hist.__tradehist_params_valid(params, multi_value_params)
    assert valid
    assert body is None
    assert status is None


def test_params_invalid(invalid_tradehist_event: APIGatewayProxyEvent):
    params: Dict[str, str] = invalid_tradehist_event["queryStringParameters"]
    multi_value_params: Dict[str, List] = invalid_tradehist_event["multiValueQueryStringParameters"]
    valid, body, status = trade_hist.__tradehist_params_valid(params, multi_value_params)
    assert not valid
    assert isinstance(body, str)
    assert status == 400


def test___headers():
    method = "POST"
    result = api_util.headers(method=method, allow_credentials="true")
    assert result["Access-Control-Allow-Methods"] == "OPTIONS,{}".format(method)


def test___period_between_from_to():
    result = trade_hist.__period_between_from_to(
        from_str="2020-12-30T04:58:09.460556567Z", to_str="2021-01-28T04:58:09.460556567Z"
    )
    assert result == 29
