import abc
from collections.abc import Callable
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd

from src.candle_storage import FXBase
from src.data_factory_clerk import prepare_indicators
from src.lib.time_series_generator import (  # generate_ema_allows_column,
    generate_band_expansion_column,
    generate_following_trend_column,
    generate_getting_steeper_column,
    generate_in_bands_column,
    generate_thrust_column,
)
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
    def perform(self, rule: str, entry_filters: Optional[List[str]] = None) -> pd.DataFrame:
        """automatically test trade rule"""
        # INFO: 繰り返しデモする場合に前回のpositionが残っているので、リセットする いらなくない？
        self._result_processor.reset_drawer()
        filters: List[str] = FILTER_ELEMENTS if entry_filters is None else entry_filters
        self.config.set_entry_rules("entry_filters", value=filters)

        backtest: Callable[
            [pd.DataFrame, pd.DataFrame],
            Dict[str, Union[str, pd.DataFrame]],
        ]
        if rule in ("swing", "scalping"):
            backtest = self.backtest
        # elif rule == "wait_close":
        #     backtest = self._backtest_wait_close
        else:
            print("Rule {} is not exist ...".format(rule))
            exit()

        # TODO: The order of these processings cannot be changed.
        #     But should be able to be changed.
        indicators: pd.DataFrame = prepare_indicators()
        candles: pd.DataFrame = FXBase.get_candles().copy()
        candles = self._prepare_trade_signs(rule, candles, indicators)
        candles = self._mark_entryable_rows(candles)  # This needs 'thrust'

        result: Dict[str, Union[str, pd.DataFrame]] = backtest(candles, indicators)

        print("{} ... (perform)".format(result["result"]))
        df_positions: pd.DataFrame = self._result_processor.run(rule, result, indicators)
        return df_positions

    @abc.abstractmethod
    def backtest(
        self, candles: pd.DataFrame, indicators: pd.DataFrame
    ) -> Dict[str, Union[str, pd.DataFrame]]:
        pass

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
    # private
    #
    def _prepare_trade_signs(
        self, rule: str, candles: pd.DataFrame, indicators: pd.DataFrame
    ) -> pd.DataFrame:
        print("[Trader] preparing base-data for judging ...")

        candles["trend"] = base_rules.generate_trend_column(indicators, candles.close)
        trend = pd.DataFrame(
            {
                "bull": np.where(candles["trend"] == "bull", True, False),
                "bear": np.where(candles["trend"] == "bear", True, False),
            }
        )
        candles["thrust"] = generate_thrust_column(rule, candles, trend, indicators)
        # 60EMA is necessary?
        # candles['ema60_allows'] = generate_ema_allows_column(candles=candles)

        entryable_prices: Union[np.ndarray, pd.Series]
        if self.config.operation in ["live", "forward_test"]:
            entryable_prices = candles["close"]
        else:
            entryable_prices = self._generate_entryable_price(
                candles.rename(columns={"thrust": "entryable"})
            )

        candles["in_the_band"] = generate_in_bands_column(indicators, entryable_prices)
        candles["band_expansion"] = generate_band_expansion_column(
            df_bands=indicators[["sigma*2_band", "sigma*-2_band"]]
        )
        candles["ma_gap_expanding"] = generate_getting_steeper_column(trend, indicators)
        candles["sma_follow_trend"] = generate_following_trend_column(trend, indicators["20SMA"])
        candles["stoc_allows"] = base_rules.generate_stoc_allows_column(
            indicators, sr_trend=candles["trend"]
        )
        return candles

    def _mark_entryable_rows(self, candles: pd.DataFrame) -> pd.DataFrame:
        """
        Judge whether it is entryable or not on each row.
        Then set the result in the column 'entryable'.
        """
        entryable = np.all(candles[self.config.get_entry_rules("entry_filters")], axis=1)
        candles.loc[entryable, "entryable"] = candles[entryable]["thrust"]
        return candles
