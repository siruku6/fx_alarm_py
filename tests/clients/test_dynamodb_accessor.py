import datetime
import os
import boto3

from moto import mock_dynamodb2
import pytest
import models.clients.dynamodb_accessor as dn_accessor


@pytest.fixture(scope='module', autouse=True)
def table_name():
    return 'H1_CANDLES'


@pytest.fixture(scope='module', autouse=True)
def init_endpoint():
    del os.environ['DYNAMO_ENDPOINT']


@pytest.fixture(scope='module', autouse=True)
def dynamo_client(table_name):
    yield dn_accessor.DynamodbAccessor(table_name=table_name)


@mock_dynamodb2
def test___init_table(dynamo_client, table_name):
    # Case1: There is no table
    table_names = boto3.client('dynamodb').list_tables()['TableNames']
    assert table_names == []

    # Case2 There is one table
    dynamo_client._DynamodbAccessor__init_table(table_name=table_name)
    table_names = boto3.client('dynamodb').list_tables()['TableNames']
    assert table_name in table_names

    # Case3 There is only one table even if `__init_table()` was called twice
    dynamo_client._DynamodbAccessor__init_table(table_name=table_name)
    table_names = boto3.client('dynamodb').list_tables()['TableNames']
    assert len(table_names) ==  1
