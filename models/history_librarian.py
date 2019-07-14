import datetime
# import numpy as np
import pandas as pd
from models.oanda_py_client import FXBase, OandaPyClient
from models.drawer import FigureDrawer

class Librarian():
    def __init__(self):
        inst = OandaPyClient.select_instrument()
        self.__instrument = inst['name']
        self._client  = OandaPyClient(instrument=self.__instrument)
        self.__drawer = FigureDrawer()

    def merge_history_and_instruments(self, granularity='M10'):
        '''
        create dataframe which includes trade-history & time-series currency price

        Parameters
        ----------
        granularity : string
            M1, M5, M10, H1, or D and so on ...

        Returns
        -------
        dataframe
        '''
        # INFO: lastTransactionIDを取得するために実行
        self._client.request_open_trades()

        # preapre history_df: trade-history
        history_df = self._client.request_transactions()
        history_df['time'] = [self.__convert_to_M10_dt(time) for time in history_df.time]
        entry_df, close_df, trail_df = self.__divide_history_by_type(history_df)

        # prepare candles: time-series currency price
        start_str, end_str = self.__calc_requestable_period(
            history_df['time'][0],
            history_df['time'][len(history_df)-1]
        )
        candles = self._client.request_specified_period_candles(
            start_str=start_str,
            end_str=end_str,
            granularity=granularity
        )
        candles['time'] = [time[:19] for time in candles.time]
        candles['time'] = [datetime.datetime.strptime(time, '%Y-%m-%d %H:%M:%S') for time in candles.time]

        # merge
        result = pd.merge(candles, entry_df, on='time', how='outer', right_index=True)
        result = pd.merge(result,  close_df, on='time', how='outer', right_index=True)
        result = pd.merge(result,  trail_df, on='time', how='outer', right_index=True)
        result = result.drop_duplicates(['time'])
        result.to_csv('./tmp/oanda_trade_hist.csv', index=False)
        return result

    #
    # Private
    #
    def __divide_history_by_type(self, df):
        entry_df = df.dropna(subset=['tradeOpened'])[['price', 'time', 'units']]
        entry_df = entry_df.rename(columns={'price': 'entry_price'})
        close_df = df.dropna(subset=['tradesClosed'])[['price', 'time', 'pl']]
        close_df = close_df.rename(columns={'price': 'close_price'})
        trail_df = df[df.type == 'STOP_LOSS_ORDER'][['price', 'time']]
        trail_df = trail_df.rename(columns={'price': 'stoploss'})
        return entry_df, close_df, trail_df

    def __convert_to_M10_dt(self, oanda_time):
        m1_pos = 15
        m10_str = oanda_time[:m1_pos] + '0' + oanda_time[m1_pos + 1:]
        m10_str = self.__truncate_sec(m10_str)
        m10_datetime = self.__convert_oandatime_to_dt(m10_str)
        return m10_datetime

    def __truncate_sec(self, oanda_time_str):
        sec_start = 17
        truncated_str = oanda_time_str[:sec_start] + '00'
        return truncated_str

    def __convert_oandatime_to_dt(self, oanda_time):
        py_datetime = datetime.datetime.strptime(oanda_time[:19], '%Y-%m-%dT%H:%M:%S')
        return py_datetime

    def __calc_requestable_period(self, start_dt, end_dt):
        new_start_dt = start_dt - datetime.timedelta(minutes=30)
        new_end_dt = end_dt + datetime.timedelta(minutes=30)
        diff_min = self.__calc_minutes_diff(new_start_dt, new_end_dt)
        if diff_min > 50000: # 50000 / M10 = 5000(= max candles count)
            new_start_dt = new_end_dt - datetime.timedelta(minutes=49000)

        new_start_str = new_start_dt.strftime('%Y-%m-%d %H:%M:%S')
        new_end_str = new_end_dt.strftime('%Y-%m-%d %H:%M:%S')
        return new_start_str, new_end_str

    def __calc_minutes_diff(self, start_dt, end_dt):
        diff_timedelta = end_dt - start_dt
        minutes, sec = divmod(diff_timedelta.seconds, 60)
        minutes += diff_timedelta.days * 24 * 60
        return minutes

# def sample(val=None):
#     print(val)
#     print(np.arange(1, 10))
