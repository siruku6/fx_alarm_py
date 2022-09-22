from typing import Dict, Optional


def headers(method: str, allow_credentials: Optional[str] = None) -> Dict[str, str]:
    headers: Dict[str, str] = {
        # 'Access-Control-Allow-Origin': 'https://www.example.com',
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "OPTIONS,{}".format(method),
    }

    if allow_credentials is not None:
        headers = dict(**headers, **{"Access-Control-Allow-Credentials": "true"})

    return headers
