import abc
from collections.abc import Callable
from typing import Dict, List, Optional, Union

import pandas as pd

from src.candle_storage import FXBase
from src.data_factory_clerk import (
    generate_entryable_price,
    mark_entryable_rows,
    prepare_indicators,
    prepare_trade_signs,
)
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
        else:
            print("Rule {} is not exist ...".format(rule))
            exit()

        # TODO: The order of these processings cannot be changed.
        #     But should be able to be changed.
        indicators: pd.DataFrame = prepare_indicators()
        candles: pd.DataFrame = FXBase.get_candles().copy()
        candles = prepare_trade_signs(self.config, rule, candles, indicators)
        candles = mark_entryable_rows(
            self.config.get_entry_rules("entry_filters"), candles
        )  # This needs 'thrust'

        candles.loc[:, "entryable_price"] = generate_entryable_price(
            rule, candles, self.config.static_spread
        )
        result: Dict[str, Union[str, pd.DataFrame]] = backtest(candles, indicators)

        print("{} ... (perform)".format(result["result"]))
        df_positions: pd.DataFrame = self._result_processor.run(rule, result, indicators)
        return df_positions

    @abc.abstractmethod
    def backtest(
        self, candles: pd.DataFrame, indicators: pd.DataFrame
    ) -> Dict[str, Union[str, pd.DataFrame]]:
        pass
