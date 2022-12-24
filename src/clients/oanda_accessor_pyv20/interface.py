from collections.abc import Callable
from datetime import datetime, timedelta
import time
from typing import Any, Dict, List, Union
import warnings

import pandas as pd

from src.clients import sns
from src.clients.oanda_accessor_pyv20.api import OandaClient
import src.clients.oanda_accessor_pyv20.preprocessor as prepro
import src.lib.format_converter as converter

# pd.set_option('display.max_rows', candles_count)  # 表示可能な最大行数を設定


class OandaInterface:
    def __init__(self, instrument: str, test: bool = False) -> None:
        self.__instrument: str = instrument
        self.__oanda_client: OandaClient = OandaClient(instrument=self.__instrument, test=test)

    def accessable(self) -> bool:
        return self.__oanda_client.accessable

    # INFO: request-candles
    def load_specify_length_candles(
        self, length: int = 60, granularity: str = "M5"
    ) -> Dict[str, Union[str, pd.DataFrame]]:
        """
        load candles for specified length
        """
        response = self.__oanda_client.query_instruments(
            candles_count=length,
            granularity=granularity,
        )

        candles = prepro.to_candle_df(response)
        return {"success": "[Watcher] Succeeded to request to Oanda", "candles": candles}

    def load_candles_by_days(
        self, days: int = 0, granularity: str = "M5", sleep_time: float = 1.0
    ) -> Dict[str, Union[str, pd.DataFrame]]:
        """
        load long days candles using multiple API requests

        Parameters
        ----------
        days : int
            days you would
        granularity : str
            Example: "H1" or "D"

        Returns
        ----------
        Dict[str, Union[str, pd.DataFrame]]:
            {
                "success": "message",
                "candles": <loaded candles>,
            }
        """
        remaining_days = days
        candles = None
        requestable_max_days = self.__calc_requestable_max_days(granularity=granularity)

        last_datetime = datetime.utcnow()
        while remaining_days > 0:
            start_datetime = last_datetime - timedelta(days=remaining_days)
            remaining_days -= requestable_max_days
            if remaining_days < 0:
                remaining_days = 0
            end_datetime = last_datetime - timedelta(days=remaining_days)

            response = self.__oanda_client.query_instruments(
                start=prepro.to_oanda_format(start_datetime),
                end=prepro.to_oanda_format(end_datetime),
                granularity=granularity,
            )
            tmp_candles = prepro.to_candle_df(response)
            candles = self.__union_candles_distinct(candles, tmp_candles)
            print(
                "[OandaInterface] Remaining: {remaining_days} days".format(
                    remaining_days=remaining_days
                )
            )
            time.sleep(sleep_time)

        return {"success": "[OandaInterface] Succeeded to request API", "candles": candles}

    def load_candles_by_duration(
        self, start: datetime, end: datetime, granularity: str, sleep_time: float = 1.0
    ) -> Dict[str, Union[str, pd.DataFrame]]:
        """
        load candles for a specified time period using multiple API requests

        Parameters
        ----------
        start : datetime
            the start of time period for candles you want
        end : datetime
            the end of time period for candles you want
        granularity : str
            Example: "H1" or "D"

        Returns
        ----------
        Dict[str, Union[str, pd.DataFrame]]:
            {
                "success": "message",
                "candles": <loaded candles>,
            }
        """
        candles = None
        requestable_duration = self.__calc_requestable_time_duration(granularity)
        next_starttime: datetime = start
        next_endtime: datetime = self.__minimize_period(start, end, requestable_duration)

        while next_starttime < end:
            now = datetime.utcnow() - timedelta(minutes=1)
            if now < next_endtime:
                next_endtime = now
            response = self.__oanda_client.query_instruments(
                start=prepro.to_oanda_format(next_starttime),
                end=prepro.to_oanda_format(next_endtime),
                granularity=granularity,
            )
            tmp_candles = prepro.to_candle_df(response)
            candles = self.__union_candles_distinct(candles, tmp_candles)
            print("Loaded: up to {datetime}".format(datetime=next_endtime))
            time.sleep(sleep_time)

            next_starttime += requestable_duration
            next_endtime += requestable_duration

        return {"success": "[OandaInterface] Succeeded to request API", "candles": candles}

    def __minimize_period(
        self, start: datetime, end: datetime, requestable_duration: timedelta
    ) -> datetime:
        possible_end: datetime = start + requestable_duration
        next_end: datetime = possible_end if possible_end < end else end
        return next_end

    def call_oanda(self, method_type: str, **kwargs: Dict[str, Any]):
        warnings.warn(
            "'call_oanda' is going to be replaced into other method in the future.",
            FutureWarning,
        )

        method_dict: Dict[str, Union[Callable[[Any], Any], Callable[[], Any]]] = {
            "is_tradeable": self.__oanda_client.request_is_tradeable,
            "open_trades": self.__oanda_client.request_open_trades,
            "transactions": self.__request_latest_transactions,
            "current_price": self.request_current_price,
        }
        return method_dict.get(method_type)(**kwargs)

    def order_oanda(self, method_type: str, **kwargs: Dict[str, Any]) -> dict:
        warnings.warn(
            "'order_oanda' is going to be replaced into other method in the future.",
            FutureWarning,
        )

        method_dict: Dict[str, Callable[[Any], Dict[str, Any]]] = {
            "entry": self.__oanda_client.request_market_ordering,
            "trail": self.__oanda_client.request_trailing_stoploss,
            "exit": self.__oanda_client.request_closing,
        }
        result: dict = method_dict.get(method_type)(**kwargs)
        if method_type == "entry" or method_type == "exit":
            sns.publish(result, "Message: {} is done !".format(method_type))
        return result

    def request_current_price(self) -> Dict[str, Any]:
        # INFO: .to_dict() just make Return easy to read for you
        latest_candle: Dict[str, Any] = (
            self.load_specify_length_candles(length=1, granularity="M1")["candles"]  # type: ignore
            .iloc[-1]
            .to_dict()
        )
        return latest_candle

    def prepare_one_page_transactions(self) -> pd.DataFrame:
        """
        preapre history_df: trade-history
        """
        history_df: pd.DataFrame = self.__request_latest_transactions()
        history_df.to_csv("./tmp/csvs/hist_positions.csv", index=False)
        return history_df

    def request_massive_transactions(self, from_str: str, to_str: str) -> pd.DataFrame:
        gained_transactions = []

        from_id: str
        to_id: str
        from_id, to_id = self.__oanda_client.request_transaction_ids(from_str, to_str)
        if from_id is None or to_id is None:
            return pd.DataFrame([])

        while True:
            print("[INFO] requesting {}..{}".format(from_id, to_id))

            response = self.__oanda_client.request_transactions_once(from_id, to_id)
            tmp_transactons = response["transactions"]
            gained_transactions += tmp_transactons

            # INFO: ループの終了条件
            #   'to' に指定した ID の transaction がない時が多々あり、
            #   その場合、transactions を取得できないので、ごくわずかな数になる。
            #   そこまで来たら処理終了
            if len(tmp_transactons) <= 10 or str(int(tmp_transactons[-1]["id"]) + 1) >= to_id:
                break

            gained_last_transaction_id: str = tmp_transactons[-1]["id"]
            print("[INFO] last_transaction_id {}".format(gained_last_transaction_id))
            from_id = str(int(gained_last_transaction_id) + 1)

        filtered_df = prepro.filter_and_make_df(gained_transactions, self.__instrument)
        return filtered_df

    def __request_latest_transactions(self, count: int = 999) -> pd.DataFrame:
        result: Dict[str, Union[List[dict], str]] = self.__oanda_client.request_open_trades()
        last_transaction_id: str = result["last_transaction_id"]
        to_id = int(last_transaction_id)
        from_id = to_id - count
        from_id = max(from_id, 1)
        response = self.__oanda_client.request_transactions_once(from_id, to_id)
        filtered_df = prepro.filter_and_make_df(response["transactions"], self.__instrument)
        return filtered_df

    def __calc_requestable_max_days(self, granularity: str = "M5") -> int:
        candles_per_a_day: int = self.__calc_candles_wanted(days=1, granularity=granularity)

        # http://developer.oanda.com/rest-live-v20/instrument-ep/
        max_days: int = int(OandaClient.REQUESTABLE_COUNT / candles_per_a_day)
        return max_days

    def __calc_candles_wanted(self, days: int = 1, granularity: str = "M5") -> int:
        time_unit = granularity[0]
        if time_unit == "D":
            return int(days)

        time_span = int(granularity[1:])
        if time_unit == "H":
            result = int(days * 24 / time_span)
        elif time_unit == "M":
            result = int(days * 24 * 60 / time_span)
        return result

    def __calc_requestable_time_duration(self, granularity: str) -> timedelta:
        _timedelta: timedelta = converter.granularity_to_timedelta(granularity)
        requestable_duration: timedelta = _timedelta * (OandaClient.REQUESTABLE_COUNT - 1)

        return requestable_duration

    def __union_candles_distinct(
        self, old_candles: pd.DataFrame, new_candles: pd.DataFrame
    ) -> pd.DataFrame:
        if old_candles is None:
            return new_candles

        return (
            pd.concat([old_candles, new_candles])
            .drop_duplicates(subset="time")
            .sort_values(by="time", ascending=True)
            .reset_index(drop=True)
        )
