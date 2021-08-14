from decimal import Decimal
import json
import os
import typing as t

import boto3
from boto3.dynamodb.conditions import Key  # , Attr
from botocore.exceptions import ClientError, EndpointConnectionError
from numpy import nan
import pandas as pd


class DynamodbAccessor():
    def __init__(self, pare_name: str, table_name: str = 'H1_CANDLES'):
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
        items: t.List[t.Dict[str, t.Union[str, float]]] = items.replace({nan: None}) \
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

    def list_records(self, from_str: str, to_str: str) -> t.List[t.Dict[str, t.Union[str, float]]]:
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
            response: t.Dict[str, t.Union[t.List, int, t.Dict]] = self.table.query(
                KeyConditionExpression=Key('pareName').eq(self.pare_name) & Key('time').between(from_str, to_edge)
            )
        except ClientError as error:
            print(error.response['Error']['Message'])
            raise
        else:
            records: t.List[t.Dict[str, t.Union[str, float]]] = response['Items']
            return records

    def __init_table(self, table_name: str) -> 'boto3.resources.factory.dynamodb.Table':
        # HACK: env:DYNAMO_ENDPOINT(endpoint_url) が
        #   設定されている場合 => localhost の DynamoDB テーブルを参照
        #   設定されていない場合 => AWS上の DynamoDB テーブルを参照する
        endpoint_url: str = os.environ.get('DYNAMO_ENDPOINT')
        dynamodb: 'boto3.resources.factory.dynamodb.ServiceResource' = boto3.resource(
            'dynamodb',
            region_name='us-east-2', endpoint_url=endpoint_url,
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
        )

        try:
            table_names: t.List[str] = boto3.client(
                'dynamodb', region_name='us-east-2', endpoint_url=endpoint_url
            ).list_tables()['TableNames']
            if table_name not in table_names:
                table: 'boto3.resources.factory.dynamodb.Table' = self.__create_table(dynamodb, table_name)
            else:
                table: 'boto3.resources.factory.dynamodb.Table' = dynamodb.Table(table_name)
        except EndpointConnectionError as error:
            print(error)
            raise Exception('[Dynamo] can`t have reached DynamoDB !')

        return table

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
