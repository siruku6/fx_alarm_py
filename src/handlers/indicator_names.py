import json
from typing import Dict

from aws_lambda_powertools.utilities.data_classes import (
    APIGatewayProxyEvent,
    # SQSEvent, event_source
)
from aws_lambda_powertools.utilities.typing import LambdaContext

from . import api_util
from src.analyzer import Analyzer


def api_handler(_event: APIGatewayProxyEvent, _context: LambdaContext) -> Dict:
    return {
        "statusCode": 200,
        "headers": api_util.headers(method="GET"),
        "body": json.dumps(Analyzer.INDICATOR_NAMES),
    }
