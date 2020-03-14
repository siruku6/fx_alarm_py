# FX_Alarm_py

[![Build Status](https://travis-ci.org/siruku6/fx_alarm_py.svg?branch=master)](https://travis-ci.org/siruku6/fx_alarm_py)
[![Maintainability](https://api.codeclimate.com/v1/badges/67acc571f4fe4e7f7959/maintainability)](https://codeclimate.com/github/siruku6/fx_alarm_py/maintainability)

## Overview
FXの為替レートを自動取得し、
- 指定した期間中、特定のルールでトレードした場合の損益を自動集計
- 今後の予測が容易なタイミングでメールを送信

するようにする予定（したい）

## Description
まだ全然できてません！

## Requirement
- python3.x
- pip modules
    ```bash
    # 詳細は requirements.txt を参照
    # pip install -r requirements.txt
    ```

- 環境変数
    ```
    $ vim ~/.bash_profile

    #  - - - Necessary - - -
    # Client
    export OANDA_ACCESS_TOKEN=YOUR TOKEN
    export OANDA_ACCOUNT_ID=YOUR Account ID

    # Other
    export SENDGRID_APIKEY=sendgridのapikey
    export MAIL_TO=通知メール宛先
    export MAIL_FROM=送信元となるGmailメルアド

    #  - - - Option - - -
    # Client
    export OANDA_ENVIRONMENT=OANDA側の環境    # default: practice
    export UNITS=注文毎の購入通貨数           # default: 1

    # Trader
    export GRANULARITY=取引時に利用する足     # default: M5
    export INSTRUMENT=取引する通貨ペア        # default: USD_JPY
    export STOPLOSS_BUFFER=stoplossまでの間隔 # default: 0.05
    export CUSTOM_RULE=on                     # default: off 試験中のruleを使う場合はonにする
    ```

- Enable your GmailAPI or SendGrid  
