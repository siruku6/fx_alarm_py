from typing import Dict, Union

from aws_lambda_powertools.utilities.data_classes import EventBridgeEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

from src.real_trader import RealTrader
from tools.trade_lab import create_trader_instance


def lambda_handler(_event: EventBridgeEvent, _context: LambdaContext) -> Dict[str, Union[int, str]]:
    trader, _ = create_trader_instance(RealTrader, operation="live", days=60)
    if trader is None:
        msg = "1. lambda function is correctly finished, but now the market is closed."
        return {"statusCode": 204, "body": msg}

    trader.apply_trading_rule()
    msg = "lambda function is correctly finished."
    return {"statusCode": 200, "body": msg}


# For local console
if __name__ == "__main__":
    lambda_handler(None, None)
