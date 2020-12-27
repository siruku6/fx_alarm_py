import datetime
import pandas as pd

from models.candle_storage import FXBase
from models.client_manager import ClientManager
from models.analyzer import Analyzer
from models.drawer import FigureDrawer
import models.tools.format_converter as converter


class Librarian():
    DRAWABLE_ROWS = 200

    def __init__(self, instrument=None):
        self.__instrument = instrument or ClientManager.select_instrument()[0]
        self.__client = ClientManager(instrument=self.__instrument)
        self.__ana = Analyzer()
        self._indicators = None

    @property
    def indicators(self):
        return self._indicators

    @indicators.setter
    def indicators(self, indicators):
        self._indicators = indicators

    def visualize_latest_hist(self, granularity):
        transactions = self.__client.prepare_one_page_transactions()
        result = self.__merge_history_and_instruments(transactions, granularity=granularity)

        # INFO: Visualization
        result.to_csv('./tmp/csvs/oanda_trade_hist.csv', index=False)
        self.__draw_history()

    def serve_analysis_object(self, from_datetime):
        transactions = self.__client.request_massive_transactions(from_datetime=from_datetime)
        result = self.__merge_history_and_instruments(transactions, granularity='H1')
        return result

    def __merge_history_and_instruments(self, history_df, granularity='M10'):
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
        history_df.loc[:, 'price'] = history_df.price.astype('float32')
        candles = self.__prepare_candles(log_oldest_time=history_df.iloc[0].time, granularity=granularity)
        print('[Libra] candles and trade-logs are loaded')

        history_df = self.__adjust_time_for_merging(candles, history_df, granularity)

        # prepare pl_and_gross
        pl_and_gross_df = self.__calc_pl_gross(granularity, history_df[['time', 'pl', 'dst']])
        history_df.drop('pl', axis=1, inplace=True)  # pl カラムは1つあれば十分

        result = self.__merge_hist_dfs(candles, history_df, pl_and_gross_df)
        result['stoploss'] = self.__fill_stoploss(result.copy())
        FXBase.set_candles(result)
        print('[Libra] candles and trade-history are merged')

        # prepare indicators
        self.__ana.calc_indicators(candles=result)
        self.indicators = self.__ana.get_indicators()
        print('[Libra] and indicators are merged')

        return pd.merge(result, self.indicators, on='time', how='left')

    # def prepare_one_page_transactions(self):
    #     # INFO: lastTransactionIDを取得するために実行
    #     self.__client.request_open_trades()

    #     # preapre history_df: trade-history
    #     history_df = self.__client.request_latest_transactions()
    #     history_df.to_csv('./tmp/csvs/hist_positions.csv', index=False)
    #     return history_df

    # def request_massive_transactions(self, from_datetime):
    #     gained_transactions = []
    #     from_id, to_id = self.__client.request_transaction_ids(from_str=from_datetime)

    #     while True:
    #         print('[INFO] requesting {}..{}'.format(from_id, to_id))

    #         response = self.__client.request_transactions_once(from_id, to_id)
    #         tmp_transactons = response['transactions']
    #         gained_transactions += tmp_transactons
    #         # INFO: ループの終了条件
    #         #   'to' に指定した ID の transaction がない時が多々あり、
    #         #   その場合、transactions を取得できないので、ごくわずかな数になる。
    #         #   そこまで来たら処理終了
    #         if len(tmp_transactons) <= 10 or tmp_transactons[-1]['id'] == to_id:
    #             break

    #         print('[INFO] last_transaction_id {}'.format(tmp_transactons[-1]['id']))
    #         gained_last_transaction_id = tmp_transactons[-1]['id']
    #         from_id = str(int(gained_last_transaction_id) + 1)

    #     filtered_df = prepro.filter_and_make_df(gained_transactions, self.__instrument)
    #     return filtered_df

    #
    # Private
    #
    def __prepare_candles(self, log_oldest_time, granularity):
        now_dt = datetime.datetime.utcnow()
        buffer_timedelta_by_20candles = converter.granularity_to_timedelta(granularity) * 20
        start_dt = pd.to_datetime(log_oldest_time) - buffer_timedelta_by_20candles

        result = self.__client.load_candles_by_duration(start=start_dt, end=now_dt, granularity=granularity)
        return result['candles']

    def __adjust_time_for_merging(self, candles, history_df, granularity):
        dict_dst_switches = None
        if granularity in ('H4',):
            # TODO: dict_dst_switches は H4 candles でのみしか使えない形になっている
            dict_dst_switches = self.__detect_dst_switches(candles)
            history_df = self.__append_dst_column(history_df, dst_switches=dict_dst_switches)
        else:
            history_df.loc[:, 'dst'] = None

        # make time smooth, adaptively to Daylight Saving Time
        if granularity == 'M10':  # TODO: M15, 30 も対応できるようにする
            history_df['time'] = [converter.convert_to_m10(time) for time in history_df.time]
        elif granularity in ('H1', 'H4'):
            history_df['time'] = [self.__convert_time_str_to(granularity, time, dict_dst_switches) for time in history_df.time]
        return history_df

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
            is_dst = dst_switching_point['summer_time']
            if i == (switch_count - 1):
                target_row_index = dst_switching_point['time'] <= hist_df['time']
            else:
                target_row_index = (dst_switching_point['time'] <= hist_df['time']) \
                    & (hist_df['time'] < dst_switches[i + 1]['time'])
            hist_df.loc[target_row_index, 'dst'] = is_dst

        hist_df['dst'] = hist_df['dst'].astype(bool)
        return hist_df

    def __convert_time_str_to(self, granularity, oanda_time, dict_dst_switches=None):
        time_str = oanda_time.replace('T', ' ')
        # INFO: 12文字目までで hour まで取得できる
        time = datetime.datetime.strptime(time_str[:13], '%Y-%m-%d %H')

        # INFO: adjust according to day light saving time
        if granularity in ('H4',):
            if self.__is_summer_time(time_str, dict_dst_switches):
                # INFO: OandaのH4は [1,5,9,13,17,21] を取り得るので、それをはみ出した時間を切り捨て
                minus = ((time.hour + 3) % 4)
            else:
                minus = (time.hour % 4)
            time -= datetime.timedelta(hours=minus)

        hour_str = time.strftime('%Y-%m-%d %H:%M:%S')
        return hour_str

    def __is_summer_time(self, time_str, dict_dst_switches):
        for i, switch_dict in enumerate(dict_dst_switches):
            if dict_dst_switches[-1]['time'] < time_str:
                return dict_dst_switches[-1]['summer_time']
            elif switch_dict['time'] < time_str and time_str < dict_dst_switches[i + 1]['time']:
                return switch_dict['summer_time']

    def __calc_pl_gross(self, granularity, original_df):
        '''
        Parameters
        ----------
        granularity : string
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
        if granularity in ('H4',):
            pl_gross_hist = self.__downsample_pl_df(pl_df=original_df)
        elif granularity in ('H1',):
            pl_gross_hist = self.__resample_by('1H', original_df.copy())
        else:
            pl_gross_hist = original_df.copy()
        pl_gross_hist.reset_index(inplace=True)
        pl_gross_hist.loc[:, 'time'] = pl_gross_hist['time'].astype({'time': str})
        pl_gross_hist.loc[:, 'gross'] = pl_gross_hist['pl'].cumsum()
        return pl_gross_hist

    def __downsample_pl_df(self, pl_df):
        # time 列の調節と resampling
        hist_dst_on = self.__resample_by('4H', pl_df[pl_df['dst']].copy(), base=1)
        hist_dst_off = self.__resample_by('4H', pl_df[~pl_df['dst']].copy(), base=0)
        return hist_dst_on.append(hist_dst_off).sort_index()

    def __resample_by(self, rule, target_df, base=0):
        target_df.loc[:, 'time'] = pd.to_datetime(target_df['time'])
        if target_df.empty:
            return target_df[[]]

        return target_df.resample(rule, on='time', base=base).sum()

    def __merge_hist_dfs(self, candles, history_df, pl_and_gross_df):
        tmp_positions_df = self.__extract_positions_df_from(history_df)
        result = pd.merge(candles, tmp_positions_df, on='time', how='outer', right_index=True)
        result = pd.merge(result, pl_and_gross_df, on='time', how='left').drop_duplicates(['time'])
        result['pl'].fillna(0, inplace=True)
        result['gross'].fillna(0, inplace=True)
        return result

    def __extract_positions_df_from(self, d_frame):
        tmp_positions_df = d_frame.dropna(subset=['tradeOpened'])[['price', 'time', 'units']].copy() \
                                  .rename(columns={'price': 'long'})
        tmp_positions_df['short'] = tmp_positions_df['long'].copy()
        exits = d_frame.dropna(subset=['tradesClosed'])[['price', 'time']].copy() \
            .rename(columns={'price': 'exit'})
        stoplosses = d_frame[d_frame.type == 'STOP_LOSS_ORDER'][['price', 'time']].copy() \
            .rename(columns={'price': 'stoploss'})
        tmp_positions_df = pd.merge(tmp_positions_df, exits, on='time', how='outer', right_index=True)
        tmp_positions_df = pd.merge(tmp_positions_df, stoplosses, on='time', how='outer', right_index=True)
        tmp_positions_df['units'] = tmp_positions_df['units'].fillna('0').astype(int)

        # INFO: remove unused records & values
        tmp_positions_df = tmp_positions_df.sort_values('time') \
                                           .drop_duplicates('time')
        # INFO: Nan は描画されないが None も描画されない
        tmp_positions_df.loc[tmp_positions_df.units <= 0, 'long'] = None
        tmp_positions_df.loc[tmp_positions_df.units >= 0, 'short'] = None

        return tmp_positions_df  # , exit_df, trail_df

    def __fill_stoploss(self, hist_df):
        ''' entry ~ exit の間の stoploss を補完 '''
        hist_df.loc[pd.notna(hist_df['exit'].shift(1)), 'entried'] = False
        is_long_or_short = hist_df[['long', 'short']].any(axis=1)
        hist_df.loc[is_long_or_short, 'entried'] = True
        hist_df['entried'] = hist_df['entried'].fillna(method='ffill') \
                                               .fillna(False)
        hist_df['stoploss'] = hist_df.loc[hist_df['entried'], 'stoploss'].fillna(method='ffill')
        return hist_df.loc[:, 'stoploss']

    def __draw_history(self):
        # INFO: データ準備
        candles_and_hist = FXBase.get_candles(start=-Librarian.DRAWABLE_ROWS, end=None) \
                                 .copy().reset_index(drop=True)
        # TODO: candles_and_hist にも indicators データが丸々入っているので、次の行は修正した方がよい
        drawn_indicators = self.indicators[-Librarian.DRAWABLE_ROWS:None]

        # - - - - - - - - - - - - - - - - - - - -
        #                  描画
        # - - - - - - - - - - - - - - - - - - - -
        drawer = FigureDrawer(rows_num=3, instrument=self.__instrument)
        drawer.draw_indicators(d_frame=drawn_indicators.reset_index(drop=True))

        drawer.draw_vertical_lines(
            indexes=candles_and_hist[['long', 'short']].dropna(how='all').index,
            vmin=drawn_indicators['band_-2σ'].min(skipna=True),
            vmax=drawn_indicators['band_+2σ'].max(skipna=True)
        )

        for column_name in ['long', 'short', 'exit']:
            drawer.draw_positions_df(
                positions_df=candles_and_hist[[column_name]].rename(columns={column_name: 'price'}),
                plot_type=drawer.PLOT_TYPE[column_name]
            )
        drawer.draw_positions_df(
            positions_df=candles_and_hist[['stoploss']].rename(columns={'stoploss': 'price'}),
            plot_type=drawer.PLOT_TYPE['trail']
        )

        # axis3
        candles_and_hist['gross'].fillna(method='ffill', inplace=True)
        drawer.draw_df_on_plt(
            candles_and_hist[['gross', 'pl']],
            drawer.PLOT_TYPE['bar'], colors=['orange', 'yellow'], plt_id=3
        )

        target_candles = candles_and_hist.iloc[-Librarian.DRAWABLE_ROWS:, :]  # 200本より古い足は消している
        drawer.draw_candles(target_candles)
        result = drawer.create_png(
            granularity='real-trade',
            sr_time=candles_and_hist.time, num=0, filename='hist'
        )
        drawer.close_all()
        print(result['success'])
