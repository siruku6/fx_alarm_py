from typing import Any, Dict, Union

from aws_lambda_powertools import Logger

from src.clients import sns

LOGGER = Logger()


def _notify_error(
    error_body: Any,
    raised_line: Union[str, list],
    _traceback: str,
) -> None:
    LOGGER.info({"callable options of e": dir(error_body)})  # type: ignore

    error_summary_dict: Dict[str, Any] = {
        "class": error_body.__class__.__name__,
        "error_msg": error_body.msg,
        "raised_line": raised_line,
        "code": error_body.code,
        "traceback": _traceback,
    }
    LOGGER.error({"summary": error_summary_dict})
    LOGGER.error({"error_body": error_body})

    sns.publish(dic=error_summary_dict, subject=f"Error: {error_body.code}")
