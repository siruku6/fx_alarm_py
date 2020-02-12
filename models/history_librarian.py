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
        history_df.loc[:, 'price'] = history_df.price.astype('float32')
        history_df.to_csv('./tmp/csvs/hist_positions.csv', index=False)
        print('[Libra] trade_log is loaded')

        # prepare candles:
        oldest_log_datetime = pd.to_datetime(history_df.iloc[0].time)
        dt_a_month_ago = oldest_log_datetime - datetime.timedelta(days=1)
        start_str = dt_a_month_ago.strftime('%Y-%m-%d %H:%M:%S')
        candles = self.__prepare_candles(
            starttime_str=start_str,
            granularity=granularity
        )
        dict_summer_time_borders = self.__detect_summer_time_borders(candles)
        print('[Libra] candles are loaded')

        if granularity == 'M10':
            history_df['time'] = [self.__convert_to_m10(time) for time in history_df.time]
        elif granularity == 'H4':
            history_df['time'] = [self.__convert_to_h4(time, dict_summer_time_borders) for time in history_df.time]
        entry_df, close_df, trail_df = self.__divide_history_by_type(history_df)

        # merge
        result = pd.merge(candles, entry_df, on='time', how='outer', right_index=True)
        result = pd.merge(result, close_df, on='time', how='outer', right_index=True)
        result = pd.merge(result, trail_df, on='time', how='outer', right_index=True)
        result = result.drop_duplicates(['time'])
        result['units'] = result.units.fillna('0').astype(int)
        FXBase.set_candles(result)
        print('[Libra] candles and trade-history is merged')

        # INFO: Visualization
        result.to_csv('./tmp/csvs/oanda_trade_hist.csv', index=False)
        self.__draw_history()
        self.__drawer.close_all()

        return result

    #
    # Private
    #
    def __prepare_candles(self, starttime_str, granularity):
        today_dt = datetime.datetime.now() - datetime.timedelta(hours=9)
        start_dt = datetime.datetime.strptime(starttime_str, '%Y-%m-%d %H:%M:%S')
        days_wanted = (today_dt - start_dt).days + 1
        result = self.__client.load_long_chart(days=days_wanted, granularity=granularity)
        return result['candles']

    def __detect_summer_time_borders(self, candles):
        candles['summer_time'] = pd.to_numeric(candles.time.str[12], downcast='signed') % 2 == 1
        return candles[candles.summer_time != candles.summer_time.shift(1)][['time', 'summer_time']].to_dict('records')

    def __convert_to_m10(self, oanda_time):
        m1_pos = 15
        m10_str = oanda_time[:m1_pos] + '0' + oanda_time[m1_pos + 1:]
        m10_str = self.__truncate_sec(m10_str).replace('T', ' ')
        return m10_str

    def __convert_to_h4(self, oanda_time, dict_summer_time_borders):
        time_str = oanda_time.replace('T', ' ')

        # INFO: 12文字目までで hour まで取得できる
        time = datetime.datetime.strptime(time_str[:13], '%Y-%m-%d %H')

        if self.__is_summer_time(time_str, dict_summer_time_borders):
            # INFO: OandaのH4は [1,5,9,13,17,21] を取り得るので、それをはみ出した時間を切り捨て
            minus = ((time.hour + 3) % 4)
        else:
            minus = ((time.hour + 2) % 4)

        time -= datetime.timedelta(hours=minus)
        h4_str = time.strftime('%Y-%m-%d %H:%M:%S')
        return h4_str

    def __is_summer_time(self, time_str, dict_summer_time_borders):
        for i, summertime_dict in enumerate(dict_summer_time_borders):
            if dict_summer_time_borders[-1]['time'] < time_str:
                return dict_summer_time_borders[-1]['summer_time']
            elif summertime_dict['time'] < time_str and time_str < dict_summer_time_borders[i + 1]['time']:
                return summertime_dict['summer_time']

    def __truncate_sec(self, oanda_time_str):
        sec_start = 17
        truncated_str = oanda_time_str[:sec_start] + '00'
        return truncated_str

    def __divide_history_by_type(self, d_frame):
        entry_df = d_frame.dropna(subset=['tradeOpened'])[['price', 'time', 'units']]
        entry_df = entry_df.rename(columns={'price': 'entry_price'})

        close_df = d_frame.dropna(subset=['tradesClosed'])[['price', 'time', 'pl']]
        close_df = close_df.rename(columns={'price': 'close_price'})

        trail_df = d_frame[d_frame.type == 'STOP_LOSS_ORDER'][['price', 'time']]
        trail_df = trail_df.rename(columns={'price': 'stoploss'})
        return entry_df, close_df, trail_df

    def __draw_history(self):
        DRAWABLE_ROWS = 200

        # INFO: データ準備
        d_frame = FXBase.get_candles(start=-DRAWABLE_ROWS, end=None) \
                        .copy().reset_index(drop=True)
        d_frame['sequence'] = d_frame.index
        entry_df = d_frame[['sequence', 'entry_price', 'units']].rename(columns={'entry_price': 'price'})
        close_df = d_frame[['sequence', 'close_price', 'units']].copy().rename(columns={'close_price': 'price'})

        long_df, short_df = entry_df.copy(), entry_df.copy()
        # INFO: Nan は描画されないが None も描画されない
        long_df.loc[long_df.units <= 0, 'price'] = None
        short_df.loc[short_df.units >= 0, 'price'] = None

        # prepare indicators
        self.__ana.calc_indicators()
        self._indicators = self.__ana.get_indicators()

        # INFO: 描画
        drwr = self.__drawer
        drwr.draw_indicators(d_frame=self._indicators[-DRAWABLE_ROWS:None].reset_index(drop=True))

        drwr.draw_vertical_lines(
            indexes=np.concatenate([
                long_df.dropna(subset=['price']).sequence.values,
                short_df.dropna(subset=['price']).sequence.values
            ]),
            vmin=self._indicators['band_-2σ'].min(skipna=True),
            vmax=self._indicators['band_+2σ'].max(skipna=True)
        )

        drwr.draw_positions_df(positions_df=close_df[['sequence', 'price']], plot_type=drwr.PLOT_TYPE['exit'])
        drwr.draw_positions_df(positions_df=long_df[['sequence', 'price']], plot_type=drwr.PLOT_TYPE['long'])
        drwr.draw_positions_df(positions_df=short_df[['sequence', 'price']], plot_type=drwr.PLOT_TYPE['short'])
        drwr.draw_positions_df(
            positions_df=d_frame[['sequence', 'stoploss']].rename(columns={'stoploss': 'price'}),
            plot_type=drwr.PLOT_TYPE['trail']
        )

        drwr.draw_candles(-DRAWABLE_ROWS, None)  # 200本より古い足は消している
        result = drwr.create_png(
            instrument=self.__instrument, granularity='real-trade',
            sr_time=d_frame.time, num=0, filename='hist_figure'
        )
        print(result['success'])
