import math, os
import numpy as np
import pandas as pd
from models.oanda_py_client import FXBase, OandaPyClient
from models.analyzer import Analyzer
from models.drawer import FigureDrawer

class Trader():
    def __init__(self, operation='verification'):
        if operation is 'custom' or operation is 'verification':
            inst = OandaPyClient.select_instrument()
            self.__instrument = inst['name']
            self.__static_spread = inst['spread']
        else:
            self.__instrument = os.environ.get('INSTRUMENT') or 'USD_JPY'
            self.__static_spread = 0.0

        self._client  = OandaPyClient(instrument=self.__instrument)
        self.__ana    = Analyzer()
        self.__drawer = FigureDrawer()
        self.__columns = ['sequence', 'price', 'stoploss', 'type', 'time', 'profit']
        self.__granularity = os.environ.get('GRANULARITY') or 'M5'
        sl_buffer = round(float(os.environ.get('STOPLOSS_BUFFER')), 2)
        self._STOPLOSS_BUFFER_pips = sl_buffer or 0.05

        if operation is 'custom':
            self.__request_custom_candles()
            self._client.request_current_price()
        elif operation is 'live':
            result = self._client.request_is_tradeable()
            self.tradeable = result['tradeable']
            if self.tradeable == False:
                print('[Trader] 市場が開いていないため、処理を終了します')
                self.__drawer.close_all()
                return

            self._client.load_long_chart(days=1, granularity=self.__granularity)
            # OPTIMIZE: これがあるせいで意外とトレードが発生しない
            self._client.request_current_price()

        result = self.__ana.calc_indicators()
        if 'error' in result:
            print(result['error'])
            return

        print(result['success'])
        self._indicators = self.__ana.get_indicators()
        self.__initialize_position_variables()

    def __initialize_position_variables(self):
        self._position = { 'type': 'none' }
        self.__hist_positions = { 'long': [], 'short': [] }

    #
    # public
    #
    def get_instrument(self):
        return self.__instrument

    def auto_verify_trading_rule(self, accurize=False):
        ''' tradeルールを自動検証 '''
        print(self.__demo_swing_trade()['success'])
        if accurize and (self.__granularity[0] is not 'M'):
            print(self.__accurize_entry_prices()['success'])

    def verify_varios_stoploss(self, accurize=False):
        ''' StopLossの設定値を自動でスライドさせて損益を検証 '''
        verification_dataframes_array = []

        stoploss_buffer_list = np.append(
            np.round(np.arange(0.01, 0.10, 0.02), decimals=2), [0.50]
        )
        for sl in stoploss_buffer_list:
            print('[Trader] stoploss buffer: {}pipsで検証開始...'.format(sl))
            self._STOPLOSS_BUFFER_pips = sl
            self.auto_verify_trading_rule(accurize=True)

            self.__calc_profit()
            _df = pd.concat(
                [ pd.DataFrame(self.__hist_positions['long'],  columns=self.__columns),
                  pd.DataFrame(self.__hist_positions['short'], columns=self.__columns) ],
                axis=1, keys=['long', 'short'],
                names=['type', '-']
            )
            verification_dataframes_array.append(_df)

        result = pd.concat(
            verification_dataframes_array,
            axis=1, keys=stoploss_buffer_list,
            names=['SL_buffer']
        )
        result.to_csv('./sl_verify_{inst}.csv'.format(inst=self.get_instrument()))

    def draw_chart(self):
        ''' チャートや指標をpngに描画 '''
        drwr = self.__drawer
        drwr.draw_df_on_plt(df=self._indicators.loc[:, ['20SMA']],    plot_type=drwr.PLOT_TYPE['simple-line'], color='lightskyblue')
        drwr.draw_df_on_plt(df=self._indicators.loc[:, ['10EMA']],    plot_type=drwr.PLOT_TYPE['simple-line'], color='cyan')
        drwr.draw_df_on_plt(df=self._indicators.loc[:, ['band_+2σ']], plot_type=drwr.PLOT_TYPE['simple-line'], color='royalblue')
        drwr.draw_df_on_plt(df=self._indicators.loc[:, ['band_-2σ']], plot_type=drwr.PLOT_TYPE['simple-line'], color='royalblue')
        drwr.draw_df_on_plt(df=self._indicators.loc[:, ['band_+3σ']], plot_type=drwr.PLOT_TYPE['simple-line'], color='lightcyan')
        drwr.draw_df_on_plt(df=self._indicators.loc[:, ['band_-3σ']], plot_type=drwr.PLOT_TYPE['simple-line'], color='lightcyan')
        drwr.draw_df_on_plt(df=self._indicators.loc[:, ['SAR']],      plot_type=drwr.PLOT_TYPE['dot'],         color='purple')
        # drwr.draw_df_on_plt(df=self.desc_trends, plot_type=drwr.PLOT_TYPE['dashed-line'], color='navy')
        # drwr.draw_df_on_plt(df=self.asc_trends,  plot_type=drwr.PLOT_TYPE['dashed-line'], color='navy')
        # drwr.draw_indexes_on_plt(index_array=self.jump_trendbreaks,   plot_type=drwr.PLOT_TYPE['break'], pos=drwr.POS_TYPE['over'])
        # drwr.draw_indexes_on_plt(index_array=self.fall_trendbreaks,   plot_type=drwr.PLOT_TYPE['break'], pos=drwr.POS_TYPE['beneath'])
        drwr.draw_candles()
        df_pos = {
            'long':  pd.DataFrame(self.__hist_positions['long'],  columns=self.__columns),
            'short': pd.DataFrame(self.__hist_positions['short'], columns=self.__columns)
        }
        drwr.draw_positionDf_on_plt(df=df_pos['long'][df_pos['long'].type=='long'],    plot_type=drwr.PLOT_TYPE['long'])
        drwr.draw_positionDf_on_plt(df=df_pos['long'][df_pos['long'].type=='trail'],   plot_type=drwr.PLOT_TYPE['trail'])
        drwr.draw_positionDf_on_plt(df=df_pos['long'][df_pos['long'].type=='close'],   plot_type=drwr.PLOT_TYPE['exit'])
        drwr.draw_positionDf_on_plt(df=df_pos['short'][df_pos['short'].type=='short'], plot_type=drwr.PLOT_TYPE['short'])
        drwr.draw_positionDf_on_plt(df=df_pos['short'][df_pos['short'].type=='trail'], plot_type=drwr.PLOT_TYPE['trail'])
        drwr.draw_positionDf_on_plt(df=df_pos['short'][df_pos['short'].type=='close'], plot_type=drwr.PLOT_TYPE['exit'])
        result = drwr.create_png()
        if 'success' in result: print(result['success'])
        return {
            'success': '[Trader] チャート分析、png生成完了',
            # メール送信フラグ: 今は必要ない
            'alart_necessary': False
        }

    def report_trading_result(self):
        ''' ポジション履歴をcsv出力 '''
        self.__calc_profit()

        df_long = pd.DataFrame.from_dict(self.__hist_positions['long'])
        df_short = pd.DataFrame.from_dict(self.__hist_positions['short'])
        df_long.to_csv('./long_history.csv')
        df_short.to_csv('./short_history.csv')

        print('[Trader] ポジション履歴をcsv出力完了')

    #
    # Shared with subclass
    #
    def _check_trend(self, index, c_price):
        '''
        ルールに基づいてトレンドの有無を判定
        '''
        sma    = self._indicators['20SMA'][index]
        ema    = self._indicators['10EMA'][index]
        parabo = self._indicators['SAR'][index]
        if sma    < ema     and \
           ema    < c_price and \
           parabo < c_price:
            trend = 'bull'
        elif sma    > ema     and \
             ema    > c_price and \
             parabo > c_price:
            trend = 'bear'
        else:
            trend = None
        print('[Trader] trend: {}'.format(trend))
        return trend

    def _find_thrust(self, i, trend):
        '''
        thrust発生の有無と方向を判定して返却する
        '''
        candles = FXBase.get_candles()[['high', 'low']]
        if trend == 'bull' and candles.high[i] > candles.high[i-1]:
            direction = 'long'
        elif trend == 'bear' and candles.low[i] < candles.low[i-1]:
            direction = 'short'
        else:
            direction = None
        print('[Trader] thrust: {}'.format(direction))
        return direction

    def _judge_settle_position(self, i, c_price):
        candles        = FXBase.get_candles()
        parabolic      = self._indicators['SAR']
        position_type  = self._position['type']
        stoploss_price = self._position['stoploss']
        if position_type == 'long':
            if candles.low[i-1] - self._STOPLOSS_BUFFER_pips > stoploss_price:
                stoploss_price = candles.low[i-1] - self._STOPLOSS_BUFFER_pips
                self._trail_stoploss(
                    index=i, new_SL=stoploss_price, time=candles.time[i]
                )
            if stoploss_price > candles.low[i]:
                self._settle_position(
                    index=i, price=stoploss_price, time=candles.time[i]
                )
            elif parabolic[i] > c_price:
                self._settle_position(
                    index=i, price=c_price, time=candles.time[i]
                )
        elif position_type == 'short':
            if candles.high[i-1] + self._STOPLOSS_BUFFER_pips < stoploss_price:
                stoploss_price = candles.high[i-1] + self._STOPLOSS_BUFFER_pips
                self._trail_stoploss(
                    index=i, new_SL=stoploss_price, time=candles.time[i]
                )
            if stoploss_price < candles.high[i] + self.__static_spread:
                self._settle_position(
                    index=i, price=stoploss_price, time=candles.time[i]
                )
            elif parabolic[i] < c_price + self.__static_spread:
                self._settle_position(
                    index=i, price=c_price + self.__static_spread, time=candles.time[i]
                )

    #
    # private
    #

    def __request_custom_candles(self):
        # Custom request
        print('何日分のデータを取得する？(半角数字): ', end='')
        days = int(input())
        if days > 365:
            print('[ALERT] 現在は365日までに制限しています')
            exit()

        print('取得スパンは？(ex: M5): ', end='')
        self.__granularity = str(input())

        result = self._client.load_long_chart(
            days=days,
            granularity=self.__granularity
        )
        if 'error' in result:
            print(result['error'])
            exit()
        # FXBase.set_candles(result['candles'])

    def __demo_swing_trade(self):
        ''' スイングトレードのentry pointを検出 '''
        sma = self._indicators['20SMA']
        # INFO: 繰り返しデモする場合に前回のpositionが残っているので、リセットする
        self.__initialize_position_variables()

        close_candles = FXBase.get_candles().close
        candle_length = len(close_candles)
        for index, close_price in enumerate(close_candles):
            print('[Trader] progress... {i}/{total}'.format(i=index, total=candle_length))
            self._position['sequence'] = index
            if self._position['type'] == 'none':
                if math.isnan(sma[index]): continue

                trend = self._check_trend(index, close_price)
                if trend is None: continue

                direction = self._find_thrust(index, trend)
                if direction is None: continue

                self._create_position(index, direction)
            else:
                self._judge_settle_position(index, close_price)

        return { 'success': '[Trader] 売買判定終了' }

    def _create_position(self, index, direction):
        '''
        ルールに基づいてポジションをとる(検証用)
        '''
        candles = FXBase.get_candles()
        if direction == 'long':
            # OPTIMIZE: entry_priceが甘い。 candles.close[index] でもいいかも
            entry_price = candles.high[index-1] + self.__static_spread
            stoploss    = candles.low[index-1] - self._STOPLOSS_BUFFER_pips
        elif direction == 'short':
            entry_price = candles.low[index-1]
            stoploss    = candles.high[index-1] + self._STOPLOSS_BUFFER_pips

        self._position = {
            'sequence': index, 'price': entry_price, 'stoploss': stoploss,
            'type': direction, 'time': candles.time[index]
        }
        self.__hist_positions[direction].append(self._position.copy())

    def _trail_stoploss(self, index, new_SL, time):
        direction = self._position['type']
        self._position['stoploss']      = new_SL
        position_after_trailing         = self._position.copy()
        position_after_trailing['type'] = 'trail'
        position_after_trailing['time'] = time
        self.__hist_positions[direction].append(position_after_trailing)

    def _settle_position(self, index, price, time):
        '''
        ポジション解消の履歴を残す

        Parameters
        ----------
        index : int
            ポジションを解消するタイミングを表す
        price : float
            ポジション解消時の価格
        time : string
            ポジションを解消する日（時）

        Returns
        -------
        None
        '''
        direction = self._position['type']
        self._position = { 'type': 'none' }
        self.__hist_positions[direction].append({
            'sequence': index, 'price': price,
            'stoploss': 0.0, 'type': 'close', 'time': time
        })

    def __accurize_entry_prices(self):
        '''
        ポジション履歴のエントリーpriceを、実際にエントリー可能な価格に修正する
        '''
        # TODO: 総リクエスト数と所要時間、rpsをこまめに表示した方がよさそう
        # long価格の修正
        for i, row in enumerate(self.__hist_positions['long']):
            if row['type'] == 'long':
                M10_candles = self._client.request_specified_candles(
                    start_datetime=row['time'][:19],
                    granularity='M10',
                    base_granurarity=self.__granularity
                )
                for j, M10_row in M10_candles.iterrows():
                    if row['price'] < M10_row.high:
                        old_price = row['price']
                        row['price'] = M10_row.high
                        row['time'] = M10_row.time
                        self.__chain_accurization(
                            i, type='long', old_price=old_price, accurater_price=M10_row.high
                        )
                        break

        # short価格の修正
        for i, row in enumerate(self.__hist_positions['short']):
            if row['type'] == 'short':
                M10_candles = self._client.request_specified_candles(
                    start_datetime=row['time'][:19],
                    granularity='M10',
                    base_granurarity=self.__granularity
                )
                for j, M10_row in M10_candles.iterrows():
                    if row['price'] > M10_row.low:
                        old_price = row['price']
                        row['price'] = M10_row.low
                        row['time'] = M10_row.time
                        self.__chain_accurization(
                            i, type='short', old_price=old_price, accurater_price=M10_row.low
                        )
                        break

        return { 'success': '[Trader] entry価格を、現実的に取引可能な値に修正' }

    def __chain_accurization(self, index, type, old_price, accurater_price):
        index += 1
        while (self.__hist_positions[type][index]['price'] == old_price):
            self.__hist_positions[type][index]['price'] = accurater_price
            index += 1

    def __calc_profit(self):
        '''
        ポジション履歴から総損益を算出する
        '''
        # longエントリーの損益を計算
        long_hist = self.__hist_positions['long']
        for i, row in enumerate(long_hist):
            if row['type'] == 'close':
                row['profit'] = row['price'] - long_hist[i-1]['price']

        # shortエントリーの損益を計算
        short_hist = self.__hist_positions['short']
        for i, row in enumerate(short_hist):
            if row['type'] == 'close':
                row['profit'] = short_hist[i-1]['price'] - row['price']

        hist_array = long_hist + short_hist
        profit_array =  [
            row['profit'] for row in hist_array if row['type'] == 'close'
        ]
        print('[合計損益] {profit}pips'.format(
            profit=round(sum(profit_array) * 100, 3)
        ))

