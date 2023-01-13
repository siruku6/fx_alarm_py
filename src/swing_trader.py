from typing import Any, Dict, Union

import pandas as pd

import src.trade_rules.stoploss as stoploss_strategy
from src.trader import Trader


class SwingTrader(Trader):
    def __init__(self, **kwargs: Dict[str, Any]):
        super(SwingTrader, self).__init__(**kwargs)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Public
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def backtest(
        self, candles: pd.DataFrame, indicators: pd.DataFrame
    ) -> Dict[str, Union[str, pd.DataFrame]]:
        """backtest swing trade"""
        self.__generate_entry_column(candles=candles)
        result = self.__slide_to_reasonable_prices(candles=candles)

        return {
            "result": result["result"],
            "candles": candles,
        }

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Private
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def __generate_entry_column(self, candles: pd.DataFrame) -> None:
        print("[Trader] judging entryable or not ...")

        entry_direction: pd.Series = candles["entryable"].fillna(method="ffill")
        candles.loc[:, "possible_stoploss"] = self.__set_stoploss_prices(candles, entry_direction)
        self._commit_positions(
            candles,
            long_indexes=(entry_direction == "long"),
            short_indexes=(entry_direction == "short"),
            spread=self.config.static_spread,
        )

    def __set_stoploss_prices(
        self, candles: pd.DataFrame, entry_direction: pd.Series
    ) -> pd.DataFrame:
        return stoploss_strategy.previous_candle_othersides(
            candles,
            entry_direction,
            self.config,
        )

    # OPTIMIZE: probably this method has many unnecessary processings!
    def __slide_to_reasonable_prices(self, candles: pd.DataFrame) -> Dict[str, str]:
        print("[Trader] start sliding ...")

        position_index = candles.position.isin(["long", "short"]) | (
            candles.position.isin(["sell_exit", "buy_exit"]) & ~candles.entryable_price.isna()
        )
        position_rows = candles[position_index][["time", "entryable_price", "position"]].to_dict(
            "records"
        )
        if position_rows == []:
            return {"result": "no position"}

        df_with_positions = pd.DataFrame.from_dict(position_rows)

        candles.loc[position_index, "entry_price"] = df_with_positions["entryable_price"].to_numpy(
            copy=True
        )
        candles.loc[position_index, "time"] = (
            df_with_positions["time"].astype(str).to_numpy(copy=True)
        )

        return {"result": "[Trader] 1 series of trading is FINISHED!"}

    def _commit_positions(
        self,
        candles: pd.DataFrame,
        long_indexes: pd.Series,
        short_indexes: pd.Series,
        spread: float,
    ) -> None:
        """
        set timing and price of exit

        Parameters
        ----------
        candles : pd.DataFrame
            Index:
                Any
            Columns:
                Name: high,              dtype: float64 (required)
                Name: low,               dtype: float64 (required)
                Name: entryable,         dtype: object  (required)
                Name: entryable_price,   dtype: float64 (required)
                Name: possible_stoploss, dtype: float64 (required)
                Name: time,              dtype: object  # datetime64[ns]

        Returns
        -------
        None
        """
        candles.loc[:, "position"] = candles["entryable"].copy()

        long_exits = long_indexes & (candles["low"] < candles["possible_stoploss"])
        candles.loc[long_exits, "position"] = "sell_exit"
        candles.loc[long_exits, "exitable_price"] = candles.loc[long_exits, "possible_stoploss"]

        short_exits = short_indexes & (candles["high"] + spread > candles["possible_stoploss"])
        candles.loc[short_exits, "position"] = "buy_exit"
        candles.loc[short_exits, "exitable_price"] = candles.loc[short_exits, "possible_stoploss"]

        # INFO: position column の整理
        candles["position"].fillna(method="ffill", inplace=True)

        # INFO: 2連続entry, entryなしでのexitを除去
        no_position_index = (candles["position"] == candles["position"].shift(1)) & (
            candles["entryable_price"].isna() | candles["exitable_price"].isna()
        )
        candles.loc[no_position_index, "position"] = None
