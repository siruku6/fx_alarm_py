from collections import OrderedDict
from typing import Dict, List, Optional, Tuple, Type, Union

import pandas as pd

from src.alpha_trader import AlphaTrader
from src.lib import logic
from src.lib.instance_builder import InstanceBuilder
import src.lib.interface as i_face
from src.lib.interface import select_from_dict
from src.lib.mathematics import (
    generate_different_length_combinations,
    range_2nd_decimal,
)
from src.swing_trader import SwingTrader
from src.trader import Trader
from src.trader_config import FILTER_ELEMENTS, TraderConfig

RULE_DICT = OrderedDict(
    swing={"dummy": ""},
    # wait_close={"dummy": ""},
    scalping={"dummy": ""},
    cancel={"dummy": ""},
)

TRADER_CLASSES: Dict[str, Type["Trader"]] = {
    "scalping": AlphaTrader,
    "swing": SwingTrader,
    # "wait_close": SwingTrader,
}


def select_trader_class() -> Tuple[str, Type["Trader"]]:
    rule_name = select_from_dict(RULE_DICT, menumsg="取引ルールを選択して下さい")
    trader_class: Optional[Type[Trader]] = TRADER_CLASSES.get(rule_name)
    if trader_class is None:
        raise RuntimeError(f"rule_name is wrong. rule_name: {rule_name}")

    return rule_name, trader_class


def verify_various_entry_filters(
    tr_instance: Union[AlphaTrader, SwingTrader], config: TraderConfig, rule: str
) -> None:
    """
    verify all available combinations of the elements in entry_filter
    """
    filter_sets: Tuple[List[Optional[str]]] = generate_different_length_combinations(
        items=FILTER_ELEMENTS
    )

    for filter_set in filter_sets:
        print("[Trader] ** Now trying filter -> {} **".format(filter_set))
        verify_various_stoploss(
            tr_instance,
            config,
            rule=rule,
            entry_filters=filter_set,
        )


def verify_various_stoploss(
    tr_instance: Union[AlphaTrader, SwingTrader],
    config: TraderConfig,
    rule: str,
    entry_filters: List[str] = [],
) -> None:
    """
    verify P/L sliding the value of StopLoss
    """
    stoploss_digit: float = config.stoploss_buffer_base
    stoploss_buffer_list: List[float] = range_2nd_decimal(
        stoploss_digit, stoploss_digit * 20, stoploss_digit * 2
    )

    verification_dataframes_array: List[Optional[pd.DataFrame]] = []
    for stoploss_buf in stoploss_buffer_list:
        print("[Trader] Start verification with the stoploss buffer {}pips".format(stoploss_buf))
        config.set_entry_rules("stoploss_buffer_pips", stoploss_buf)
        df_positions = tr_instance.perform(rule=rule, entry_filters=entry_filters)
        verification_dataframes_array.append(df_positions)

    result = pd.concat(
        verification_dataframes_array, axis=1, keys=stoploss_buffer_list, names=["SL_buffer"]
    )
    result.to_csv("./tmp/csvs/sl_verify_{inst}.csv".format(inst=config.get_instrument()))


def is_tradeable(interface) -> Dict[str, Union[str, bool]]:
    tradeable = interface.call_oanda("is_tradeable")["tradeable"]
    if not tradeable:
        return {"info": "Now the trading market is closed.", "tradeable": False}
    if logic.is_reasonable() is False:
        return {"info": "Now it is not reasonable to trade.", "tradeable": False}

    return {"info": "Now it is tradeable.", "tradeable": True}


def prepare_candles(candle_loader) -> None:
    _: Dict[str, str] = candle_loader.run()
    candle_loader.load_long_span_candles()


def create_trader_instance(
    trader_class: Type["Trader"], operation: str = "backtest", days: Optional[int] = None
) -> Tuple:
    if operation in ["backtest", "forward_test"]:
        msg: str = "How many days would you like to get candles for? (Only single-byte number): "
        days = i_face.ask_number(msg=msg, limit=365)
    if days is None:
        raise RuntimeError("'days' must be specified, but is None.")

    (
        config,
        o_interface,
        candle_loader,
        result_processor,
    ) = InstanceBuilder.build(operation=operation, days=days).values()

    result: Dict[str, Union[str, bool]] = is_tradeable(interface=o_interface)

    if candle_loader.need_request and (result["tradeable"] is False):
        print("[TradeLab]", result["info"])
        return None, None

    prepare_candles(candle_loader)

    tr_instance: Trader = trader_class(
        o_interface=o_interface,
        config=config,
        result_processor=result_processor,
    )
    return tr_instance, config
