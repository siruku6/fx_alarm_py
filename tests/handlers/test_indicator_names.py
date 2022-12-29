import json
from typing import Dict, Union

from src.handlers import indicator_names
from src.analyzer import Analyzer


class TestIndicatorNames:
    def test_default(self) -> None:
        """
        Condition: loading candles from OandaAPI is failed
        """
        res: Dict[str, Union[int, str]] = indicator_names.api_handler({}, {})

        assert res["statusCode"] == 200
        assert res["headers"] == {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "OPTIONS,GET",
        }
        assert res["body"] == json.dumps(Analyzer.INDICATOR_NAMES)
