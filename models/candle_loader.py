from typing import Dict  # , List, Optional
import pandas as pd

import models.tools.interface as i_face
from models.candle_storage import FXBase
from models.trader_config import TraderConfig
from models.client_manager import ClientManager


class CandleLoader:

    def __init__(self, config: TraderConfig, client_manager: ClientManager) -> None:
        self.config: TraderConfig = config
        self.client_manager: ClientManager = client_manager

    def run(self) -> Dict[str, str]:
        candles: pd.DataFrame
        if self.config.need_request is False:
            candles = pd.read_csv('tests/fixtures/sample_candles.csv')
        elif self.config.operation in ('backtest', 'forward_test'):
            self.config.set_entry_rules('granularity', value=i_face.ask_granularity())
            candles = self.client_manager.load_long_chart(
                days=self.config.get_entry_rules('days'),
                granularity=self.config.get_entry_rules('granularity')
            )['candles']
        elif self.config.operation == 'live':
            self.tradeable: bool = self.client_manager.call_oanda('is_tradeable')['tradeable']
            if not self.tradeable:
                return {'info': 'exit at once'}

            candles = self.client_manager.load_specify_length_candles(
                length=70, granularity=self.config.get_entry_rules('granularity')
            )['candles']
        else:
            return {'info': 'exit at once'}

        FXBase.set_candles(candles)
        if self.config.need_request is False: return {'info': None}

        latest_candle = self.client_manager.call_oanda('current_price')
        self.__update_latest_candle(latest_candle)
        return {'info': None}

    def load_long_span_candles(self) -> None:
        long_span_candles: pd.DataFrame
        if self.config.need_request is False:
            long_span_candles = pd.read_csv('tests/fixtures/sample_candles_h4.csv')
        else:
            long_span_candles = self.__load_long_chart(granularity='D')

        long_span_candles['time'] = pd.to_datetime(long_span_candles['time'])
        long_span_candles.set_index('time', inplace=True)
        FXBase.set_long_span_candles(long_span_candles)
        # long_span_candles.resample('4H').ffill() # upsamplingしようとしたがいらなかった。

    def __load_long_chart(self, granularity: str = None) -> pd.DataFrame:
        if granularity is None:
            granularity: str = self.config.get_entry_rules('granularity')

        return self.client_manager.load_long_chart(
            days=self.config.get_entry_rules('days'),
            granularity=granularity
        )['candles']

    def __update_latest_candle(self, latest_candle) -> None:
        '''
        Update the latest candle,
        if either end of the new latest candle is beyond either end of old latest candle
        '''
        candle_dict = FXBase.get_candles().iloc[-1].to_dict()
        FXBase.replace_latest_price('close', latest_candle['close'])
        if candle_dict['high'] < latest_candle['high']:
            FXBase.replace_latest_price('high', latest_candle['high'])
        if candle_dict['low'] > latest_candle['low']:
            FXBase.replace_latest_price('low', latest_candle['low'])
        print('[Client] Last_H4: {}, Current_M1: {}'.format(candle_dict, latest_candle))
        print('[Client] New_H4: {}'.format(FXBase.get_candles().iloc[-1].to_dict()))
