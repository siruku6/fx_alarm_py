import datetime
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
            history_df['time'] = [self.__convert_to_m10(time) for time in history_df.time]
        elif granularity == 'H4':
            history_df['time'] = [self.__convert_to_h4(time) for time in history_df.time]
        entry_df, close_df, trail_df = self.__divide_history_by_type(history_df)

        # INFO: instrumentによってはhistory_dfが空
        if history_df.empty:
            dt_a_month_ago = datetime.datetime.now() - datetime.timedelta(days=30)
            start_str = dt_a_month_ago.strftime('%Y-%m-%d %H:%M:%S')
        else:
            start_str = history_df.iat[0,9]  # dataframe 1行目のtimeを取得

        candles = self.__prepare_candles(
            starttime_str=start_str,
            granularity=granularity
        )
        print('[Libra] candles are loaded')

        # merge
        result = pd.merge(candles, entry_df, on='time', how='outer', right_index=True)
        result = pd.merge(result, close_df, on='time', how='outer', right_index=True)
        result = pd.merge(result, trail_df, on='time', how='outer', right_index=True)
        result = result.drop_duplicates(['time'])
        result['units'] = result.units.fillna('0').astype(int)
        FXBase.set_candles(result)
        print('[Libra] candles and trade-history is merged')

        # INFO: Visualization
        result.to_csv('./tmp/oanda_trade_hist.csv', index=False)
        self.__draw_history()
        self.__drawer.close_all()

        return result

    #
    # Private
    #
    def __convert_to_m10(self, oanda_time):
        m1_pos = 15
        m10_str = oanda_time[:m1_pos] + '0' + oanda_time[m1_pos + 1:]
        m10_str = self.__truncate_sec(m10_str).replace('T', ' ')
        return m10_str

    def __convert_to_h4(self, oanda_time):
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

    def __prepare_candles(self, starttime_str, granularity):
        today_dt = datetime.datetime.now() - datetime.timedelta(hours=9)
        start_dt = datetime.datetime.strptime(starttime_str, '%Y-%m-%d %H:%M:%S')
        days_wanted = (today_dt - start_dt).days + 1
        result = self.__client.load_long_chart(days=days_wanted, granularity=granularity)
        return result['candles']

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
        # INFO: 本当は None ではなく Nan にすれば表示されないが、 None でも表示されない
        long_df.loc[long_df.units <= 0, 'price'] = None
        short_df.loc[short_df.units >= 0, 'price'] = None

        # prepare indicators
        self.__ana.calc_indicators()
        self._indicators = self.__ana.get_indicators()

        # INFO: 描画
        drwr = self.__drawer
        drwr.draw_candles(-DRAWABLE_ROWS, None)  # 200本より古い足は消している
        drwr.draw_indicators(d_frame=self._indicators[-DRAWABLE_ROWS:None].reset_index(drop=True))

        drwr.draw_positions_df(
            positions_df=long_df[['sequence', 'price']], plot_type=drwr.PLOT_TYPE['long']
        )
        drwr.draw_positions_df(
            positions_df=short_df[['sequence', 'price']], plot_type=drwr.PLOT_TYPE['short']
        )
        drwr.draw_positions_df(
            positions_df=d_frame[['sequence', 'stoploss']], plot_type=drwr.PLOT_TYPE['trail']
        )
        drwr.draw_positions_df(
            positions_df=close_df[['sequence', 'price']], plot_type=drwr.PLOT_TYPE['exit']
        )
        result = drwr.create_png(instrument=self.__instrument, granularity='real-trade', sr_time=d_frame.time, num=0)
        print(result['success'])
