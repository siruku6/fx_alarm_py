from datetime import datetime
import json
from typing import Dict, List, Tuple

from aws_lambda_powertools.utilities.data_classes import (
    APIGatewayProxyEvent,)  # SQSEvent, event_source
from aws_lambda_powertools.utilities.typing import LambdaContext
import numpy as np
import pandas as pd

from src.history_visualizer import Visualizer

from . import api_util


def api_handler(event: APIGatewayProxyEvent, _context: LambdaContext) -> Dict:
    # TODO: oandaとの通信失敗時などは、500 エラーレスポンスを返せるようにする
    params: Dict[str, str] = event["queryStringParameters"]
    multi_value_params: Dict[str, List] = event["multiValueQueryStringParameters"]

    valid: bool
    body: str
    status: int
    valid, body, status = __tradehist_params_valid(params, multi_value_params)
    if valid:
        body = __drive_generating_tradehist(params, multi_value_params)
        status = 200
    print("[Main] lambda function is correctly finished.")

    return {
        "statusCode": status,
        "headers": api_util.headers(method="GET", allow_credentials="true"),
        "body": body,
    }


def __tradehist_params_valid(
    params: Dict[str, str], _multi_value_params: Dict[str, List]
) -> Tuple[bool, str, int]:
    requested_period: int = __period_between_from_to(params["from"], params["to"])
    if requested_period >= 60:
        msg: str = "Maximum days between FROM and TO is 60 days. You requested {} days!".format(
            requested_period
        )
        body: str = json.dumps({"message": msg})
        status: int = 400
        result = {"valid": False, "body": body, "status": status}
    else:
        result = {"valid": True, "body": None, "status": None}
    return result["valid"], result["body"], result["status"]  # type: ignore


def __period_between_from_to(from_str: str, to_str: str) -> int:
    start: datetime = datetime.fromisoformat(from_str[:26].rstrip("Z"))
    end: datetime = datetime.fromisoformat(to_str[:26].rstrip("Z"))
    result: int = (end - start).days
    return result


def __drive_generating_tradehist(
    params: Dict[str, str], multi_value_params: Dict[str, List]
) -> str:
    pare_name: str = params["pareName"]
    from_str: str = params["from"]
    to_str: str = params["to"]
    indicator_names: List[str] = multi_value_params.get("indicator_names[]") or []

    visualizer: Visualizer = Visualizer(
        from_str,
        to_str,
        instrument=pare_name,
        indicator_names=tuple(indicator_names),
    )
    tradehist: pd.DataFrame = visualizer.run()
    result: str = json.dumps(
        {
            # HACK: use replace np.nan into None because `json` can't realize np.nan(Nan)
            #   to_json ならこの問題は起きないが、dumps と組み合わせると文字列になってしまうのでしない
            "history": (tradehist.replace({np.nan: None}).to_dict(orient="records"))
        }
    )
    return result


# For local console
if __name__ == "__main__":
    DUMMY_EVENT = {
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
    api_handler(DUMMY_EVENT, None)  # type: ignore
