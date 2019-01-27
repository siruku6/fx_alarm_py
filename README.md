# FX_Alarm_py
This alarms the timing for trading currency, with python. (now being developed...)

## Overview
FXの為替レートを自動取得し、今後の予測が容易なタイミングでメールを送信する。  
以下のような流れで動作する。  
1. FXの為替レートをOandaAPI経由で取得
2. トレンドラインを自動生成
3. 終値が2回トレンドラインを突破したタイミングでメールを送信

するようになる予定

## Description
まだ全然できてません！

## Requirement
- python3
- pip modules
    ```bash
    # 詳細は requirements.txt を参照
    # pip install -r requirements.txt
    ```

- 環境変数
    ```
    $ vim ~/.bash_profile
    export OANDA_ACCESS_TOKEN=YOUR TOKEN
    export MAIL_TO=通知メール宛先
    export MAIL_FROM=送信元となるGmailメルアド
    ```

- Enable your GmailAPI  
coming soon ...
