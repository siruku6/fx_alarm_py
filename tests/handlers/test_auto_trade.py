from typing import Dict, Union
from unittest.mock import patch

from src.handlers import auto_trade


class TestLambdaHandler:
    def test_market_is_closed(self):
        """
        Condition: loading candles from OandaAPI is failed
        """
        with patch("src.candle_loader.CandleLoader.run", return_value={"tradeable": False}):
            res: Dict[str, Union[int, str]] = auto_trade.lambda_handler({}, {})

        assert res["statusCode"] == 204
        assert (
            res["body"] == "1. lambda function is correctly finished, but now the market is closed."
        )
