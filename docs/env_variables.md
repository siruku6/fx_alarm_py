1. **Settings for AWS**

    |*Variable*            |*Example*            |*Explanation*|
    |----------------------|---------------------|-------------|
    |AWS_ACCOUNT_ID        |123456789012         |Your Account ID of AWS|
    |AWS_DEFAULT_REGION    |us-east-1            |The region your AWS resource is located on|
    |AWS_ACCESS_KEY_ID     |A18Z (20 digits)     ||
    |AWS_SECRET_ACCESS_KEY |a38Z (40 digits)     ||
    |DYNAMO_ENDPOINT       |http://localhost:8000|1. When developing on localhost,<br>it is better to set the endpoint of `DynamoDB Local`<br>2. On AWS Lambda, you don't have to set this.|

2. **Settings for Oanda infromation**

    |*Variable*            |*Example*            |*Explanation*|
    |----------------------|---------------------|-------------|
    |OANDA_ACCESS_TOKEN    |a30z-a30z (65 digits)|Get on Oanda<br>[OANDA REST API DOCS](https://developer.oanda.com/docs/jp/)|
    |OANDA_ACCOUNT_ID      |100-000-1234567-000  |"|
    |OANDA_ENVIRONMENT     |practice             |The name of environment for Oanda|

3. **Settings for trading**

    |*Variable*            |*Example*            |*Explanation*|
    |----------------------|---------------------|-------------|
    |INSTRUMENT            |USD_JPY              |The name of currency pair you would like to trade|
    |GRANULARITY           |H4                   |The time unit of candles you rely on|
    |STOPLOSS_BUFFER       |0.05                 |This is the buffer for setting stoploss price.<br>For example, if the low price of previous candle is `104.123`,<br>stoploss price is going to be `104.073`.|
    |UNITS                 |1000                 |How much you would like to exchange per one trade|
