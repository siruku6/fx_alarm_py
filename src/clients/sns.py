import json
import os
from typing import Any, Dict

import boto3


def publish(dic: Dict[str, Any], subject: str = "SNS message") -> None:
    sns = boto3.client("sns", region_name=os.environ.get("AWS_DEFAULT_REGION"))
    sns.publish(
        Subject=subject,
        TopicArn=os.environ.get("SNS_TOPIC_SEND_MAIL_ARN"),
        Message=json.dumps(dic, indent=4, sort_keys=False),
    )
