import pandas as pd


class FXBase():
    __candles = None
    __long_span_candles = None

    # candles
    @classmethod
    def get_candles(cls, start=0, end=None):
        if cls.__candles is None:
            return pd.DataFrame(columns=[])
        return cls.__candles[start:end]

    @classmethod
    def set_time_id(cls):
        cls.__candles['time_id'] = cls.get_candles().index + 1

    @classmethod
    def set_candles(cls, candles):
        cls.__candles = candles

    @classmethod
    def replace_latest_price(cls, price_type, new_price):
        column_num = cls.__candles.columns.get_loc(price_type)
        cls.__candles.iat[-1, column_num] = new_price

    @classmethod
    def write_candles_on_csv(cls, filename='./tmp/candles.csv'):
        cls.__candles.to_csv(filename)

    # D1 or H4 candles
    @classmethod
    def get_long_span_candles(cls):
        return cls.__long_span_candles

    @classmethod
    def set_long_span_candles(cls, long_span_candles):
        cls.__long_span_candles = long_span_candles
