import dataclasses
from datetime import datetime, timedelta
from pprint import pprint
from typing import Any, Callable, Dict, List, Literal, Optional, Union

from aws_lambda_powertools import Logger
import numpy as np
import pandas as pd

from src.candle_storage import FXBase
from src.clients import sns
from src.data_factory_clerk import prepare_indicators
import src.trade_rules.scalping as scalping
import src.trade_rules.stoploss as stoploss_strategy
from src.trader import Trader

LOGGER = Logger()
PositionType = Literal["long", "short"]


@dataclasses.dataclass
class Position:
    id: Optional[str]
    type: PositionType
    price: Optional[float]
    openTime: Optional[str]
    stoploss: Optional[float]

    # @classmethod
    # def init(
    #     cls,
    #     type,
    #     id: Optional[str] = None,
    #     price: Optional[float] = None,
    #     openTime: Optional[str] = None,
    #     stoploss: Optional[float] = None,
    # ):
    #     position: Position = Position(
    #         id=id,
    #         type=type,
    #         price=price,
    #         openTime=openTime,
    #         stoploss=stoploss,
    #     )
    #     return position


class RealTrader(Trader):
    """This class orders trading to Oanda following trading rules."""

    def __init__(self, **kwargs: Dict[str, Any]) -> None:
        print("[Trader] -------- start --------")
        super(RealTrader, self).__init__(**kwargs)

        self._positions: List[Optional[Position]] = []

    def stoploss_method(
        self,
    ) -> Union[Callable[[str, float, float], float], Callable[[str, float, float, Any], float]]:
        return stoploss_strategy.STRATEGIES[self.config.stoploss_strategy_name]

    #
    # Public
    #
    def apply_trading_rule(self) -> None:
        indicators = prepare_indicators()
        candles = FXBase.get_candles().copy()
        self._prepare_trade_signs("scalping", candles, indicators)
        candles["preconditions_allows"] = np.all(
            candles[self.config.get_entry_rules("entry_filters")], axis=1
        )
        # candles = self._merge_long_indicators(candles) # already merged on Trader.__init__()
        # self.__play_swing_trade(candles)
        self.__play_scalping_trade(candles, indicators)

    def _set_positions(self, positions: List[Optional[Position]]) -> None:
        self._positions = positions

    #
    # Override shared methods
    #
    def _create_position(
        self, previous_candle: pd.Series, direction: str, last_indicators: pd.Series = None
    ) -> None:
        """
        Order Oanda to create position
        """
        if direction == "long":
            sign = ""
            stoploss = previous_candle["low"] - self.config.stoploss_buffer_pips
            if last_indicators is not None:
                stoploss = last_indicators["support"]
        elif direction == "short":
            sign = "-"
            stoploss = (
                previous_candle["high"]
                + self.config.stoploss_buffer_pips
                + self.config.static_spread
            )
            if last_indicators is not None:
                stoploss = last_indicators["regist"]

        result: dict = self._oanda_interface.order_oanda(
            method_type="entry", posi_nega_sign=sign, stoploss_price=stoploss
        )
        LOGGER.info({"[Client] MarketOrder is done.": result["response"]})

        sns.publish(result, "Message: {} is done !".format("entry"))

    def _trail_stoploss(self, new_stop: float) -> None:
        """
        Order Oanda to trail stoploss-price
        Parameters
        ----------
        new_stop : float
            New stoploss price which is going to be set

        Returns
        -------
        None
        """
        # NOTE: trail先の価格を既に突破していたら自動でcloseしてくれた OandaAPI は優秀
        result: dict = self._oanda_interface.order_oanda(
            method_type="trail", trade_id=self._positions[-1].id, stoploss_price=new_stop
        )
        LOGGER.info({"[Client] trail": result})

    def __settle_position(self, reason: str = "") -> None:
        """ポジションをcloseする"""
        result: dict = self._oanda_interface.order_oanda(
            method_type="exit", trade_id=self._positions[-1].id, reason=reason
        )

        LOGGER.info({result["message"]: result["response"], "reason": result["reason"]})
        sns.publish(result, "Message: {} is done !".format("exit"))
        pprint(result)

    #
    # Private
    #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    #                       Swing
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def __play_swing_trade(
        self,
        candles: pd.DataFrame,
        indicators: pd.DataFrame,
    ) -> None:
        """現在のレートにおいて、スイングトレードルールでトレード"""
        last_candle = candles.iloc[-1, :]

        self._set_positions(self.__fetch_current_positions())
        if len(self._positions) == 0:
            entry_rules = [
                "sma_follow_trend",
                "band_expansion",
                "in_the_band",
                "ma_gap_expanding",
                "stoc_allows",
            ]
            self.config.set_entry_rules("entry_filters", value=entry_rules)
            precondition = np.all(candles[entry_rules], axis=1).iloc[-1]
            if last_candle["trend"] is None or not precondition:
                self.__show_why_not_entry(candles)
                return

            direction = last_candle["thrust"]
            if direction is None:
                return

            self._create_position(candles.iloc[-2], direction)
        else:
            new_stop = self.__drive_trail_process(
                self._positions[-1],  # type: ignore
                candles.iloc[-2, :],
                indicators.iloc[-1],
            )

        print(
            "[Trader] position: {}, possible_SL: {}, stoploss: {}".format(
                self._positions[-1].type,  # type: ignore
                new_stop if "new_stop" in locals() else "-",
                self._positions[-1].stoploss,  # type: ignore
            )
        )
        return None

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    #                       Scalping
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def __play_scalping_trade(
        self,
        candles: pd.DataFrame,
        indicators: pd.DataFrame,
    ) -> None:
        """
        Trade with scalping rule
        """
        last_candle: pd.Series = candles.iloc[-1]
        last_indicators: pd.Series = indicators.iloc[-1]

        self._set_positions(self.__fetch_current_positions())

        if len(self._positions) >= 1:
            new_stop: float = self.__drive_trail_process(
                self._positions[-1],  # type: ignore
                candles.iloc[-2],
                last_indicators,
            )
            self.__drive_exit_process(
                self._positions[-1].type,  # type: ignore
                indicators,
                last_candle,
            )
        else:
            self.__drive_entry_process(candles, last_candle, indicators, last_indicators)

        if len(self._positions) == 0:
            return None

        print(
            "[Trader] position: {}, possible_SL: {}, stoploss: {}".format(
                self._positions[-1].type,  # type: ignore
                new_stop if "new_stop" in locals() else "-",
                self._positions[-1].stoploss,  # type: ignore
            )
        )
        return None

    def __drive_entry_process(
        self,
        candles: pd.DataFrame,
        last_candle: pd.Series,
        indicators: pd.DataFrame,
        last_indicators: pd.Series,
    ) -> Optional[PositionType]:
        if self.__since_last_loss() < timedelta(hours=1):
            print("[Trader] skip: An hour has not passed since last loss.")
            return None
        elif not candles["preconditions_allows"].iat[-1] or last_candle.trend is None:
            self.__show_why_not_entry(candles)
            return None

        direction: Optional[PositionType] = scalping.repulsion_exist(
            trend=last_candle.trend,
            previous_ema=indicators["10EMA"].iat[-2],
            two_before_high=candles.high.iat[-3],
            previous_high=candles.high.iat[-2],
            two_before_low=candles.low.iat[-3],
            previous_low=candles.low.iat[-2],
        )
        if direction is None:
            print(
                "[Trader] repulsion is not exist Time: {}, 10EMA: {}".format(
                    last_candle.time, last_indicators["10EMA"]
                )
            )
            return None
        # INFO: exitサインが出ているときにエントリーさせない場合はコメントインする
        # if self.__drive_exit_process(direction, last_indicators, last_candle, preliminary=True):
        #     return False

        # last_index = len(indicators) - 1
        self._create_position(candles.iloc[-2], direction, last_indicators)
        return direction

    def __drive_trail_process(
        self, target_pos: Position, previous_candle: pd.Series, last_indicators: pd.Series
    ) -> float:
        old_stoploss: float = target_pos.stoploss or np.nan
        stoploss_func = self.stoploss_method()
        possible_stoploss: float = stoploss_func(
            position_type=target_pos.type,
            previous_low=previous_candle["low"],
            previous_high=previous_candle["high"],
            config=self.config,
            current_sup=last_indicators["support"],
            current_regist=last_indicators["regist"],
        )
        if self.__new_stoploss_is_closer(target_pos.type, possible_stoploss, old_stoploss):
            self._trail_stoploss(new_stop=possible_stoploss)
        else:
            possible_stoploss = old_stoploss

        return possible_stoploss

    def __new_stoploss_is_closer(
        self, position_type: str, possible_stoploss: float, old_stoploss: float
    ) -> bool:
        if position_type in ["long", "short"] and old_stoploss in [np.nan, None]:
            return True

        return ((position_type == "long") and (possible_stoploss > old_stoploss)) or (
            (position_type == "short") and (possible_stoploss < old_stoploss)
        )

    def __drive_exit_process(
        self,
        position_type: str,
        indicators: pd.DataFrame,
        last_candle: pd.Series,
        preliminary: bool = False,
    ) -> None:
        # plus_2sigma = last_indicators['sigma*2_band']
        # minus_2sigma = last_indicators['sigma*-2_band']
        # if scalping.is_exitable_by_bollinger(last_candle.close, plus_2sigma, minus_2sigma):

        current_indicator = indicators.iloc[-1].copy()
        current_indicator["stoD_over_stoSD"] = last_candle["stoD_over_stoSD"]
        previous_indicator = indicators.iloc[-2]

        # stod_over_stosd_on_long = last_candle['stoD_over_stoSD']
        if scalping.is_exitable(position_type, current_indicator, previous_indicator):
            # if scalping._exitable_by_long_stoccross(position_type, stod_over_stosd_on_long) \
            #         and scalping._exitable_by_stoccross(
            #             position_type, previous_indicator['stoD_3'], previous_indicator['stoSD_3']
            #         ):
            if preliminary:
                return

            reason = "stoc crossed at {} ! position_type: {}".format(
                last_candle["time"], position_type
            )
            self.__settle_position(reason=reason)

    def __fetch_current_positions(self) -> List[Optional[Position]]:
        result = self._oanda_interface.call_oanda("open_trades")
        LOGGER.info({"[Client] OpenTrades": result["response"]})

        positions: List[dict] = result["positions"]
        if positions == []:
            return []

        # Extract only the necessary information of open position
        target: dict = positions[0]
        if target["currentUnits"][0] == "-":
            position_type: str = "short"
        else:
            position_type = "long"

        if "stopLossOrder" not in target:
            sl_price: Optional[float] = None
        else:
            sl_price = float(target["stopLossOrder"]["price"])

        pos = {
            "id": target["id"],
            "price": float(target["price"]),
            "openTime": target["openTime"],
            "type": position_type,
            "stoploss": sl_price,
        }
        return [Position(**pos)]

    def __since_last_loss(self) -> timedelta:
        """
        Return the elapsed time since the most recent lose

        Parameters
        ----------
        None

        Returns
        -------
        time_since_loss : timedelta
        """
        candle_size = 100
        hist_df = self._oanda_interface.call_oanda("transactions", count=candle_size)
        LOGGER.info({"hist_df": hist_df})

        time_series = hist_df[hist_df.pl < 0]["time"]
        if time_series.empty:
            return timedelta(hours=99)

        last_loss_time = time_series.iat[-1]
        last_loss_datetime = datetime.strptime(
            last_loss_time.replace("T", " ")[:16], "%Y-%m-%d %H:%M"
        )
        time_since_loss = datetime.utcnow() - last_loss_datetime
        return time_since_loss

    def __show_why_not_entry(self, conditions_df: pd.DataFrame) -> None:
        time = conditions_df.time.values[-1]
        if conditions_df.trend.iat[-1] is None:
            msg: str = 'c. {}: "trend" is None !'.format(time)
            print("[Trader] skip: {}".format(msg))

        columns = self.config.get_entry_rules("entry_filters")
        vals = conditions_df[columns].iloc[-1].values
        for reason, val in zip(columns, vals):
            if not val:
                msg = 'c. {}: "{}" is not satisfied !'.format(time, reason)
                print("[Trader] skip: {}".format(msg))

    def _generate_entryable_price(self, _) -> np.ndarray:
        pass

    def backtest(
        self, candles: pd.DataFrame, indicators: pd.DataFrame
    ) -> Dict[str, Union[str, pd.DataFrame]]:
        pass
