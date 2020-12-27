import datetime
# import decimal
# import json
import os

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError
import pandas as pd


class DynamodbAccessor():
    def __init__(self, pare_name, table_name='H1_CANDLES'):
        self.pare_name = pare_name
        self._table = self.__init_table(table_name)

    @property
    def table(self):
        return self._table

    def batch_insert(self, items):
        print('[Dynamo] batch_insert is starting ...')

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

        to_edge = '{}.999999'.format(to_str)
        try:
            response = self.table.query(
                KeyConditionExpression=Key('pareName').eq(self.pare_name) & Key('time').between(from_str, to_edge)
            )
        except ClientError as error:
            print(error.response['Error']['Message'])
            return []
        else:
            records = response['Items']
            return pd.json_normalize(records)

    def __init_table(self, table_name):
        # HACK: env:DYNAMO_ENDPOINT(endpoint_url) が
        #   設定されている場合 => localhost の DynamoDB テーブルを参照
        #   設定されていない場合 => AWS上の DynamoDB テーブルを参照する
        endpoint_url = os.environ.get('DYNAMO_ENDPOINT')
        dynamodb = boto3.resource('dynamodb', region_name='us-east-2', endpoint_url=endpoint_url)

        table_names = boto3.client('dynamodb', region_name='us-east-2', endpoint_url=endpoint_url) \
                           .list_tables()['TableNames']
        if table_names == []:
            table = self.__create_table(dynamodb, table_name)
        else:
            table = dynamodb.Table(table_name)

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


def main():
    pare_name = 'GBP_JPY'
    dynamodb_accessor = DynamodbAccessor(pare_name)
    prepare_dummy_data(dynamodb_accessor)

    candles = dynamodb_accessor.list_records(from_str='2020-12-08T00:00:00', to_str=datetime.datetime.now().isoformat())
    print(candles)


def prepare_dummy_data(dynamodb_accessor):
    try:
        record = dynamodb_accessor.table.scan(
            FilterExpression=Attr('pareName').eq(dynamodb_accessor.pare_name),
            Limit=1
        ).get('Items')
    except ClientError as error:
        print(error.response['Error']['Message'])
    else:
        if not record == []:
            return

        now = datetime.datetime.utcnow()
        dummy_items = [
            {
                'pareName': dynamodb_accessor.pare_name,
                'time': (now - datetime.timedelta(days=i)).isoformat()
            } for i in range(0, 15)
        ]
        dynamodb_accessor.batch_insert(dummy_items)


if __name__ == '__main__':
    main()
    # import pdb; pdb.set_trace()
