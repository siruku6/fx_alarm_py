from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from aws_lambda_powertools import Logger
from oanda_accessor_pyv20 import OandaInterface
import pandas as pd

from src.candle_storage import FXBase
from src.clients.dynamodb_accessor import DynamodbAccessor
import src.lib.format_converter as converter
import src.lib.interface as i_face
from src.trader_config import TraderConfig

LOGGER = Logger()


class CandleLoader:
    def __init__(self, config: TraderConfig, interface: OandaInterface, days: int) -> None:
        self.config: TraderConfig = config
        self.interface: OandaInterface = interface
        self.need_request: bool = self.__select_need_request(operation=config.operation)
        self.days: int = days

    def run(self) -> Dict[str, Optional[str]]:
        candles: pd.DataFrame
        if self.need_request is False:
            candles = pd.read_csv("tests/fixtures/sample_candles.csv")
        elif self.config.operation in ("backtest", "forward_test"):
            candles = self.interface.load_candles_by_days(
                days=self.days,
                granularity=self.config.get_entry_rules("granularity"),  # type: ignore
            )["candles"]
        elif self.config.operation == "live":
            candles = self.interface.load_specify_length_candles(
                length=70, granularity=self.config.get_entry_rules("granularity")  # type: ignore
            )["candles"]
        else:
            raise ValueError(f"trader_config.operation is invalid!: {self.config.operation}")

        FXBase.set_candles(candles)
        if self.need_request is False:
            return {"info": None}

        latest_candle: Dict[str, Any] = self.interface.call_oanda("current_price")
        LOGGER.info({"latest_candle": latest_candle})
        self.__update_latest_candle(latest_candle)
        return {"info": None}

    def __select_need_request(self, operation: str) -> bool:
        need_request: bool = True
        if operation in ("backtest", "forward_test"):
            need_request = i_face.ask_true_or_false(
                msg="[Trader] Which do you use ?  [1]: current_candles, [2]: static_candles :"
            )
        elif operation == "unittest":
            need_request = False
        return need_request

    def load_long_span_candles(self) -> None:
        long_span_candles: pd.DataFrame
        if self.need_request is False:
            long_span_candles = pd.read_csv("tests/fixtures/sample_candles_h4.csv")
        else:
            long_span_candles = self.__load_long_chart(granularity="D")

        long_span_candles["time"] = pd.to_datetime(long_span_candles["time"])
        long_span_candles.set_index("time", inplace=True)
        FXBase.set_long_span_candles(long_span_candles)
        # long_span_candles.resample('4H').ffill() # upsamplingしようとしたがいらなかった。

    def __load_long_chart(self, granularity: Optional[str] = None) -> pd.DataFrame:
        if granularity is None:
            granularity: str = self.config.get_entry_rules("granularity")  # type: ignore
        if self.days is None:
            raise RuntimeError("'days' must be specified, but is None.")

        return self.interface.load_candles_by_days(days=self.days, granularity=granularity)[
            "candles"
        ]

    def __update_latest_candle(self, latest_candle: Dict[str, Any]) -> None:
        """
        Update the latest candle,
        if either end of the new latest candle is beyond either end of old latest candle
        """
        candle_dict = FXBase.get_candles().iloc[-1].to_dict()
        FXBase.replace_latest_price("close", latest_candle["close"])
        if candle_dict["high"] < latest_candle["high"]:
            FXBase.replace_latest_price("high", latest_candle["high"])
        if candle_dict["low"] > latest_candle["low"]:
            FXBase.replace_latest_price("low", latest_candle["low"])
        LOGGER.info(
            {
                "[Client] Last_H4": candle_dict,
                "Current_M1": latest_candle,
                "[Client] New_H4": FXBase.get_candles().iloc[-1].to_dict(),
            }
        )

    def load_candles_by_duration_for_hist(
        self, instrument: str, start: datetime, end: datetime, granularity: str
    ) -> pd.DataFrame:
        """Prepare candles with specifying the range of datetime"""
        # 1. query from DynamoDB
        table_name: str = "{}_CANDLES".format(granularity)
        dynamo = DynamodbAccessor(instrument, table_name=table_name)
        candles: pd.DataFrame = dynamo.list_candles(
            # INFO: now preparing a little wide range of candles
            #   because 休日やらタイミングやらで、start, endを割り込むデータしか取得できないことがあるため
            # TODO: not using `3`days, it seems better to alter number of days according to granurality
            (start - timedelta(days=3)).isoformat(),
            (end + timedelta(days=1)).isoformat(),
        )
        if self.interface.accessable is False:
            print("[Manager] Skipped requesting candles from Oanda")
            return candles

        # 2. detect period of missing candles
        missing_start, missing_end = self.__detect_missings(candles, start, end)
        if missing_end <= missing_start:
            return candles

        # 3. complement missing candles using API
        missed_candles: pd.DataFrame = self.interface.load_candles_by_duration(
            missing_start, missing_end, granularity=granularity
        )["candles"]
        # INFO: If it is closed time between start and end, `missed_candles` is gonna be [].
        #   Then, skip insert and union.
        if len(missed_candles) > 0:
            dynamo.batch_insert(items=missed_candles.copy())
            candles = self.interface._OandaInterface__union_candles_distinct(
                candles, missed_candles
            )

        return candles

    def __detect_missings(
        self, candles: pd.DataFrame, required_start: datetime, required_end: datetime
    ) -> Tuple[datetime, datetime]:
        """
        Parameters
        ----------
        candles : pandas.DataFrame
            Columns :

        required_start : datetime
            Example : datetime(2020, 1, 2, 12, 34)
        required_end : datetime

        Returns
        -------
        Array: [missing_start, missing_end]
            missing_start : datetime
            missing_end : datetime
        """
        if len(candles) == 0:
            return required_start, required_end

        # 1. DBから取得したデータの先頭と末尾の日時を取得
        stocked_first: datetime = converter.str_to_datetime(candles.iloc[0]["time"])
        stocked_last: datetime = converter.str_to_datetime(candles.iloc[-1]["time"])
        ealiest: datetime = min(required_start, required_end, stocked_first, stocked_last)
        latest: datetime = max(required_start, required_end, stocked_first, stocked_last)

        # 2. どの期間のデータが不足しているのかを判別
        missing_start: datetime = required_start if ealiest == required_start else stocked_last
        missing_end: datetime = required_end if latest == required_end else stocked_first
        return missing_start, missing_end
