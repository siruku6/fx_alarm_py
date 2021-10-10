import datetime
import os
import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError
import pandas as pd

from moto import mock_dynamodb2
import pytest
import models.clients.dynamodb_accessor as dn_accessor


@pytest.fixture(name='table_name', scope='module', autouse=True)
def fixture_table_name():
    return 'H1_CANDLES'


@pytest.fixture(scope='module', autouse=True)
def init_endpoint():
    if os.environ.get('DYNAMO_ENDPOINT') is not None:
        del os.environ['DYNAMO_ENDPOINT']


@pytest.fixture(name='dynamo_client', scope='module')
def fixture_dynamo_client(table_name):
    mock = mock_dynamodb2()
    mock.start()

    yield dn_accessor.DynamodbAccessor(pare_name='USD_JPY', table_name=table_name)

    mock.stop()


@pytest.fixture(name='import_dummy_records', scope='module')
def fixture_import_dummy_records():
    def _method(dynamodb_accessor):
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
                {'time': (now - datetime.timedelta(days=i)).isoformat()} for i in range(0, 15)
            ]
            dummy_df = pd.DataFrame(dummy_items)
            dynamodb_accessor.batch_insert(dummy_df)
    return _method


@mock_dynamodb2
class TestInitTable:
    def test_no_table(self):
        table_names = boto3.client('dynamodb').list_tables()['TableNames']
        assert table_names == []

    def test_one_table(self, dynamo_client, table_name):
        dynamo_client._DynamodbAccessor__init_table(table_name=table_name)
        table_names = boto3.client('dynamodb').list_tables()['TableNames']
        assert table_name in table_names

    def test_duplicate_table(self, dynamo_client, table_name):
        dynamo_client._DynamodbAccessor__init_table(table_name=table_name)
        table_names = boto3.client('dynamodb').list_tables()['TableNames']
        assert len(table_names) == 1


@mock_dynamodb2
def test_list_table(dynamo_client, table_name, import_dummy_records):
    dynamo_client._DynamodbAccessor__init_table(table_name=table_name)

    # Case1: There is no record
    to_str = datetime.datetime.utcnow()
    from_str = to_str - datetime.timedelta(days=16)
    records = dynamo_client.list_records(from_str.isoformat(), to_str.isoformat())
    assert len(records) == 0
    assert isinstance(records, list)

    # Case2: There is 15 records
    import_dummy_records(dynamo_client)  # Create 15 records
    to_str = datetime.datetime.utcnow()
    from_str = to_str - datetime.timedelta(days=16)
    records = dynamo_client.list_records(from_str.isoformat(), to_str.isoformat())
    assert len(records) == 15
    assert isinstance(records, list)
    assert isinstance(records[0], dict)
