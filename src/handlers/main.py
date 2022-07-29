import datetime
import json
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from src.analyzer import Analyzer
from src.history_visualizer import Visualizer
from src.real_trader import RealTrader


# For auto trader
def lambda_handler(_event, _context):
    trader = RealTrader(operation="live")
    if not trader.tradeable:
        msg = "1. lambda function is correctly finished, but now the market is closed."
        return {"statusCode": 204, "body": json.dumps(msg)}

    trader.apply_trading_rule()
    msg = "lambda function is correctly finished."
    return {"statusCode": 200, "body": json.dumps(msg)}


# ------------------------------
#         For tradehist
# ------------------------------
def indicator_names_handler(_event: Dict[str, Dict], _context: Dict) -> Dict:
    return {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "OPTIONS,GET",
            # 'Access-Control-Allow-Credentials': 'true'
        },
        "body": json.dumps(Analyzer.INDICATOR_NAMES),
    }


def api_handler(event: Dict[str, Dict], _context: Dict) -> Dict:
    # TODO: oandaとの通信失敗時などは、500 エラーレスポンスを返せるようにする
    params: Dict[str, str] = event["queryStringParameters"]
    multi_value_params: Dict[str, List] = event["multiValueQueryStringParameters"]

    valid: bool
    body: str
    status: int
    valid, body, status = __tradehist_params_valid(params, multi_value_params)
    if valid:
        body: str = __drive_generating_tradehist(params, multi_value_params)
        status: int = 200
    print("[Main] lambda function is correctly finished.")

    return {"statusCode": status, "headers": __headers(method="GET"), "body": body}


def __headers(method: str) -> Dict[str, str]:
    return {
        # 'Access-Control-Allow-Origin': 'https://www.example.com',
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "OPTIONS,{}".format(method),
        "Access-Control-Allow-Credentials": "true",
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
    return result["valid"], result["body"], result["status"]


def __period_between_from_to(from_str: str, to_str: str) -> int:
    start: datetime = datetime.datetime.fromisoformat(from_str[:26].rstrip("Z"))
    end: datetime = datetime.datetime.fromisoformat(to_str[:26].rstrip("Z"))
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
            # HACK: Nan は json では認識できないので None に書き換えてから to_dict している
            #   to_json ならこの問題は起きないが、dumps と組み合わせると文字列になってしまうのでしない
            "history": (tradehist.replace({np.nan: None}).to_dict(orient="records"))
        }
    )
    return result


# For local console
if __name__ == "__main__":
    # # Real Trade
    # lambda_handler(None, None)

    # Get Indicators
    # print(indicator_names_handler(None, None))

    # Tradehist
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
    api_handler(DUMMY_EVENT, None)
