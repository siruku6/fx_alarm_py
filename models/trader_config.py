import os
from typing import Dict, List, Optional, Union

from models.client_manager import ClientManager
import models.tools.interface as i_face


class TraderConfig:
    ''' Traderなどで必要なパラメータを保持するクラス '''
    def __init__(self, operation: str, days: Optional[int] = None) -> None:
        self.operation: str = operation
        self.need_request: bool
        if operation in ('backtest', 'forward_test'):
            self.need_request = i_face.ask_true_or_false(
                msg='[Trader] Which do you use ?  [1]: current_candles, [2]: static_candles :'
            )
        elif operation == 'unittest':
            self.need_request = False
        else:
            self.need_request = True
        self.__init_common_params(days=days)

    def __init_common_params(self, days: int):
        self._instrument: str
        self._static_spread: float
        self._stoploss_buffer_pips: float

        if self.operation in ('backtest', 'forward_test'):
            selected_inst: List[str, float] = ClientManager.select_instrument()
            # TODO: the variables declared on following 3 lines is to be moved into _entry_rules
            self._instrument = selected_inst[0]
            self._static_spread = selected_inst[1]['spread']
            self._stoploss_buffer_pips = i_face.select_stoploss_digit() * 5
            days: int = i_face.ask_number(msg='何日分のデータを取得する？(半角数字): ', limit=365)
        elif self.operation in ('live', 'unittest'):
            self._instrument = os.environ.get('INSTRUMENT') or 'USD_JPY'
            self._static_spread = 0.0
            self._stoploss_buffer_pips = round(float(os.environ.get('STOPLOSS_BUFFER') or 0.05), 5)

        self._entry_rules: Dict[str, Union[int, str, List[str]]] = {
            # TODO: the variable 'days' is to be moved out of _entry_rules
            'days': days,
            'granularity': os.environ.get('GRANULARITY') or 'M5',
            # default-filter: かなりhigh performance
            'entry_filter': ['in_the_band', 'stoc_allows', 'band_expansion']
        }

    # - - - - - - - - - - - - - - - - - - - - - - - -
    #                getter & setter
    # - - - - - - - - - - - - - - - - - - - - - - - -
    def get_instrument(self):
        return self._instrument

    def get_entry_rules(self, rule_property):
        return self._entry_rules[rule_property]

    def set_entry_rules(self, rule_property, value):
        self._entry_rules[rule_property] = value
