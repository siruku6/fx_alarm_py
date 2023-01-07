import abc
from collections.abc import Callable
from typing import Dict, List, Union

import numpy as np
import pandas as pd

from src.candle_storage import FXBase
from src.lib.time_series_generator import prepare_indicators
import src.trade_rules.base as base_rules
from src.trader_config import FILTER_ELEMENTS

# pd.set_option('display.max_rows', 400)


class Trader(metaclass=abc.ABCMeta):
    TIME_STRING_FMT = "%Y-%m-%d %H:%M:%S"

    def __init__(
        self,
        o_interface,
        config,
        result_processor,
    ) -> None:
        """
        Parameters
        ----------
        operation : str
            Available Values: ['backtest', 'forward_test', 'live', 'unittest']
        days : Optional[int]

        Returns
        -------
        None
        """
        self._oanda_interface = o_interface
        self.config = config
        self._result_processor = result_processor

    #
    # public
    #
    def perform(self, rule: str = "swing", entry_filters: List[str] = []) -> pd.DataFrame:
        """automatically test trade rule"""
        # INFO: 繰り返しデモする場合に前回のpositionが残っているので、リセットする いらなくない？
        self._result_processor.reset_drawer()
        filters: List[str] = FILTER_ELEMENTS if entry_filters == [] else entry_filters
        self.config.set_entry_rules("entry_filters", value=filters)

        backtest: Callable[[pd.DataFrame], Dict[str, Union[str, pd.DataFrame]]]
        if rule in ("swing", "scalping"):
            backtest = self.backtest
        elif rule == "wait_close":
            backtest = self._backtest_wait_close
        else:
            print("Rule {} is not exist ...".format(rule))
            exit()

        # TODO: The order of these processings cannot be changed.
        #     But should be able to be changed.
        indicators: pd.DataFrame = prepare_indicators()
        candles: pd.DataFrame = FXBase.get_candles().copy()
        self._prepare_trade_signs(candles, indicators)

        result: Dict[str, Union[str, pd.DataFrame]] = backtest(candles, indicators)

        print("{} ... (perform)".format(result["result"]))
        df_positions: pd.DataFrame = self._result_processor.run(rule, result, indicators)
        return df_positions

    # @abc.abstractmethod
    # def backtest(self):
    #     pass

    @abc.abstractmethod
    def _generate_entryable_price(self, candles: pd.DataFrame) -> np.ndarray:
        """
        Generate possible prices assuming that entries are done

        Parameters
        ----------
        candles : pd.DataFrame
            Index:
                Any
            Columns:
                Name: open,      dtype: float64 (required)
                Name: high,      dtype: float64 (required)
                Name: low,       dtype: float64 (required)
                Name: entryable, dtype: object  (required)

        Returns
        -------
        np.ndarray
        """
        pass

    #
    # Methods for judging Entry or Close
    #
    def _generate_thrust_column(self, candles: pd.DataFrame, trend: pd.DataFrame, _) -> pd.Series:
        # INFO: the most highest or lowest in last 10 candles
        recent_highests: pd.Series = candles["high"] == candles["high"].rolling(window=3).max()
        recent_lowests: pd.Series = candles["low"] == candles["low"].rolling(window=3).min()

        up_thrusts: pd.Series = recent_highests & trend["bull"]
        down_thrusts: pd.Series = recent_lowests & trend["bear"]

        thrust_type_series: pd.Series = pd.Series(np.full(len(candles), None))
        thrust_type_series[up_thrusts] = "long"
        thrust_type_series[down_thrusts] = "short"
        return thrust_type_series

        # INFO: decide 'thrust' by only comparing with shift(1)
        # method_thrust_checker = np.frompyfunc(base_rules.detect_thrust, 5, 1)
        # result = method_thrust_checker(
        #     candles.trend,
        #     candles.high.shift(1), candles.high,
        #     candles.low.shift(1), candles.low
        # )
        # return result

    # 60EMA is necessary?
    def __generate_ema_allows_column(self, candles, indicators):
        ema60 = indicators["60EMA"]
        ema60_allows_bull = np.all(np.array([candles.bull, ema60 < candles.close]), axis=0)
        ema60_allows_bear = np.all(np.array([candles.bear, ema60 > candles.close]), axis=0)
        return np.any(np.array([ema60_allows_bull, ema60_allows_bear]), axis=0)

    def __generate_in_bands_column(
        self, candles: pd.DataFrame, indicators: pd.DataFrame
    ) -> np.ndarray:
        """
        Generate the column shows whether if the price is remaining between 2-sigma-bands
        """
        entryable_prices: Union[np.ndarray, pd.Series]
        if self.config.operation in ["live", "forward_test"]:
            entryable_prices = candles["close"]
        else:
            entryable_prices = self._generate_entryable_price(
                candles.rename(columns={"thrust": "entryable"})
            )

        df_over_band_detection = pd.DataFrame(
            {
                "under_positive_band": indicators["sigma*2_band"] > entryable_prices,
                "above_negative_band": indicators["sigma*-2_band"] < entryable_prices,
            }
        )
        return np.all(df_over_band_detection, axis=1)  # type: ignore

    def __generate_band_expansion_column(
        self, df_bands: pd.DataFrame, shift_size: int = 3
    ) -> pd.Series:
        """band が拡張していれば True を格納して numpy配列 を生成"""
        # OPTIMIZE: bandについては、1足前(shift(1))に広がっていることを条件にしてもよさそう
        #   その場合、広がっていることの確定を待つことになるので、条件としては厳しくなる
        bands_gap = df_bands["sigma*2_band"] - df_bands["sigma*-2_band"]  # .shift(1).fillna(0.0)
        return bands_gap.rolling(window=shift_size).max() == bands_gap
        # return bands_gap.shift(shift_size) < bands_gap

    def __generate_getting_steeper_column(
        self, df_trend: pd.DataFrame, indicators: pd.DataFrame
    ) -> np.ndarray:
        """移動平均が勢いづいているか否かを判定"""
        gap_of_ma: pd.Series = indicators["10EMA"] - indicators["20SMA"]
        result: pd.Series = gap_of_ma.shift(1) < gap_of_ma

        # INFO: 上昇方向に勢いづいている
        is_long_steeper: pd.Series = df_trend["bull"].fillna(False) & result
        # INFO: 下降方向に勢いづいている
        is_short_steeper: pd.Series = df_trend["bear"].fillna(False) & np.where(result, False, True)

        return np.any([is_long_steeper, is_short_steeper], axis=0)  # type: ignore

    def __generate_following_trend_column(
        self, df_trend: pd.DataFrame, series_sma: pd.Series
    ) -> np.ndarray:
        """移動平均線がtrendに沿う方向に動いているか判定する列を返却"""
        # series_sma = indicators["20SMA"].copy()
        df_tmp = df_trend.copy()
        df_tmp["sma_up"] = series_sma.shift(1) < series_sma
        df_tmp["sma_down"] = series_sma.shift(1) > series_sma

        both_up: np.ndarray = np.all(df_tmp[["bull", "sma_up"]], axis=1)
        both_down: np.ndarray = np.all(df_tmp[["bear", "sma_down"]], axis=1)
        return np.any([both_up, both_down], axis=0)  # type: ignore

    #
    # private
    #
    def _prepare_trade_signs(self, candles: pd.DataFrame, indicators: pd.DataFrame) -> None:
        print("[Trader] preparing base-data for judging ...")

        candles["trend"] = base_rules.generate_trend_column(indicators, candles.close)
        trend = pd.DataFrame(
            {
                "bull": np.where(candles["trend"] == "bull", True, False),
                "bear": np.where(candles["trend"] == "bear", True, False),
            }
        )
        # NOTE: _generate_thrust_column varies by the super class
        candles["thrust"] = self._generate_thrust_column(candles, trend, indicators)
        # 60EMA is necessary?
        # candles['ema60_allows'] = self.__generate_ema_allows_column(candles=candles)
        candles["in_the_band"] = self.__generate_in_bands_column(candles, indicators)
        candles["band_expansion"] = self.__generate_band_expansion_column(
            df_bands=indicators[["sigma*2_band", "sigma*-2_band"]]
        )
        candles["ma_gap_expanding"] = self.__generate_getting_steeper_column(trend, indicators)
        candles["sma_follow_trend"] = self.__generate_following_trend_column(
            trend, indicators["20SMA"]
        )
        candles["stoc_allows"] = base_rules.generate_stoc_allows_column(
            indicators, sr_trend=candles["trend"]
        )
        self._mark_entryable_rows(candles)  # This needs 'thrust'

    def _mark_entryable_rows(self, candles: pd.DataFrame) -> None:
        """
        Judge whether it is entryable or not on each row.
        Then set the result in the column 'entryable'.
        """
        entryable = np.all(candles[self.config.get_entry_rules("entry_filters")], axis=1)
        candles.loc[entryable, "entryable"] = candles[entryable]["thrust"]

    def _log_skip_reason(self, reason: str) -> None:
        print("[Trader] skip: {}".format(reason))
