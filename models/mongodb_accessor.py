import datetime
import pandas as pd
from pymongo import MongoClient, DESCENDING, ASCENDING

class MongodbAccessor():
    def __init__(self, db_name):
        self.client = MongoClient()
        self._database = self.client.get_database(db_name)

    @property
    def database(self):
        return self._database

    def query_candles(self, currency_pare, start_dt=None, end_dt=None):
        '''
        Return
            DataFrame
                columns -> time(index) |  close  |   high  |   low   |   open  |
                type    ->   string    | float64 | float64 | float64 | float64 |
        '''
        if start_dt is None:
            start_dt = datetime.datetime(1900, 1, 1)
        if end_dt is None:
            end_dt = datetime.datetime.now()

        candles = pd.DataFrame.from_dict(
            self.__where_by(collection_name=currency_pare, start_dt=start_dt, end_dt=end_dt),
        )
        if candles is None:
            return candles

        candles.rename(columns={'_id': 'time'}, inplace=True)
        candles.set_index('time', inplace=True)
        return candles

    def edge_datetimes_of(self, currency_pare):
        '''
        Return
            [datetime, datetime]
        '''
        collection = self.database.get_collection(currency_pare)
        first_record = collection.find_one(sort=[('_id', ASCENDING)])
        last_record = collection.find_one(sort=[('_id', DESCENDING)])

        if first_record is None or last_record is None:
            first = datetime.datetime.now()
            last = first
        else:
            first = first_record['_id']
            last = last_record['_id']
        return first, last

    def bulk_insert(self, dict_array, currency_pare):
        print('[Mongo] bulk_insert is starting ...')
        collection = self.database.get_collection(currency_pare)
        collection.insert_many(dict_array)
        print('[Mongo] bulk_insert is finished !')

    def __where_by(self, collection_name, start_dt, end_dt):
        '''
        Summary
            query from collection (where _id: from start_dt to end_dt),
            but not include end_dt
        Params
            collection_name
                type: string
                sample: 'hoge'
            start_dt
                type: datetime
                sample: datetime.datetime(year=2019, month=10, day=1)
            end_dt:
                type: datetime
                sample: datetime.datetime(year=2019, month=10, day=1)
        Return
            [
                {'_id': datetime,  'close': float, 'high': float, 'low': float, 'open': float},
                {'_id': datetime,  'close': float, 'high': float, 'low': float, 'open': float},
                ...
            ]
        '''
        collection = self.database.get_collection(collection_name)
        # INFO: https://symfoware.blog.fc2.com/blog-entry-1436.html
        records = collection.find(
            filter={'_id': {'$gte': start_dt, '$lt': end_dt}},
            sort=[('_id', ASCENDING)]
        )
        # INFO: <pymongo.cursor.Cursor object at xxxxxxxxxxxxxxxx> を dict に変換
        return [record for record in records]

def main():
    accessor = MongodbAccessor(db_name='candles')
    # gbp_m10_candles = pd.read_csv('log/candles_GBP_JPY_M10.csv', index_col=0, parse_dates=[0])
    # gbp_m10_candles.columns = ['close', 'high', 'low', 'open']
    # m10_dict = gbp_m10_candles.to_dict('records')

    # stocked_candles = pd.read_csv('log/candles_GBP_JPY_M10.csv', index_col=0)

    # # accessor.bulk_insert(collection_name='gbp', dict_array=m10_dict)
    db = accessor.database
    # import pdb; pdb.set_trace()

    res = accessor.query_candles(
        currency_pare='GBP_JPY',
        start_dt=datetime.datetime(year=2010, month=10, day=1),
        end_dt=datetime.datetime(year=2019, month=11, day=16)
    )
    first, last = accessor.edge_datetimes_of(currency_pare='gbp')


if __name__ == '__main__':
    main()
