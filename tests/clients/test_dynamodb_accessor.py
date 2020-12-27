import datetime
import os
import boto3
from boto3.dynamodb.conditions import Attr

from moto import mock_dynamodb2
import pytest
import models.clients.dynamodb_accessor as dn_accessor


@pytest.fixture(scope='module', autouse=True)
def table_name():
    return 'H1_CANDLES'


@pytest.fixture(scope='module', autouse=True)
def init_endpoint():
    if os.environ.get('DYNAMO_ENDPOINT') is not None:
        del os.environ['DYNAMO_ENDPOINT']


@pytest.fixture(scope='module', autouse=False)
def dynamo_client(table_name):
    mock = mock_dynamodb2()
    mock.start()

    yield dn_accessor.DynamodbAccessor(pare_name='USD_JPY', table_name=table_name)

    mock.stop()


@mock_dynamodb2
def test___init_table(dynamo_client, table_name):
    region = 'us-east-2'
    # Case1: There is no table
    table_names = boto3.client('dynamodb', region_name=region).list_tables()['TableNames']
    assert table_names == []

    # Case2: There is one table
    dynamo_client._DynamodbAccessor__init_table(table_name=table_name)
    table_names = boto3.client('dynamodb', region_name=region).list_tables()['TableNames']
    assert table_name in table_names

    # Case3: There is only one table even if `__init_table()` was called twice
    dynamo_client._DynamodbAccessor__init_table(table_name=table_name)
    table_names = boto3.client('dynamodb', region_name=region).list_tables()['TableNames']
    assert len(table_names) == 1


@mock_dynamodb2
def test_list_table(dynamo_client, table_name):
    region = 'us-east-2'
    dynamo_client._DynamodbAccessor__init_table(table_name=table_name)

    # Case1: There is no record
    to_str = datetime.datetime.utcnow()
    from_str = to_str - datetime.timedelta(days=16)
    records = dynamo_client.list_records(from_str.isoformat(), to_str.isoformat())
    assert len(records) == 0

    # Case2: There is 15 records
    dn_accessor.prepare_dummy_data(dynamo_client)  # Create 15 records
    to_str = datetime.datetime.utcnow()
    from_str = to_str - datetime.timedelta(days=16)
    records = dynamo_client.list_records(from_str.isoformat(), to_str.isoformat())
    assert len(records) == 15
