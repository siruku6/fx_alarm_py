import datetime
import pandas as pd
from pymongo import MongoClient, DESCENDING, ASCENDING

class MongoDBAccessor():
    def __init__(self, db_name):
        self.client = MongoClient()
        self.database = self.client.get_database(db_name)

    def query_by_datetime(self, collection_name, start_dt, end_dt):
        '''
        Summary
            query collection, where _id: from start_dt to end_dt
        Params
            collection: Collection(Database(MongoClient()))
            start_dt: datetime, ex) datetime.datetime(year=2019, month=10, day=1)
            end_dt: datetime
        Return
            [
                {'_id': datetime,  'close': float, 'high': float, 'low': float, 'open': float},
                {'_id': datetime,  'close': float, 'high': float, 'low': float, 'open': float},
                ...
            ]
        '''
        collection = self.database.get_collection(collection_name)
        # INFO: https://symfoware.blog.fc2.com/blog-entry-1436.html
        #    datetime: datetime.datetime(year=2019, month=10, day=1)
        records = collection.find(
            filter={'_id': {'$gte': start_dt, '$lt': end_dt}},
            sort=[('_id', ASCENDING)]
        )
        return [record for record in records]

    def bulk_insert(self, collection_name, dict_array):
        print('[Mongo] bulk_insert is starting ...')
        collection = self.database.get_collection(collection_name)
        collection.insert_many(dict_array)
        print('[Mongo] bulk_insert is finished !')

def main():
    accessor = MongoDBAccessor(db_name='candles')
    gbp_m10_candles = pd.read_csv('log/candles_GBP_JPY_M10.csv', parse_dates=[0])
    gbp_m10_candles.columns = ['_id', 'close', 'high', 'low', 'open']
    m10_dict = gbp_m10_candles.to_dict('records')

    # accessor.bulk_insert(collection_name='gbp', dict_array=m10_dict)
    # res = accessor.query_by_datetime('gbp', datetime.datetime(year=2010, month=10, day=1), datetime.datetime(year=2019, month=11, day=16))
    # import pdb; pdb.set_trace()


if __name__ == '__main__':
    main()
