from models.oanda_py_client import FXBase, OandaPyClient
from models.analyzer import Analyzer
from models.drawer import FigureDrawer
import math
import numpy as np
import pandas as pd

class Trader():
    def __init__(self, operation='verification'):
        if operation == 'custom':
            self.__instrument = self.__select_instrument()
        else:
            self.__instrument = 'USD_JPY'

        self._client  = OandaPyClient(instrument=self.__instrument)
        self.__ana    = Analyzer()
        self.__drawer = FigureDrawer()
        self.__columns = ['sequence', 'price', 'stoploss', 'type', 'time']
        # TODO: STOPLOSS_BUFFER_pips は要検討
        self.__STOPLOSS_BUFFER_pips = 0.05

        if operation == 'custom':
            self.__request_custom_candles()

        result = self.__ana.calc_indicators()
        if 'error' in result:
            print(result['error'])
            return

        print(result['success'])
        self.__indicators = self.__ana.get_indicators()
        self.__position = { 'type': 'none' }
        self.__hist_positions = {
            'long':  pd.DataFrame(columns=self.__columns),
            'short': pd.DataFrame(columns=self.__columns)
        }

    #
    # public
    #
    def auto_verify_trading_rule(self, accurize=False):
        ''' tradeルールを自動検証 '''
        print(self.__demo_swing_trade()['success'])
        if accurize: print(self.__accurize_entry_prices()['success'])

    def verify_varios_stoploss(self, accurize=False):
        ''' StopLossの設定値を自動でスライドさせて損益を検証 '''
        verification_dataframes_array = []

        stoploss_buffer_list = np.append(
            np.round(np.arange(0.01, 0.10, 0.02), decimals=2), [0.50]
        )
        for sl in stoploss_buffer_list:
            print('[Trader] stoploss buffer: {}pipsで検証開始...'.format(sl))
            self.__STOPLOSS_BUFFER_pips = sl
            self.auto_verify_trading_rule(accurize=True)

            _df = pd.concat(
                [ self.__hist_positions['long'],
                  self.__hist_positions['short'] ],
                axis=1, keys=['long', 'short'],
                names=['type', '-']
            )
            verification_dataframes_array.append(_df)

        result = pd.concat(
            verification_dataframes_array,
            axis=1, keys=stoploss_buffer_list,
            names=['SL_buffer']
        )
        result.to_csv('./sl_verify_{inst}.csv'.format(inst=self.__instrument))

    def draw_chart(self):
        ''' チャートや指標をpngに描画 '''
        drwr = self.__drawer
        drwr.draw_df_on_plt(df=self.__indicators.loc[:, ['20SMA']],    plot_type=drwr.PLOT_TYPE['simple-line'], color='lightskyblue')
        drwr.draw_df_on_plt(df=self.__indicators.loc[:, ['10EMA']],    plot_type=drwr.PLOT_TYPE['simple-line'], color='cyan')
        drwr.draw_df_on_plt(df=self.__indicators.loc[:, ['band_+2σ']], plot_type=drwr.PLOT_TYPE['simple-line'], color='blue')
        drwr.draw_df_on_plt(df=self.__indicators.loc[:, ['band_-2σ']], plot_type=drwr.PLOT_TYPE['simple-line'], color='blue')
        drwr.draw_df_on_plt(df=self.__indicators.loc[:, ['SAR']],      plot_type=drwr.PLOT_TYPE['dot'],         color='purple')
        # drwr.draw_df_on_plt(df=self.desc_trends, plot_type=drwr.PLOT_TYPE['dashed-line'], color='navy')
        # drwr.draw_df_on_plt(df=self.asc_trends,  plot_type=drwr.PLOT_TYPE['dashed-line'], color='navy')
        # drwr.draw_indexes_on_plt(index_array=self.jump_trendbreaks,   plot_type=drwr.PLOT_TYPE['break'], pos=drwr.POS_TYPE['over'])
        # drwr.draw_indexes_on_plt(index_array=self.fall_trendbreaks,   plot_type=drwr.PLOT_TYPE['break'], pos=drwr.POS_TYPE['beneath'])
        drwr.draw_candles()
        df_pos = self.__hist_positions
        drwr.draw_positionDf_on_plt(df=df_pos['long'][df_pos['long'].type=='long'],    plot_type=drwr.PLOT_TYPE['long'])
        drwr.draw_positionDf_on_plt(df=df_pos['long'][df_pos['long'].type=='close'],   plot_type=drwr.PLOT_TYPE['exit'])
        drwr.draw_positionDf_on_plt(df=df_pos['short'][df_pos['short'].type=='short'], plot_type=drwr.PLOT_TYPE['short'])
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
        self.__hist_positions['long'].to_csv('./long_history.csv')
        self.__hist_positions['short'].to_csv('./short_history.csv')
        print('[Trader] ポジション履歴をcsv出力完了')

    #
    # private
    #
    def __select_instrument(self):
        print('通貨ペアは？')
        instruments = ['USD_JPY', 'EUR_USD', 'GBP_JPY']
        prompt_message = ''
        for i, inst in enumerate(instruments):
            prompt_message += '[{i}]:{inst} '.format(i=i, inst=inst)
        print(prompt_message + '(半角数字): ', end='')
        inst_id = int(input())
        return instruments[inst_id]

    def __request_custom_candles(self):
        # Custom request
        print('何日分のデータを取得する？(半角数字): ', end='')
        days = int(input())
        if days > 300:
            print('[ALERT] 現在は300日までに制限しています')
            exit()

        print('取得スパンは？(ex: M5): ', end='')
        granularity = str(input())

        result = self._client.load_long_chart(
            days=days,
            granularity=granularity
        )
        if 'error' in result:
            print(result['error'])
            exit()
        FXBase.set_candles(result['candles'])

    def __demo_swing_trade(self):
        ''' スイングトレードのentry pointを検出 '''
        sma = self.__indicators['20SMA']
        # INFO: 繰り返しデモする場合に、前回のpositionが残っているので消す
        self.__position = { 'type': 'none' }
        for index, close_price in enumerate(FXBase.get_candles().close):
            self.__position['sequence'] = index
            position_buf = self.__position.copy()
            if position_buf['type'] == 'none':
                if math.isnan(sma[index]): continue

                trend = self.__check_trend(index, close_price)
                if trend is None: continue

                direction = self.__find_thrust(index, trend)
                if direction is None: continue

                self.__create_position(index, direction)
            else:
                self.__judge_settle_position(index, close_price)

            # # loop開始時と比較してpositionに変化があったら、状況をprintする
            # if not position_buf == self.__position:
            #     print('# recent position {pos}'.format(pos=self.__position))

        self.__hist_positions['long']  = self.__hist_positions['long'].reset_index(drop=True)
        self.__hist_positions['short'] = self.__hist_positions['short'].reset_index(drop=True)
        return { 'success': '[Trader] 売買判定終了' }

    def __check_trend(self, index, c_price):
        '''
        ルールに基づいてトレンドの有無を判定
        '''
        sma    = self.__indicators['20SMA'][index]
        ema    = self.__indicators['10EMA'][index]
        parabo = self.__indicators['SAR'][index]
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
        return trend

    def __find_thrust(self, i, trend):
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
        return direction

    def __create_position(self, index, direction):
        '''
        ルールに基づいてポジションをとる
        '''
        candles = FXBase.get_candles()
        if direction == 'long':
            entry_price = candles.high[index-1]
            stoploss    = candles.low[index-1] - self.__STOPLOSS_BUFFER_pips
        elif direction == 'short':
            entry_price = candles.low[index-1]
            stoploss    = candles.high[index-1] + self.__STOPLOSS_BUFFER_pips

        self.__position = {
            'sequence': index, 'price': entry_price, 'stoploss': stoploss,
            'type': direction, 'time': candles.time[index]
        }
        self.__hist_positions[direction].loc[index] = self.__position

    def __trail_stoploss(self, index, new_SL, position_type):
        self.__position['stoploss'] = new_SL
        position_after_trailing = self.__position.copy()
        position_after_trailing['type'] = 'trail'
        position_after_trailing['time'] = FXBase.get_candles().time[index]
        self.__hist_positions[position_type] =  pd.concat([
            self.__hist_positions[position_type],
            pd.DataFrame(position_after_trailing, index=[index])
        ])

    def __judge_settle_position(self, i, c_price):
        candles        = FXBase.get_candles()
        parabolic      = self.__indicators['SAR']
        position_type  = self.__position['type']
        stoploss_price = self.__position['stoploss']
        if position_type == 'long':
            if candles.low[i-1] - self.__STOPLOSS_BUFFER_pips > stoploss_price:
                stoploss_price = candles.low[i-1] - self.__STOPLOSS_BUFFER_pips
                self.__trail_stoploss(index=i, new_SL=stoploss_price, position_type=position_type)
            if stoploss_price > candles.low[i]:
                self.__settle_position(
                    index=i, price=stoploss_price,
                    position_type=position_type, time=candles.time[i]
                )
            elif parabolic[i] > c_price:
                self.__settle_position(
                    index=i, price=c_price,
                    position_type=position_type, time=candles.time[i]
                )
        elif position_type == 'short':
            if candles.high[i-1] + self.__STOPLOSS_BUFFER_pips < stoploss_price:
                stoploss_price = candles.high[i-1] + self.__STOPLOSS_BUFFER_pips
                self.__trail_stoploss(index=i, new_SL=stoploss_price, position_type=position_type)
            if stoploss_price < candles.high[i]:
                self.__settle_position(
                    index=i, price=stoploss_price,
                    position_type=position_type, time=candles.time[i]
                )
            elif parabolic[i] < c_price:
                self.__settle_position(
                    index=i, price=c_price,
                    position_type=position_type, time=candles.time[i]
                )

    def __settle_position(self, index, price, position_type, time):
        '''
        ポジション解消の履歴を残す

        Parameters
        ----------
        index : int
            ポジションを解消するタイミングを表す
        price : float
            ポジション解消時の価格
        position_type : string
            -
        time : string
            ポジションを解消する日（時）

        Returns
        -------
        None
        '''
        self.__position = { 'type': 'none' }
        self.__hist_positions[position_type] =  pd.concat([
            self.__hist_positions[position_type],
            pd.DataFrame([[index, price, 0.0, 'close', time]], columns=self.__columns)
        ])

    def __accurize_entry_prices(self):
        '''
        ポジション履歴のエントリーpriceを、実際にエントリー可能な価格に修正する
        '''
        # TODO: 総リクエスト数と所要時間、rpsをこまめに表示した方がよさそう
        # long価格の修正
        long_hist = self.__hist_positions['long']
        long_pos  = long_hist[long_hist['type']=='long']
        for index, row in long_pos.iterrows():
            M10_candles = self._client.request_latest_candles(
                target_datetime=row.time,
                instrument=self.__instrument,
                granularity='M10',
                # TODO: granularityがDの時しか正常動作しない
                period_m=1440
            )
            for i, M10_row in M10_candles.iterrows():
                if row.price < M10_row.high:
                    self.__hist_positions['long'].loc[index, 'price'] = M10_row.high
                    self.__hist_positions['long'].loc[index, 'time'] = M10_row.time
                    break

        # short価格の修正
        short_hist = self.__hist_positions['short']
        short_pos  = short_hist[short_hist['type']=='short']
        for index, row in short_pos.iterrows():
            M10_candles = self._client.request_latest_candles(
                target_datetime=row.time,
                instrument=self.__instrument,
                granularity='M10',
                period_m=1440
            )
            for i, M10_row in M10_candles.iterrows():
                if row.price > M10_row.low:
                    self.__hist_positions['short'].loc[index, 'price'] = M10_row.low
                    self.__hist_positions['short'].loc[index, 'time'] = M10_row.time
                    break
        return { 'success': '[Trader] entry価格を、現実的に取引可能な値に修正' }

    def __calc_profit(self):
        '''
        ポジション履歴から総損益を算出する
        '''
        # longエントリーの損益を計算
        self.__hist_positions['long']['profit'] = pd.Series([], index=[])

        long_hist = self.__hist_positions['long']
        for i, row in long_hist[long_hist.type=='close'].iterrows():
            profit = row.price - long_hist.price[i-1]
            self.__hist_positions['long'].loc[i, ['profit']] = profit

        # shortエントリーの損益を計算
        self.__hist_positions['short']['profit'] = pd.Series([], index=[])

        short_hist = self.__hist_positions['short']
        for i, row in short_hist[short_hist.type=='close'].iterrows():
            profit = short_hist.price[i-1] - row.price
            self.__hist_positions['short'].loc[i, ['profit']] = profit

        sum_profit = self.__hist_positions['long'][['profit']].sum() \
                   + self.__hist_positions['short'][['profit']].sum()
        print('[合計損益] {profit}pips'.format( profit=round(sum_profit['profit'] * 100, 3) ))


class RealTrader(Trader):
    #
    # Public
    #
    def apply_trading_rule(self):
        print(self.__load_position())

    #
    # Private
    #
    def __play_swing_trade(self):
        ''' 現在のレートにおいて、スイングトレードルールでトレード '''
        sma = self.__indicators['20SMA']
        index = FXBase.get_candles().tail(1).index
        close_price = FXBase.get_candles().tail(1).close

        self.__position['sequence'] = index

        # position_buf = self.__position.copy()
        if position_buf['type'] == 'none':
            if math.isnan(sma[index]): return

            trend = self.__check_trend(index, close_price)
            if trend is None: return

            direction = self.__find_thrust(index, trend)
            if direction is None: return

            self.__create_position(index, direction)
        else:
            self.__judge_settle_position(index, close_price)

    def __load_position(self):
        pos = { 'type': 'none' }
        open_trades = self._client.request_open_trades(instrument='EUR_USD')
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
