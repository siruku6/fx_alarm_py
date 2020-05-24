import datetime
import numpy as np
import pandas as pd
from models.oanda_py_client import FXBase, OandaPyClient
from models.analyzer import Analyzer
from models.drawer import FigureDrawer


class Librarian():
    DRAWABLE_ROWS = 200

    def __init__(self):
        self.__instrument, _ = OandaPyClient.select_instrument()
        self.__client = OandaPyClient(instrument=self.__instrument)
        self.__ana = Analyzer()
        self.__drawer = FigureDrawer(rows_num=3)
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

        candles = self.__prepare_candles(log_oldest_time=history_df.iloc[0].time, granularity=granularity)
        print('[Libra] candles are loaded')

        # TODO: dict_dst_switches は H4 candles でのみしか使えない形になっている
        dict_dst_switches = self.__detect_dst_switches(candles)
        history_df = self.__append_dst_column(history_df, dst_switches=dict_dst_switches)
        history_df.to_csv('./tmp/csvs/hist_positions.csv', index=False)
        print('[Libra] trade_log is loaded')

        # prepare pl_and_gross
        pl_and_gross_df = self.__calc_pl_gross(history_df[['time', 'pl', 'dst']])
        history_df.drop('pl', axis=1, inplace=True)  # pl カラムは1つあれば十分

        # make time smooth, adaptively to Daylight Saving Time
        if granularity == 'M10':
            history_df['time'] = [self.__convert_to_m10(time) for time in history_df.time]
        elif granularity == 'H4':
            history_df['time'] = [self.__convert_to_h4(time, dict_dst_switches) for time in history_df.time]

        result = self.__merge_hist_dfs(candles, history_df, pl_and_gross_df)
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
    def __prepare_candles(self, log_oldest_time, granularity):
        dt_a_month_ago = pd.to_datetime(log_oldest_time) - datetime.timedelta(days=30)
        starttime_str = dt_a_month_ago.strftime('%Y-%m-%d %H:%M:%S')

        today_dt = datetime.datetime.now() - datetime.timedelta(hours=9)
        start_dt = datetime.datetime.strptime(starttime_str, '%Y-%m-%d %H:%M:%S')
        days_wanted = (today_dt - start_dt).days + 1
        result = self.__client.load_long_chart(days=days_wanted, granularity=granularity)
        return result['candles']

    def __detect_dst_switches(self, candles):
        '''
        daylight saving time の切り替わりタイミングを見つける
        '''
        candles['summer_time'] = pd.to_numeric(candles.time.str[12], downcast='signed') % 2 == 1
        switch_points = candles[candles.summer_time != candles.summer_time.shift(1)][['time', 'summer_time']]
        return switch_points.to_dict('records')

    def __append_dst_column(self, original_df, dst_switches):
        '''
        dst is Daylight Saving Time

        Parameters
        ----------
        dst_switches : array of dict
            sample: [
                {'time': '2020-02-17 06:00:00', 'summer_time': False},
                {'time': '2020-03-12 17:00:00', 'summer_time': True},
                ...
            ]
        '''
        hist_df = original_df.copy()
        switch_count = len(dst_switches)

        for i, dst_switching_point in enumerate(dst_switches):
            is_dst = True if dst_switching_point['summer_time'] else False
            if i == (switch_count - 1):
                target_row_index = dst_switching_point['time'] <= hist_df['time']
            else:
                target_row_index = (dst_switching_point['time'] <= hist_df['time']) \
                    & (hist_df['time'] < dst_switches[i + 1]['time'])
            hist_df.loc[target_row_index, 'dst'] = is_dst

        return hist_df

    def __convert_to_m10(self, oanda_time):
        m1_pos = 15
        m10_str = oanda_time[:m1_pos] + '0' + oanda_time[m1_pos + 1:]
        m10_str = self.__truncate_sec(m10_str).replace('T', ' ')
        return m10_str

    def __convert_to_h4(self, oanda_time, dict_dst_switches):
        time_str = oanda_time.replace('T', ' ')

        # INFO: 12文字目までで hour まで取得できる
        time = datetime.datetime.strptime(time_str[:13], '%Y-%m-%d %H')

        if self.__is_summer_time(time_str, dict_dst_switches):
            # INFO: OandaのH4は [1,5,9,13,17,21] を取り得るので、それをはみ出した時間を切り捨て
            minus = ((time.hour + 3) % 4)
        else:
            minus = ((time.hour + 2) % 4)

        time -= datetime.timedelta(hours=minus)
        h4_str = time.strftime('%Y-%m-%d %H:%M:%S')
        return h4_str

    def __is_summer_time(self, time_str, dict_dst_switches):
        for i, switch_dict in enumerate(dict_dst_switches):
            if dict_dst_switches[-1]['time'] < time_str:
                return dict_dst_switches[-1]['summer_time']
            elif switch_dict['time'] < time_str and time_str < dict_dst_switches[i + 1]['time']:
                return switch_dict['summer_time']

    def __truncate_sec(self, oanda_time_str):
        sec_start = 17
        truncated_str = oanda_time_str[:sec_start] + '00'
        return truncated_str

    def __merge_hist_dfs(self, candles, history_df, pl_and_gross_df):
        entry_df, close_df, trail_df = self.__divide_history_by_type(history_df)

        result = pd.merge(candles, entry_df, on='time', how='outer', right_index=True)
        result = pd.merge(result, close_df, on='time', how='outer', right_index=True)
        result = pd.merge(result, trail_df, on='time', how='outer', right_index=True)
        result = pd.merge(result, pl_and_gross_df, on='time', how='left').drop_duplicates(['time'])
        result['units'] = result.units.fillna('0').astype(int)
        return result

    def __divide_history_by_type(self, d_frame):
        entry_df = d_frame.dropna(subset=['tradeOpened'])[['price', 'time', 'units']] \
                          .rename(columns={'price': 'entry_price'})
        close_df = d_frame.dropna(subset=['tradesClosed'])[['price', 'time']] \
                          .rename(columns={'price': 'close_price'})
        trail_df = d_frame[d_frame.type == 'STOP_LOSS_ORDER'][['price', 'time']] \
            .rename(columns={'price': 'stoploss'})
        return entry_df, close_df, trail_df

    def __calc_pl_gross(self, original_df):
        '''
        Parameters
        ----------
        original_df : dataframe
            .index -> name: time, type: datetime
            .columns -> [
                'pl', # integer
                'dst' # boolean
            ]
        Returns
        ----------
        pl_gross_hist : dataframe
        '''
        pl_gross_hist = self.__downsample_pl_df(pl_df=original_df)
        pl_gross_hist.reset_index(inplace=True)
        pl_gross_hist.loc[:, 'time'] = pl_gross_hist['time'].astype({'time': str})
        pl_gross_hist.loc[:, 'gross'] = pl_gross_hist['pl'].cumsum()
        return pl_gross_hist

    def __downsample_pl_df(self, pl_df):
        # time 列の調節と resampling
        hist_dst_on = self.__resample_by_h4(pl_df[pl_df['dst']].copy(), base=1)
        hist_dst_off = self.__resample_by_h4(pl_df[pl_df['dst'] == False].copy(), base=2)
        return hist_dst_on.append(hist_dst_off).sort_index()

    def __resample_by_h4(self, target_df, base=0):
        target_df.loc[:, 'time'] = pd.to_datetime(target_df['time'])
        if target_df.empty:
            return target_df[[]]

        return target_df.resample('4H', on='time', base=base).sum()

    def __draw_history(self):
        # INFO: データ準備
        d_frame = FXBase.get_candles(start=-Librarian.DRAWABLE_ROWS, end=None) \
                        .copy().reset_index(drop=True)
        d_frame['sequence'] = d_frame.index
        long_df, short_df, close_df = self.__prepare_position_dfs(d_frame)

        # prepare indicators
        self.__ana.calc_indicators(candles=d_frame)
        self._indicators = self.__ana.get_indicators()

        # - - - - - - - - - - - - - - - - - - - -
        #                  描画
        # - - - - - - - - - - - - - - - - - - - -
        drwr = self.__drawer
        drwr.draw_indicators(d_frame=self._indicators[-Librarian.DRAWABLE_ROWS:None].reset_index(drop=True))

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

        # axis3
        d_frame['gross'].fillna(method='ffill', inplace=True)
        drwr.draw_df_on_plt(d_frame[['gross']], drwr.PLOT_TYPE['bar'], color='orange', plt_id=3)
        drwr.draw_df_on_plt(d_frame[['pl']], drwr.PLOT_TYPE['bar'], color='yellow', plt_id=3)

        drwr.draw_candles(start=-Librarian.DRAWABLE_ROWS, end=None)  # 200本より古い足は消している
        result = drwr.create_png(
            instrument=self.__instrument, granularity='real-trade',
            sr_time=d_frame.time, num=0, filename='hist'
        )
        print(result['success'])

    def __prepare_position_dfs(self, df):
        entry_df = df[['sequence', 'entry_price', 'units']].rename(columns={'entry_price': 'price'})
        close_df = df[['sequence', 'close_price', 'units']].copy().rename(columns={'close_price': 'price'})

        long_df, short_df = entry_df.copy(), entry_df.copy()
        # INFO: Nan は描画されないが None も描画されない
        long_df.loc[long_df.units <= 0, 'price'] = None
        short_df.loc[short_df.units >= 0, 'price'] = None
        return long_df, short_df, close_df
