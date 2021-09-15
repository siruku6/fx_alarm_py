import os
from typing import Dict, List, Optional, Union, TypedDict

from models.client_manager import ClientManager
import models.tools.interface as i_face


class EntryRulesDict(TypedDict):
    static_spread: float
    stoploss_buffer_pips: float
    days: int
    granularity: str
    entry_filters: List[Optional[str]]


FILTER_ELEMENTS = [
    'in_the_band',
    'ma_gap_expanding',
    'sma_follow_trend',
    'stoc_allows',
    # 60EMA is necessary?
    # 'ema60_allows',
    'band_expansion'
]


class TraderConfig:
    ''' Traderなどで必要なパラメータを保持するクラス '''
    def __init__(self, operation: str, days: Optional[int] = None) -> None:
        self.operation: str = operation
        self.need_request: bool = self.__select_need_request()

        self._instrument: str
        selected_entry_rules: Dict[str, Union[int, float]]
        self._instrument, selected_entry_rules = self.__select_configs(days)
        self._entry_rules: EntryRulesDict = self.__init_entry_rules(selected_entry_rules)

    def __select_need_request(self) -> bool:
        need_request: bool = True
        if self.operation in ('backtest', 'forward_test'):
            need_request = i_face.ask_true_or_false(
                msg='[Trader] Which do you use ?  [1]: current_candles, [2]: static_candles :'
            )
        elif self.operation == 'unittest':
            need_request = False
        return need_request

    def __select_configs(self, days: int) -> List[Union[str, Dict[str, Union[int, float]]]]:
        if self.operation in ('backtest', 'forward_test'):
            selected_inst: List[str, float] = ClientManager.select_instrument()
            instrument = selected_inst[0]
            static_spread = selected_inst[1]['spread']
            stoploss_buffer_pips = i_face.select_stoploss_digit() * 5
            days: int = i_face.ask_number(msg='何日分のデータを取得する？(半角数字): ', limit=365)
        elif self.operation in ('live', 'unittest'):
            instrument = os.environ.get('INSTRUMENT') or 'USD_JPY'
            static_spread = 0.0
            stoploss_buffer_pips = round(float(os.environ.get('STOPLOSS_BUFFER') or 0.05), 5)

        return [instrument, {
            'static_spread': static_spread,
            'stoploss_buffer_pips': stoploss_buffer_pips,
            # TODO: the variable 'days' is to be moved out of _entry_rules
            'days': days
        }]

    def __init_entry_rules(self, selected_entry_rules: Dict[str, Union[int, float]]) -> None:
        entry_rules: EntryRulesDict = {
            'granularity': os.environ.get('GRANULARITY') or 'M5',
            'entry_filters': []
        }
        entry_rules.update(selected_entry_rules)
        return entry_rules

    # - - - - - - - - - - - - - - - - - - - - - - - -
    #                getter & setter
    # - - - - - - - - - - - - - - - - - - - - - - - -
    def get_instrument(self) -> str:
        return self._instrument

    def get_entry_rules(self, rule_property: str) -> Optional[Union[int, float, str, List[str]]]:
        return self._entry_rules[rule_property]

    def set_entry_rules(self, rule_property: str, value: Union[int, float, str, List[str]]) -> None:
        self._entry_rules[rule_property] = value

    @property
    def static_spread(self) -> float:
        return self._entry_rules['static_spread']

    @property
    def stoploss_buffer_pips(self) -> float:
        return self._entry_rules['stoploss_buffer_pips']
