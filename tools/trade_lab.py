from collections import OrderedDict
from typing import Dict, List, Optional, Tuple, Type

import pandas as pd

from src.alpha_trader import AlphaTrader
from src.analyzer import Analyzer
from src.candle_storage import FXBase
from src.lib.instance_builder import InstanceBuilder
from src.lib.interface import select_from_dict
from src.lib.mathematics import (
    generate_different_length_combinations,
    range_2nd_decimal,
)
from src.swing_trader import SwingTrader
import src.trade_rules.base as base_rules
from src.trader import Trader
from src.trader_config import FILTER_ELEMENTS

RULE_DICT = OrderedDict(
    swing={"dummy": ""},
    wait_close={"dummy": ""},
    scalping={"dummy": ""},
    cancel={"dummy": ""},
)

TRADER_CLASSES: Dict[str, Type["Trader"]] = {
    "cancel": None,
    "scalping": AlphaTrader,
    "swing": SwingTrader,
    "wait_close": SwingTrader,
}


def select_trader_class() -> Tuple[str, Type["Trader"]]:
    rule_name = select_from_dict(RULE_DICT, menumsg="取引ルールを選択して下さい")
    trader_class: Type["Trader"] = TRADER_CLASSES.get(rule_name)
    if trader_class is None:
        raise RuntimeError(f"rule_name is wrong. rule_name: {rule_name}")

    return rule_name, trader_class


def verify_various_entry_filters(tr_instance, config, rule: str) -> None:
    """entry_filterの全パターンを検証する"""
    filter_sets: Tuple[List[Optional[str]]] = generate_different_length_combinations(
        items=FILTER_ELEMENTS
    )

    for filter_set in filter_sets:
        print("[Trader] ** Now trying filter -> {} **".format(filter_set))
        verify_various_stoploss(tr_instance, config, rule=rule, entry_filters=filter_set)


def verify_various_stoploss(tr_instance, config, rule: str, entry_filters: List[str] = []) -> None:
    """StopLossの設定値を自動でスライドさせて損益を検証"""
    stoploss_digit: float = config.stoploss_buffer_base
    stoploss_buffer_list: List[float] = range_2nd_decimal(
        stoploss_digit, stoploss_digit * 20, stoploss_digit * 2
    )

    verification_dataframes_array: List[Optional[pd.DataFrame]] = []
    for stoploss_buf in stoploss_buffer_list:
        print("[Trader] stoploss buffer: {}pipsで検証開始...".format(stoploss_buf))
        config.set_entry_rules("stoploss_buffer_pips", stoploss_buf)
        df_positions = tr_instance.perform(rule=rule, entry_filters=entry_filters)
        verification_dataframes_array.append(df_positions)

    result = pd.concat(
        verification_dataframes_array, axis=1, keys=stoploss_buffer_list, names=["SL_buffer"]
    )
    result.to_csv("./tmp/csvs/sl_verify_{inst}.csv".format(inst=config.get_instrument()))


def _merge_long_indicators(ana: "Analyzer") -> pd.DataFrame:
    candles: pd.DataFrame = FXBase.get_candles()
    tmp_df = candles.merge(ana.get_long_indicators(), on="time", how="left")
    # tmp_df['long_stoD'].fillna(method='ffill', inplace=True)
    # tmp_df['long_stoSD'].fillna(method='ffill', inplace=True)
    tmp_df.loc[:, "stoD_over_stoSD"] = (
        tmp_df["stoD_over_stoSD"].fillna(method="ffill").fillna(False)
    )

    tmp_df["long_20SMA"].fillna(method="ffill", inplace=True)
    tmp_df["long_10EMA"].fillna(method="ffill", inplace=True)
    long_ma = (
        tmp_df[["long_10EMA", "long_20SMA"]]
        .copy()
        .rename(columns={"long_10EMA": "10EMA", "long_20SMA": "20SMA"})
    )
    tmp_df["long_trend"] = base_rules.generate_trend_column(long_ma, candles.close)

    return tmp_df


def prepare_candles(candle_loader, ana: "Analyzer"):
    result: Dict[str, str] = candle_loader.run()
    if result.get("tradable") is False:
        print(result)
        return None

    candle_loader.load_long_span_candles()
    ana.calc_indicators(FXBase.get_candles(), long_span_candles=FXBase.get_long_span_candles())
    indicators: pd.DataFrame = ana.get_indicators()

    candles: pd.DataFrame = _merge_long_indicators(ana)
    FXBase.set_candles(candles)
    return indicators


def create_trader_instance(
    trader_class: Type["Trader"], operation: str = "backtest", days: Optional[int] = None
) -> Tuple:
    ana: "Analyzer" = Analyzer()
    (
        config,
        client,
        candle_loader,
        result_processor,
    ) = InstanceBuilder.build(operation=operation, days=days).values()

    indicators = prepare_candles(candle_loader, ana)
    if indicators is None:
        return None, None

    tr_instance: Trader = trader_class(
        ana=ana,
        client=client,
        config=config,
        indicators=indicators,
        result_processor=result_processor,
    )
    return tr_instance, config
