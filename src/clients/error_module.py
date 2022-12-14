import sys
from typing import Any, Dict

from aws_lambda_powertools import Logger

from src.clients import sns

LOGGER = Logger()


def _notify_error(
    error_body: Any,
    parent_method: str,
    _traceback: str,
) -> None:
    error_summary_dict: Dict[str, str] = {
        "class": error_body.__class__.__name__,
        "parent_method": parent_method,
        "code": error_body.code,
        "traceback": _traceback,
    }
    LOGGER.error(error_summary_dict)
    LOGGER.error(error_body)

    sns.publish(dic=error_summary_dict, subject=f"Error: {error_body.code}")

    LOGGER.info({f"[{sys._getframe().f_back.f_code.co_name}] dir(error)": dir(error_body)})  # type: ignore
    # error.msg
