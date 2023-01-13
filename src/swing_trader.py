from typing import Any, Dict, Union

import pandas as pd

import src.trade_rules.base as base_rules
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
        sliding_result = self.__slide_to_reasonable_prices(candles=candles)

        candles.to_csv("./tmp/csvs/full_data_dump.csv")
        result_msg: str = self.__result_message(sliding_result["result"])
        return {"result": result_msg, "candles": candles}

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Private
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    def __generate_entry_column(self, candles: pd.DataFrame) -> None:
        print("[Trader] judging entryable or not ...")

        entry_direction: pd.Series = candles["entryable"].fillna(method="ffill")
        candles_with_stoploss: pd.DataFrame = self.__set_stoploss_prices(candles, entry_direction)
        base_rules.commit_positions(
            candles_with_stoploss,
            long_indexes=(entry_direction == "long"),
            short_indexes=(entry_direction == "short"),
            spread=self.config.static_spread,
        )

    def __set_stoploss_prices(
        self, candles: pd.DataFrame, entry_direction: pd.Series
    ) -> pd.DataFrame:
        candles.loc[:, "possible_stoploss"] = stoploss_strategy.previous_candle_othersides(
            candles, entry_direction, self.config
        )
        return candles

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
            print("[Trader] no positions ...")
            return {"result": "no position"}

        df_with_positions = pd.DataFrame.from_dict(position_rows)

        candles.loc[position_index, "entry_price"] = df_with_positions["entryable_price"].to_numpy(
            copy=True
        )
        candles.loc[position_index, "time"] = (
            df_with_positions["time"].astype(str).to_numpy(copy=True)
        )

        print("[Trader] finished sliding !")
        return {"result": "success"}

    def __result_message(self, result: str) -> str:
        if result == "no position":
            return "no position"

        return "[Trader] 1 series of trading is FINISHED!"
