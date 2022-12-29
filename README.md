# FX_Alarm_py

[![Python application](https://github.com/siruku6/fx_alarm_py/actions/workflows/lint_and_test.yml/badge.svg)](https://github.com/siruku6/fx_alarm_py/actions/workflows/lint_and_test.yml)
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

You have to introduce following packages before start developing.

- python3.8 or python3.9
- pip modules
    ```bash
    $ pipenv install -d
    ```

- awscli
- node
    - serverless
    ```bash
    $ npm -g install serverless@2
    ```
- DynamoDB Local (and, though it is optional, DynamoDB Admin)

## Deployment

1. Set Environment Variables

    ```bash
    $ cp .env.sample .env
    ```

    change [these variables](https://github.com/siruku6/fx_alarm_py/blob/develop/docs/env_variables.md)

2. Deploy with serverless framework

    ```bash
    $ sls deploy

    # Display the detailed progress
    $ sls deploy --verbose

    # Specifying stage of AWS resources
    $ sls deploy --stage demo
    ```
