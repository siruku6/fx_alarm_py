import sys
import traceback
from typing import Dict, Union

from aws_lambda_powertools.utilities.data_classes import EventBridgeEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from oandapyV20.exceptions import V20Error
from requests.exceptions import ConnectionError, SSLError

from src.clients.error_module import _notify_error
from src.real_trader import RealTrader
from tools.trade_lab import create_trader_instance


def lambda_handler(_event: EventBridgeEvent, _context: LambdaContext) -> Dict[str, Union[int, str]]:
    try:
        trader, _ = create_trader_instance(RealTrader, operation="live", days=60)
        if trader is None:
            msg = "1. lambda function is correctly finished, but now the market is closed."
            return {"statusCode": 204, "body": msg}

        trader.apply_trading_rule()
        msg = "lambda function is correctly finished."
    except (V20Error, SSLError, ConnectionError) as error:
        type_, value, traceback_ = sys.exc_info()
        tracebacks: list = traceback.format_exception(type_, value, traceback_)

        _notify_error(
            error,
            raised_line=tracebacks[-3:-1],  # sys._getframe().f_back.f_code.co_name,
            _traceback=traceback.format_exc(),
        )
        # NOTE: https://www.yoheim.net/blog.php?q=20190601
        return {"statusCode": 500}
    except Exception as error:
        type_, value, traceback_ = sys.exc_info()
        tracebacks = traceback.format_exception(type_, value, traceback_)

        _notify_error(
            error,
            raised_line=tracebacks[-3:-1],
            _traceback=traceback.format_exc(),
        )
        raise error

    return {"statusCode": 200, "body": msg}


# For local console
if __name__ == "__main__":
    lambda_handler(None, None)  # type: ignore
