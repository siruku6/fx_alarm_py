from typing import Any, Dict, Optional

from aws_lambda_powertools import Logger
import pandas as pd

from src.candle_storage import FXBase
from src.client_manager import ClientManager
import src.lib.interface as i_face
from src.trader_config import TraderConfig

LOGGER = Logger()


class CandleLoader:
    def __init__(self, config: TraderConfig, client_manager: ClientManager, days: int) -> None:
        self.config: TraderConfig = config
        self.client_manager: ClientManager = client_manager
        self.need_request: bool = self.__select_need_request(operation=config.operation)
        self.days: int = days

    def run(self) -> Dict[str, Optional[str]]:
        candles: pd.DataFrame
        if self.need_request is False:
            candles = pd.read_csv("tests/fixtures/sample_candles.csv")
        elif self.config.operation in ("backtest", "forward_test"):
            # TODO: move to trade_lab or trader_config
            self.config.set_entry_rules("granularity", value=i_face.ask_granularity())
            candles = self.client_manager.load_long_chart(
                days=self.days,  # self.config.get_entry_rules("days"),  # type: ignore
                granularity=self.config.get_entry_rules("granularity"),  # type: ignore
            )["candles"]
        elif self.config.operation == "live":
            candles = self.client_manager.load_specify_length_candles(
                length=70, granularity=self.config.get_entry_rules("granularity")  # type: ignore
            )["candles"]
        else:
            raise ValueError(f"trader_config.operation is invalid!: {self.config.operation}")

        FXBase.set_candles(candles)
        if self.need_request is False:
            return {"info": None}

        latest_candle: Dict[str, Any] = self.client_manager.call_oanda("current_price")
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

    def __load_long_chart(self, granularity: str = None) -> pd.DataFrame:
        if granularity is None:
            granularity: str = self.config.get_entry_rules("granularity")  # type: ignore
        if self.days is None:
            raise RuntimeError("'days' must be specified, but is None.")

        return self.client_manager.load_long_chart(days=self.days, granularity=granularity)[
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
        LOGGER.info({"[Client] Last_H4": candle_dict, "Current_M1": latest_candle})
        LOGGER.info({"[Client] New_H4": FXBase.get_candles().iloc[-1].to_dict()})
