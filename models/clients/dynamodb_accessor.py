from decimal import Decimal
import json
import os

import boto3
from boto3.dynamodb.conditions import Key  # , Attr
from botocore.exceptions import ClientError, EndpointConnectionError
from numpy import nan


class DynamodbAccessor():
    def __init__(self, pare_name, table_name='H1_CANDLES'):
        self.pare_name = pare_name
        self._table = self.__init_table(table_name)

    @property
    def table(self):
        return self._table

    def batch_insert(self, items):
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
        items = items.replace({nan: None}) \
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

    def list_records(self, from_str, to_str):
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

        to_edge = '{}.999999'.format(to_str[:19])
        try:
            response = self.table.query(
                KeyConditionExpression=Key('pareName').eq(self.pare_name) & Key('time').between(from_str, to_edge)
            )
        except ClientError as error:
            print(error.response['Error']['Message'])
            raise
        else:
            records = response['Items']
            return records

    def __init_table(self, table_name):
        # HACK: env:DYNAMO_ENDPOINT(endpoint_url) が
        #   設定されている場合 => localhost の DynamoDB テーブルを参照
        #   設定されていない場合 => AWS上の DynamoDB テーブルを参照する
        endpoint_url = os.environ.get('DYNAMO_ENDPOINT')
        dynamodb = boto3.resource('dynamodb', region_name='us-east-2', endpoint_url=endpoint_url)

        try:
            table_names = boto3.client('dynamodb', region_name='us-east-2', endpoint_url=endpoint_url) \
                               .list_tables()['TableNames']
            if table_name not in table_names:
                table = self.__create_table(dynamodb, table_name)
            else:
                table = dynamodb.Table(table_name)
        except EndpointConnectionError as error:
            print(error)
            raise Exception('[Dynamo] can`t have reached DynamoDB !')

        return table

    def __create_table(self, dynamodb, table_name):
        table = dynamodb.create_table(
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
