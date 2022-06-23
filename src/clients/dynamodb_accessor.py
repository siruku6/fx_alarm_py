from decimal import Decimal
import json
import os
import typing as t
from typing import Dict, Optional, TypedDict

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError, EndpointConnectionError, WaiterError
from numpy import nan
import pandas as pd

import src.tools.format_converter as converter


class CandleRecord(TypedDict, total=False):
    pareName: str
    time: str
    close: Decimal
    high: Decimal
    low: Decimal
    open: Decimal


QueryResult = t.Dict[str, t.Union[t.List[CandleRecord], int, t.Dict]]


class DynamodbAccessor():
    def __init__(self, pare_name: str, table_name: str = 'H1_CANDLES'):
        self._environment: str = os.environ.get('EXECTION_ENVIRONMENT')

        # NOTE: This is necessary only for accessing AWS Resources from localhost.
        self._endpoint_url: str = os.environ.get('DYNAMO_ENDPOINT')
        # self._region: str = os.environ.get('AWS_DEFAULT_REGION')

        self.pare_name: str = pare_name
        self._table: 'boto3.resources.factory.dynamodb.Table' = self.__init_table(table_name)

    @property
    def table(self) -> 'boto3.resources.factory.dynamodb.Table':
        return self._table

    def batch_insert(self, items: pd.DataFrame) -> None:
        '''
        Parameters
        ----------
        items : pandas.DataFrame
            Columns :
                pareName : String (required)
                time     : String (required)
        '''
        print('[Dynamo] batch_insert is starting ... (records size is {})'.format(len(items)))
        print('[Dynamo] items \n {})'.format(items))

        items['pareName'] = self.pare_name
        items: t.List[CandleRecord] = items.replace({nan: None}) \
                                           .to_dict('records')

        items = json.loads(json.dumps(items), parse_float=Decimal)
        try:
            with self.table.batch_writer(overwrite_by_pkeys=['pareName', 'time']) as batch:
                for item in items:
                    batch.put_item(Item=item)
        except ClientError as error:
            print(error.response['Error']['Message'])
        else:
            print('[Dynamo] batch_insert is finished !')

    def list_records(self, from_str: str, to_str: str) -> t.List[CandleRecord]:
        '''

        Parameters
        ----------
        from_str : str
            example: '2020-12-08T00:00:00'
        to_str : str
            example: '2020-12-15T15:22:21'

        Returns
        -------
        pandas.DataFrame
            example
                    pareName time
                0   USD_JPY  2020-12-13T02:44:10.558096
                1   USD_JPY  2020-12-14T02:44:10.558096
                2   USD_JPY  2020-12-15T02:44:10.558096
        '''

        to_edge: str = '{}.999999'.format(to_str[:19])
        try:
            response: QueryResult = self.table.query(
                KeyConditionExpression=Key('pareName').eq(self.pare_name) & Key('time').between(from_str, to_edge)
            )
        except ClientError as error:
            print(error.response['Error']['Message'])
            raise
        else:
            records: t.List[CandleRecord] = response['Items']
            return records

    def list_candles(self, from_str: str, to_str: str) -> pd.DataFrame:
        records: t.List[CandleRecord] = self.list_records(from_str, to_str)
        return converter.to_candles_from_dynamo(records)

    def setup_dummy_data(self) -> None:
        '''
        Generate dummy candles into dynamodb for backtest
        '''
        try:
            record: t.List[CandleRecord] = self.table.scan(
                FilterExpression=Attr('pareName').eq(self.pare_name),
                Limit=1
            ).get('Items')
        except ClientError as error:
            print(error.response['Error']['Message'])
        else:
            if not record == []:
                return

            sample_candles: pd.DataFrame = pd.read_csv('tests/fixtures/sample_candles.csv')
            sample_candles['time'] = pd.to_datetime(sample_candles['time']).map(lambda x: x.isoformat())
            self.batch_insert(sample_candles)

    def __init_table(self, table_name: str) -> 'boto3.resources.factory.dynamodb.Table':
        dynamodb: 'boto3.resources.factory.dynamodb.ServiceResource' = self.__init_dynamo_resource()

        try:
            table_names: t.List[str] = self.__init_dynamo_client().list_tables()['TableNames']
            if table_name not in table_names:
                table: 'boto3.resources.factory.dynamodb.Table' = self.__create_table(dynamodb, table_name)
            else:
                table: 'boto3.resources.factory.dynamodb.Table' = dynamodb.Table(table_name)
        except(ClientError, EndpointConnectionError, WaiterError) as error:
            print(error)
            raise Exception('[Dynamo] can`t have reached DynamoDB !')

        return table

    def __init_dynamo_resource(self) -> 'boto3.resources.factory.dynamodb.ServiceResource':
        resource_info: Dict[str, Optional[str]] = {}
        if self._environment == 'localhost':
            resource_info = {'endpoint_url': self._endpoint_url}

        return boto3.resource('dynamodb', **resource_info)

    def __init_dynamo_client(self):
        resource_info: Dict[str, Optional[str]] = {}
        if self._environment == 'localhost':
            resource_info = {'endpoint_url': self._endpoint_url}

        return boto3.client('dynamodb', **resource_info)

    def __create_table(self, dynamodb, table_name: str) -> 'boto3.resources.factory.dynamodb.Table':
        table: 'boto3.resources.factory.dynamodb.Table' = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'pareName', 'KeyType': 'HASH'},
                {'AttributeName': 'time', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'pareName', 'AttributeType': 'S'},
                {'AttributeName': 'time', 'AttributeType': 'S'}
            ],
            ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
        )
        table.meta \
             .client \
             .get_waiter('table_exists') \
             .wait(TableName=table_name)
        return table


from datetime import datetime


def loading_sample(startdate: str = None, enddate: str = None) -> pd.DataFrame:
    """
    Usage example of this class
    """
    if startdate is None:
        startdate = datetime(2020, 1, 1).isoformat()
    if enddate is None:
        enddate = datetime(2021, 12, 31).isoformat()

    granularity: str = 'H1'
    table_name = '{}_CANDLES'.format(granularity)
    dynamo = DynamodbAccessor('GBP_JPY', table_name=table_name)
    candles = dynamo.list_candles(startdate, enddate)
    print(candles)
    return candles
