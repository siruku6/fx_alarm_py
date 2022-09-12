from typing import Optional, List

import pandas as pd

CANDLE_COLUMN_LIST: List[str] = [
    "open",
    "high",
    "low",
    "close",
    "time",
]


class FXBase:
    __candles: Optional[pd.DataFrame] = None
    __long_span_candles: Optional[pd.DataFrame] = None

    # candles
    @classmethod
    def get_candles(cls, start: int = 0, end: Optional[int] = None) -> pd.DataFrame:
        if cls.__candles is None:
            return pd.DataFrame(columns=[])
        return cls.__candles[start:end]

    @classmethod
    def set_time_id(cls) -> None:
        cls.__candles["time_id"] = cls.get_candles().index + 1  # type: ignore

    @classmethod
    def set_candles(cls, candles: pd.DataFrame) -> None:
        available_column_list: List[str] = candles.columns
        # TODO: check the type of each column
        for necessary_column in CANDLE_COLUMN_LIST:
            if necessary_column not in available_column_list:
                raise ValueError(f'There is not the column "{necessary_column}" in your candles !')
        cls.__candles = candles

    @classmethod
    def replace_latest_price(cls, price_type: str, new_price: float) -> None:
        column_num = cls.__candles.columns.get_loc(price_type)
        cls.__candles.iat[-1, column_num] = new_price

    @classmethod
    def write_candles_on_csv(cls, filename: str = "./tmp/candles.csv") -> None:
        cls.__candles.to_csv(filename)

    # D1 or H4 candles
    @classmethod
    def get_long_span_candles(cls) -> pd.DataFrame:
        return cls.__long_span_candles

    @classmethod
    def set_long_span_candles(cls, long_span_candles: pd.DataFrame) -> None:
        cls.__long_span_candles = long_span_candles
