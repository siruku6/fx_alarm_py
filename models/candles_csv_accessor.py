import datetime
import pandas as pd


class CandlesCsvAccessor():
    FILEPATH_HEAD = 'log/candles'
    DATETIME_FMT = '%Y-%m-%d %H:%M:%S'

    def __init__(self, granularity, currency_pare):
        self._csv_path = '{head}_{inst}_{granularity}.csv'.format(
            head=CandlesCsvAccessor.FILEPATH_HEAD,
            inst=currency_pare,
            granularity=granularity
        )
        try:
            self._candles = pd.read_csv(self._csv_path, index_col=0)
        except FileNotFoundError as _error:
            print(_error)
            self._candles = pd.DataFrame([])

    def query_candles(self, start_dt=None, end_dt=None):
        '''
        Return
            DataFrame
                columns -> time(index) |  close  |   high  |   low   |   open  |
                type    ->   string    | float64 | float64 | float64 | float64 |
        '''
        if start_dt is None and end_dt is None:
            return self._candles.copy()
        else:
            start_str = self.__datetime_to_str(start_dt)
            end_str = self.__datetime_to_str(end_dt)
            return self._candles[start_str:end_str].copy()

    def edge_datetimes_of(self):
        '''
        Summary
            return two datetimes, both edges of stocked candles
            if nothing is stocked, return two datetimes of now
        Return
            [datetime, datetime]
        '''
        if self._candles.empty:
            first = datetime.datetime.now()
            last = first
        else:
            first = self.__str_to_datetime(self._candles.index[0])
            last = self.__str_to_datetime(self._candles.index[-1])
        return first, last

    def bulk_insert(self, original_candles):
        if type(original_candles) is dict:
            candles_supplement = pd.DataFrame.from_dict(original_candles)
        else:
            candles_supplement = original_candles
        full_candles = candles_supplement.combine_first(self._candles)
        full_candles.to_csv(self._csv_path)
        self._candles = full_candles

    def __str_to_datetime(self, time_string):
        return datetime.datetime.strptime(time_string, CandlesCsvAccessor.DATETIME_FMT)

    def __datetime_to_str(self, time):
        return datetime.datetime.strftime(time, CandlesCsvAccessor.DATETIME_FMT)
