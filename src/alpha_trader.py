from typing import Dict, Union

import numpy as np
import pandas as pd

import src.trade_rules.scalping as scalping
from src.trader import Trader


class AlphaTrader(Trader):
    """トレードルールに基づいてOandaへの発注を行うclass"""

    def __init__(self, operation="backtest", days=None):
        super(AlphaTrader, self).__init__(operation=operation, days=days)

    #
    # Public
    #
    def backtest(self, candles) -> Dict[str, Union[str, pd.DataFrame]]:
        """backtest scalping trade"""
        candles["entryable_price"] = self._generate_entryable_price(candles)
        self.__generate_entry_column(candles)

        candles.to_csv("./tmp/csvs/scalping_data_dump.csv")
        return {"result": "[Trader] Finsihed a series of backtest!", "candles": candles}

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Private
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def _generate_thrust_column(self, candles: pd.DataFrame, _: pd.Series = None) -> pd.Series:
        return scalping.generate_repulsion_column(candles, ema=self._indicators["10EMA"])

    def _generate_entryable_price(self, candles: pd.DataFrame) -> np.ndarray:
        return scalping.generate_entryable_prices(
            candles[["open", "entryable"]], self.config.static_spread
        )

    def __generate_entry_column(self, candles: pd.DataFrame) -> pd.DataFrame:
        # INFO: Commit when Entry / Exit is done
        base_df = pd.merge(
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
                ]
            ],
            self._indicators[
                ["sigma*2_band", "sigma*-2_band", "stoD_3", "stoSD_3", "support", "regist"]
            ],
            left_index=True,
            right_index=True,
        )
        commited_df = scalping.commit_positions_by_loop(factor_dicts=base_df.to_dict("records"))
        # OPTIMIZE: We may be able to  merge two dataframes by the way written in following article.
        #   https://ymt-lab.com/post/2020/python-pandas-insert-columns/
        # like this (but this doesn't work anyway)
        # return pd.concat([candles, commited_df], axis=1) \
        #          .rename(columns={'entryable_price': 'entry_price'})
        candles.loc[:, "entry_price"] = commited_df["entryable_price"]
        candles.loc[:, "position"] = commited_df["position"]
        candles.loc[:, "exitable_price"] = commited_df["exitable_price"]
        candles.loc[:, "exit_reason"] = commited_df["exit_reason"]
        candles.loc[:, "possible_stoploss"] = commited_df["possible_stoploss"]
