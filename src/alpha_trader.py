from typing import Any, Dict, Union

import pandas as pd

from src.lib import transition_loop
from src.trade_rules.stoploss import generate_sup_reg_stoploss
from src.trader import Trader


class AlphaTrader(Trader):
    def __init__(self, **kwargs: Dict[str, Any]):
        super(AlphaTrader, self).__init__(**kwargs)

    #
    # Public
    #
    def backtest(
        self, candles: pd.DataFrame, indicators: pd.DataFrame
    ) -> Dict[str, Union[str, pd.DataFrame]]:
        """backtest scalping trade"""
        candles["stoploss_for_long"], candles["stoploss_for_short"] = generate_sup_reg_stoploss(
            indicators["support"], indicators["regist"]
        )
        candles = self.__generate_entry_column(candles, indicators)

        return {
            "result": "[Trader] Finsihed a series of backtest!",
            "candles": candles,
        }

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Private
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def __generate_entry_column(
        self, candles: pd.DataFrame, indicators: pd.DataFrame
    ) -> pd.DataFrame:
        # INFO: Commit when Entry / Exit is done
        base_df: pd.DataFrame = pd.merge(
            candles[
                [
                    "open",
                    "high",
                    "low",
                    "close",
                    "time",
                    "entryable",
                    "entryable_price",
                    "stoD_over_stoSD",
                    "stoploss_for_long",
                    "stoploss_for_short",
                ]
            ],
            indicators[["sigma*2_band", "sigma*-2_band", "stoD_3", "stoSD_3"]],
            left_index=True,
            right_index=True,
        )
        committed_df: pd.DataFrame = transition_loop.commit_positions_by_loop(
            factor_dicts=base_df.to_dict("records")
        )
        orignal_candles: pd.DataFrame = candles.drop(labels=["entryable_price"], axis=1)
        return pd.concat([orignal_candles, committed_df], axis=1).rename(
            columns={"entryable_price": "entry_price"}
        )
