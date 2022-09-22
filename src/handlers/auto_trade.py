from typing import Dict, Union

from aws_lambda_powertools.utilities.data_classes import EventBridgeEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

from src.real_trader import RealTrader


def lambda_handler(_event: EventBridgeEvent, _context: LambdaContext) -> Dict[str, Union[int, str]]:
    trader = RealTrader(operation="live")
    if not trader.tradeable:
        msg = "1. lambda function is correctly finished, but now the market is closed."
        return {"statusCode": 204, "body": msg}

    trader.apply_trading_rule()
    msg = "lambda function is correctly finished."
    return {"statusCode": 200, "body": msg}


# For local console
if __name__ == "__main__":
    lambda_handler(None, None)