class RealTrader(Trader):
    def __init__(self, operation='verification'):
        super(RealTrader, self).__init__(operation=operation)

    #
    # Public
    #
    def apply_trading_rule(self):
        self.__play_swing_trade()

    #
    # Override shared methods
    #
    def _create_position(self, index, direction):
        '''
        ルールに基づいてポジションをとる(Oanda通信有)
        '''
        candles = FXBase.get_candles()
        if direction is 'long':
            sign = ''
            stoploss = candles.low[index-1] - self._STOPLOSS_BUFFER_pips
        elif direction is 'short':
            sign = '-'
            stoploss = candles.high[index-1] + self._STOPLOSS_BUFFER_pips
        self._client.request_market_ordering(posi_nega_sign=sign, stoploss_price=stoploss)

    def _trail_stoploss(self, index, new_SL, time):
        '''
        ポジションのstoploss-priceを強気方向へ修正する
        Parameters
        ----------
        index : int
            不要
        new_SL : float
            新しいstoploss-price
        time : string
            不要

        Returns
        -------
        None
        '''
        result = self._client.request_trailing_stoploss(SL_price=new_SL)
        print(result)

    def _settle_position(self, index, price, time):
        '''
        ポジションをcloseする

        Parameters
        ----------
        index : int
        price : float
        time : string
            全て不要

        Returns
        -------
        None
        '''
        from pprint import pprint
        pprint(self._client.request_closing_position())

    #
    # Private
    #
    def __play_swing_trade(self):
        ''' 現在のレートにおいて、スイングトレードルールでトレード '''
        index = len(self._indicators) - 1 # INFO: 最終行
        close_price = FXBase.get_candles().close.values[-1]

        self._position = self.__load_position()
        if self._position['type'] == 'none':
            trend = self._check_trend(index=index, c_price=close_price)
            if trend is None: return

            direction = self._find_thrust(index, trend)
            if direction is None: return

            self._create_position(index, direction)
        else:
            self._judge_settle_position(index, close_price)

        return None

    def __load_position(self):
        pos = { 'type': 'none' }
        open_trades = self._client.request_open_trades()
        if open_trades == []: return pos

        # Open position の情報抽出
        target = open_trades[0]
        id = target['id']
        pos['price'] = float(target['price'])
        if target['currentUnits'][0] == '-':
            pos['type'] = 'short'
        else:
            pos['type'] = 'long'
        if 'stopLossOrder' not in target: return pos

        pos['stoploss'] = float(target['stopLossOrder']['price'])
        return pos
