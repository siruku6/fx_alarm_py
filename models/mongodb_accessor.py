import datetime
import pandas as pd
from pymongo import MongoClient, DESCENDING, ASCENDING

class MongoDBAccessor():
    def __init__(self, db_name):
        self.client = MongoClient()
        self._database = self.client.get_database(db_name)

    @property
    def database(self):
        return self._database

    def where_by_datetimes_set(self, collection_name, start_dt, end_dt):
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
        return [record for record in records]

    def edge_datetimes_of(self, collection_name):
        '''
        Return
            [datetime, datetime]
        '''
        collection = self.database.get_collection(collection_name)
        first = collection.find_one(sort=[('_id', ASCENDING)])['_id']
        last = collection.find_one(sort=[('_id', DESCENDING)])['_id']
        return first, last

    def bulk_insert(self, collection_name, dict_array):
        print('[Mongo] bulk_insert is starting ...')
        collection = self.database.get_collection(collection_name)
        collection.insert_many(dict_array)
        print('[Mongo] bulk_insert is finished !')

def main():
    accessor = MongoDBAccessor(db_name='candles')
    # gbp_m10_candles = pd.read_csv('log/candles_GBP_JPY_M10.csv', index_col=0, parse_dates=[0])
    # gbp_m10_candles.columns = ['close', 'high', 'low', 'open']
    # m10_dict = gbp_m10_candles.to_dict('records')

    # stocked_candles = pd.read_csv('log/candles_GBP_JPY_M10.csv', index_col=0)

    # # accessor.bulk_insert(collection_name='gbp', dict_array=m10_dict)
    # res = accessor.where_by_datetimes_set('gbp', datetime.datetime(year=2010, month=10, day=1), datetime.datetime(year=2019, month=11, day=16))
    first, last = accessor.edge_datetimes_of(collection_name='gbp')
    import pdb; pdb.set_trace()


if __name__ == '__main__':
    main()
