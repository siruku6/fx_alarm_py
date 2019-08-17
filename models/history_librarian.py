import datetime
import numpy as np
import pandas as pd
from models.oanda_py_client import FXBase, OandaPyClient
from models.analyzer import Analyzer
from models.drawer import FigureDrawer


class Librarian():
    def __init__(self):
        inst = OandaPyClient.select_instrument()
        self.__instrument = inst['name']
        self.__client = OandaPyClient(instrument=self.__instrument)
        self.__ana = Analyzer()
        self.__drawer = FigureDrawer()
        self._indicators = None

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
        self.__client.request_open_trades()

        # preapre history_df: trade-history
        history_df = self.__client.request_transactions()
        if granularity == 'M10':
            history_df['time'] = [self.__convert_to_M10(time) for time in history_df.time]
        elif granularity == 'H4':
            history_df['time'] = [self.__convert_to_H4(time) for time in history_df.time]
        entry_df, close_df, trail_df = self.__divide_history_by_type(history_df)

        # prepare candles: time-series currency price
        today_dt = datetime.datetime.now() - datetime.timedelta(hours=9)
        start_dt = datetime.datetime.strptime(history_df['time'][0][:19], '%Y-%m-%d %H:%M:%S')
        days_wanted = (today_dt - start_dt).days + 1
        self.__client.load_long_chart(days=days_wanted, granularity=granularity)
        candles = FXBase.get_candles()
        print('[Libra] candlesセット完了')

        # merge
        result = pd.merge(candles, entry_df, on='time', how='outer', right_index=True)
        result = pd.merge(result,  close_df, on='time', how='outer', right_index=True)
        result = pd.merge(result,  trail_df, on='time', how='outer', right_index=True)
        result = result.drop_duplicates(['time'])
        result['units'] = result.units.fillna('0').astype(int)
        FXBase.set_candles(result)
        print('[Libra] データmerge完了')

        # INFO: Visualization
        result.to_csv('./tmp/oanda_trade_hist.csv', index=False)
        self.__draw_history()
        self.__drawer.close_all()

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

    def __convert_to_M10(self, oanda_time):
        m1_pos = 15
        m10_str = oanda_time[:m1_pos] + '0' + oanda_time[m1_pos + 1:]
        m10_str = self.__truncate_sec(m10_str).replace('T', ' ')
        return m10_str

    def __convert_to_H4(self, oanda_time):
        # INFO: 12文字目までで hour まで取得できる
        time = datetime.datetime.strptime(oanda_time.replace('T', ' ')[:13], '%Y-%m-%d %H')

        # INFO: OandaのH4は [1,5,9,13,17,21] を取り得るので、それをはみ出した時間を切り捨て
        minus = ((time.hour + 3) % 4)
        time -= datetime.timedelta(hours=minus)
        h4_str = time.strftime('%Y-%m-%d %H:%M:%S')
        return h4_str

    def __truncate_sec(self, oanda_time_str):
        sec_start = 17
        truncated_str = oanda_time_str[:sec_start] + '00'
        return truncated_str

    def __calc_minutes_diff(self, start_dt, end_dt):
        diff_timedelta = end_dt - start_dt
        minutes, _sec = divmod(diff_timedelta.seconds, 60)
        minutes += diff_timedelta.days * 24 * 60
        return minutes

    def __draw_history(self):
        DRAWABLE_ROWS = 200

        # INFO: データ準備
        d_frame = FXBase.get_candles().copy()[-DRAWABLE_ROWS:None].reset_index(drop=True)
        d_frame['sequence'] = d_frame.index
        entry_df = d_frame[['sequence', 'entry_price', 'units']].rename(columns={'entry_price': 'price'})
        close_df = d_frame[['sequence', 'close_price', 'units']].copy().rename(columns={'close_price': 'price'})

        long_df, short_df = entry_df.copy(), entry_df.copy()
        # OPTIMIZE: numpyを使わなくて済むなら使わない
        long_df.loc[long_df.units <= 0, 'price'] = np.nan
        short_df.loc[short_df.units >= 0, 'price'] = np.nan

        # prepare indicators
        self.__ana.calc_indicators()
        self._indicators = self.__ana.get_indicators()

        # INFO: 描画
        drwr = self.__drawer
        drwr.draw_candles(-DRAWABLE_ROWS, None)
        drwr.draw_indicators(d_frame=self._indicators[-DRAWABLE_ROWS:None].reset_index(drop=True))

        drwr.draw_positionDf_on_plt(df=long_df[['sequence', 'price']],    plot_type=drwr.PLOT_TYPE['long'])
        drwr.draw_positionDf_on_plt(df=short_df[['sequence', 'price']],   plot_type=drwr.PLOT_TYPE['short'])
        drwr.draw_positionDf_on_plt(df=d_frame[['sequence', 'stoploss']], plot_type=drwr.PLOT_TYPE['trail'])
        drwr.draw_positionDf_on_plt(df=close_df[['sequence', 'price']],   plot_type=drwr.PLOT_TYPE['exit'])
        result = drwr.create_png(instrument=self.__instrument, granularity='real-trade', sr_time=d_frame.time, num=0)
        print(result['success'])
