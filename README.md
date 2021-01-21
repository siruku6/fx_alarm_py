# FX_Alarm_py

[![Build Status](https://travis-ci.com/siruku6/fx_alarm_py.svg?branch=master)](https://travis-ci.com/siruku6/fx_alarm_py)
[![Maintainability](https://api.codeclimate.com/v1/badges/67acc571f4fe4e7f7959/maintainability)](https://codeclimate.com/github/siruku6/fx_alarm_py/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/67acc571f4fe4e7f7959/test_coverage)](https://codeclimate.com/github/siruku6/fx_alarm_py/test_coverage)

## Overview

- Backtest
- Real Trade
    - Trade through Oanda API
    - Trading history

## Description

In development ...

## Requirement
- python3.8 or python3.9
- pip modules
    ```bash
    # 詳細は requirements.txt を参照
    $ pip install -r requirements.txt
    ```

- 環境変数
    ```
    $ vim ~/.bash_profile

    #  - - - Necessary - - -
    # Client
    export OANDA_ACCESS_TOKEN=YOUR TOKEN
    export OANDA_ACCOUNT_ID=YOUR Account ID

    #  - - - Option - - -
    # Client
    export OANDA_ENVIRONMENT=OANDA側の環境    # default: practice
    export UNITS=注文毎の購入通貨数           # default: 1

    # Trader
    export GRANULARITY=取引時に利用する足     # default: M5
    export INSTRUMENT=取引する通貨ペア        # default: USD_JPY
    export STOPLOSS_BUFFER=stoplossまでの間隔 # default: 0.05
    
    # DynamoDB: ローカルで開発する場合は、DynamoDB Localのendpointを設定。本番では何も設定しない
    export DYNAMO_ENDPOINT=http://localhost:8000 # defaut: null 
    ```
