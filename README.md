# FX_Alarm_py
Verifying one trade rule and Alarming trader (now being developed...)

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

    # Necessary
    export OANDA_ACCESS_TOKEN=YOUR TOKEN
    export OANDA_ACCOUNT_ID=YOUR Account ID
    export SENDGRID_APIKEY=sendgridのapikey
    export MAIL_TO=通知メール宛先
    export MAIL_FROM=送信元となるGmailメルアド

    # Option
    export UNITS=注文毎の購入通貨数 # default: UNITS=1
    ```

- Enable your GmailAPI or SendGrid  
