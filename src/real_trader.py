import datetime
from pprint import pprint
from typing import Any, Callable, TypedDict, Union

import numpy as np
import pandas as pd

from src.candle_storage import FXBase
import src.trade_rules.scalping as scalping
import src.trade_rules.stoploss as stoploss_strategy
from src.trader import Trader


class PositionRequired(TypedDict):
    """Required keys"""

    type: str


class Position(PositionRequired, total=False):
    """Optional keys"""

    price: float
    openTime: str
    stoploss: float


class RealTrader(Trader):
    """This class orders trading to Oanda following trading rules."""

    def __init__(self, operation):
        print("[Trader] -------- start --------")
        super(RealTrader, self).__init__(operation=operation, days=60)

        self._position: Position = {"type": "none"}
        # self._set_position({'type': 'none'})

    @property
    def stoploss_method(
        self,
    ) -> Union[Callable[[str, float, float], float], Callable[[str, float, float, Any], float]]:
        return stoploss_strategy.STRATEGIES[self.config.stoploss_strategy_name]

    #
    # Public
    #
    def apply_trading_rule(self):
        candles = FXBase.get_candles().copy()
        self._prepare_trade_signs(candles)
        candles["preconditions_allows"] = np.all(
            candles[self.config.get_entry_rules("entry_filters")], axis=1
        )
        # candles = self._merge_long_indicators(candles) # already merged on Trader.__init__()
        # self.__play_swing_trade(candles)
        self.__play_scalping_trade(candles)

    def _set_position(self, position_dict: Position):
        self._position: Position = position_dict

    #
    # Override shared methods
    #
    def _create_position(self, previous_candle, direction, last_indicators=None):
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

        self._client.order_oanda(method_type="entry", posi_nega_sign=sign, stoploss_price=stoploss)

    def _trail_stoploss(self, new_stop):
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
        self._client.order_oanda(method_type="trail", stoploss_price=new_stop)

    def __settle_position(self, reason=""):
        """ポジションをcloseする"""
        pprint(self._client.order_oanda(method_type="exit", reason=reason))

    #
    # Private
    #
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    #                       Swing
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def __play_swing_trade(self, candles):
        """現在のレートにおいて、スイングトレードルールでトレード"""
        last_candle = candles.iloc[-1, :]

        self._set_position(self.__fetch_current_position())
        if self._position["type"] == "none":
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
            new_stop = self.__drive_trail_process(candles.iloc[-2, :], self._indicators.iloc[-1])

        print(
            "[Trader] position: {}, possible_SL: {}, stoploss: {}".format(
                self._position["type"],
                new_stop if "new_stop" in locals() else "-",
                self._position.get("stoploss", None),
            )
        )
        return None

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    #                       Scalping
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def __play_scalping_trade(self, candles):
        """Trade with scalping rule"""
        indicators = self._indicators
        last_candle = candles.iloc[-1]
        last_indicators = indicators.iloc[-1]

        self._set_position(self.__fetch_current_position())

        if self._position["type"] != "none":
            new_stop: float = self.__drive_trail_process(candles.iloc[-2], last_indicators)
            self.__drive_exit_process(self._position["type"], indicators, last_candle)
        else:
            self.__drive_entry_process(candles, last_candle, indicators, last_indicators)

        print(
            "[Trader] position: {}, possible_SL: {}, stoploss: {}".format(
                self._position["type"],
                new_stop if "new_stop" in locals() else "-",
                self._position.get("stoploss", None),
            )
        )
        return None

    def __drive_entry_process(self, candles, last_candle, indicators, last_indicators):
        if self.__since_last_loss() < datetime.timedelta(hours=1):
            print("[Trader] skip: An hour has not passed since last loss.")
            return False
        elif not candles["preconditions_allows"].iat[-1] or last_candle.trend is None:
            self.__show_why_not_entry(candles)
            return False

        direction = scalping.repulsion_exist(
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
            return False
        # INFO: exitサインが出ているときにエントリーさせない場合はコメントインする
        # if self.__drive_exit_process(direction, last_indicators, last_candle, preliminary=True):
        #     return False

        # last_index = len(indicators) - 1
        self._create_position(candles.iloc[-2], direction, last_indicators)
        return direction

    def __drive_trail_process(
        self, previous_candle: pd.Series, last_indicators: pd.Series
    ) -> float:
        old_stoploss: float = self._position.get("stoploss", np.nan)
        possible_stoploss: float = self.stoploss_method(
            position_type=self._position["type"],
            previous_low=previous_candle["low"],
            previous_high=previous_candle["high"],
            config=self.config,
            current_sup=last_indicators["support"],
            current_regist=last_indicators["regist"],
        )
        if self.__new_stoploss_is_closer(self._position["type"], possible_stoploss, old_stoploss):
            self._trail_stoploss(new_stop=possible_stoploss)
        else:
            possible_stoploss = old_stoploss

        return possible_stoploss

    def __new_stoploss_is_closer(self, position_type, possible_stoploss, old_stoploss):
        if position_type in ["long", "short"] and old_stoploss in [np.nan, None]:
            return True

        return ((position_type == "long") and (possible_stoploss > old_stoploss)) or (
            (position_type == "short") and (possible_stoploss < old_stoploss)
        )

    def __drive_exit_process(self, position_type, indicators, last_candle, preliminary=False):
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
                return True

            reason = "stoc crossed at {} ! position_type: {}".format(
                last_candle["time"], position_type
            )
            self.__settle_position(reason=reason)

    def __fetch_current_position(self) -> Position:
        pos: Position = {"type": "none"}
        open_trades = self._client.call_oanda("open_trades")
        if open_trades == []:
            return pos

        # Extract only the necessary information of open position
        target = open_trades[0]
        pos["price"] = float(target["price"])
        pos["openTime"] = target["openTime"]
        if target["currentUnits"][0] == "-":
            pos["type"] = "short"
        else:
            pos["type"] = "long"
        if "stopLossOrder" not in target:
            return pos

        pos["stoploss"] = float(target["stopLossOrder"]["price"])
        return pos

    def __since_last_loss(self):
        """
        Return the elapsed time since the most recent lose

        Parameters
        ----------
        None

        Returns
        -------
        time_since_loss : datetime
        """
        candle_size = 100
        hist_df = self._client.call_oanda("transactions", count=candle_size)
        time_series = hist_df[hist_df.pl < 0]["time"]
        if time_series.empty:
            return datetime.timedelta(hours=99)

        last_loss_time = time_series.iat[-1]
        last_loss_datetime = datetime.datetime.strptime(
            last_loss_time.replace("T", " ")[:16], "%Y-%m-%d %H:%M"
        )
        time_since_loss = datetime.datetime.utcnow() - last_loss_datetime
        return time_since_loss

    def __show_why_not_entry(self, conditions_df):
        time = conditions_df.time.values[-1]
        if conditions_df.trend.iat[-1] is None:
            self._log_skip_reason('c. {}: "trend" is None !'.format(time))

        columns = self.config.get_entry_rules("entry_filters")
        vals = conditions_df[columns].iloc[-1].values
        for reason, val in zip(columns, vals):
            if not val:
                self._log_skip_reason('c. {}: "{}" is not satisfied !'.format(time, reason))

    def _generate_entryable_price(self, _) -> np.ndarray:
        pass
