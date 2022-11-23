import os
from typing import Dict, List, Optional, TypedDict, Union

import src.lib.interface as i_face


class EntryRulesDict(TypedDict):
    static_spread: float
    stoploss_buffer_base: float
    stoploss_buffer_pips: float
    days: int
    granularity: str
    entry_filters: List[Optional[str]]


FILTER_ELEMENTS = [
    "in_the_band",
    "ma_gap_expanding",
    "sma_follow_trend",
    "stoc_allows",
    # 60EMA is necessary?
    # 'ema60_allows',
    "band_expansion",
]


class TraderConfig:
    """Class holding parameters necessary for Traders"""

    def __init__(
        self,
        operation: str,
        instrument: Optional[str] = None,
        days: Optional[int] = None,
    ) -> None:
        self.operation: str = operation
        self.need_request: bool = self.__select_need_request()

        self._instrument: str
        selected_entry_rules: Dict[str, Union[int, float]]
        self._stoploss_strategy_name: str = os.environ["STOPLOSS_STRATEGY"]
        self._instrument, selected_entry_rules = self.__select_configs(days)
        if instrument is not None:
            self._instrument = instrument
        self._entry_rules: EntryRulesDict = self.__init_entry_rules(selected_entry_rules)

    def __select_need_request(self) -> bool:
        need_request: bool = True
        if self.operation in ("backtest", "forward_test"):
            need_request = i_face.ask_true_or_false(
                msg="[Trader] Which do you use ?  [1]: current_candles, [2]: static_candles :"
            )
        elif self.operation == "unittest":
            need_request = False
        return need_request

    def __select_configs(
        self, days: Optional[int]
    ) -> List[Union[str, Dict[str, Union[int, float]]]]:
        instrument: str
        static_spread: float
        stoploss_buffer_base: float
        stoploss_buffer_pips: float

        if self.operation in ("backtest", "forward_test"):
            selected_inst: Dict[str, Union[str, float]] = i_face.select_instrument()
            instrument = selected_inst["name"]
            static_spread = selected_inst["spread"]
            stoploss_buffer_base = i_face.select_stoploss_digit()
            stoploss_buffer_pips = stoploss_buffer_base * 5
            msg: str = "How many days would you like to get candles for?"
            "(Only single-byte number): "
            fixed_days: int = i_face.ask_number(msg=msg, limit=365)
        elif self.operation in ("live", "unittest"):
            instrument = os.environ["INSTRUMENT"]
            static_spread = 0.0  # TODO: set correct value
            stoploss_buffer_base = 0.01  # TODO: set correct value
            stoploss_buffer_pips = round(float(os.environ.get("STOPLOSS_BUFFER") or 0.05), 5)
            fixed_days = days  # type: ignore

        return [
            instrument,
            {
                "static_spread": static_spread,
                "stoploss_buffer_base": stoploss_buffer_base,
                "stoploss_buffer_pips": stoploss_buffer_pips,
                # TODO: the variable 'days' is to be moved out of _entry_rules
                "days": fixed_days,
            },
        ]

    def __init_entry_rules(
        self, selected_entry_rules: Dict[str, Union[int, float]]
    ) -> EntryRulesDict:
        entry_rules: EntryRulesDict = {
            "granularity": os.environ.get("GRANULARITY") or "M5",
            "entry_filters": [],
        }
        entry_rules.update(selected_entry_rules)
        return entry_rules

    # - - - - - - - - - - - - - - - - - - - - - - - -
    #                getter & setter
    # - - - - - - - - - - - - - - - - - - - - - - - -
    def get_instrument(self) -> str:
        return self._instrument

    def get_entry_rules(self, rule_property: str) -> Optional[Union[int, float, str, List[str]]]:
        """
        Parameters
        ----------
        rule_property : str
            Available Values: [
                'granularity', 'entry_filters', 'static_spread',
                'stoploss_buffer_base', 'stoploss_buffer_pips', 'days'
            ]

        Returns
        -------
        Optional[Union[int, float, str, List[str]]]
        """
        return self._entry_rules[rule_property]

    def set_entry_rules(self, rule_property: str, value: Union[int, float, str, List[str]]) -> None:
        self._entry_rules[rule_property] = value

    @property
    def static_spread(self) -> float:
        return self._entry_rules["static_spread"]

    @property
    def stoploss_buffer_pips(self) -> float:
        return self._entry_rules["stoploss_buffer_pips"]

    @property
    def stoploss_buffer_base(self) -> float:
        return self._entry_rules["stoploss_buffer_base"]

    @property
    def stoploss_strategy_name(self) -> str:
        return self._stoploss_strategy_name
