from typing import Dict, Union
from unittest.mock import patch

from oandapyV20.exceptions import V20Error

from src.handlers import auto_trade


class TestLambdaHandler:
    # @patch("src.clients.sns.publish")
    def test_market_is_closed(self, patch_not_tradeable):
        """
        Condition: loading candles from OandaAPI is failed
        """
        with patch("src.candle_loader.CandleLoader.run", return_value={"tradeable": False}):
            res: Dict[str, Union[int, str]] = auto_trade.lambda_handler({}, {})

        assert res["statusCode"] == 204
        assert (
            res["body"] == "1. lambda function is correctly finished, but now the market is closed."
        )

    def test_V20Error(self):
        with patch(
            "oandapyV20.API.request",
            side_effect=V20Error(code=400, msg="Invalid value specified for 'accountID'"),
        ):
            with patch("src.clients.sns.publish"):
                res: Dict[str, Union[int, str]] = auto_trade.lambda_handler({}, {})
                assert res["statusCode"] == 500
