from models.oanda_py_client import FXBase, OandaPyClient
from models.analyzer import Analyzer
from models.drawer   import FigureDrawer
import math
import pandas as pd

class Trader():
    def __init__(self):
        self.__client  = OandaPyClient()
        self.__ana     = Analyzer()
        self.__drawer  = FigureDrawer()
        self.__columns = ['sequence', 'price', 'stoploss', 'type', 'time']
        # TODO: STOPLOSS_BUFFER_pips は要検討
        self.__STOPLOSS_BUFFER_pips = 0.05
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
    def auto_verify_trading_rule(self):
        ''' tradeルールを自動検証 '''
        print(self.__demo_swing_trade()['success'])
        print(self.__accurize_entry_prices()['success'])

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
        drwr.draw_positionDf_on_plt(df=df_pos['long'][df_pos['long'].type=='long'],   plot_type=drwr.PLOT_TYPE['long'])
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
    def __demo_swing_trade(self):
        ''' スイングトレードのentry pointを検出 '''
        sma = self.__indicators['20SMA']
        for index, c_price in enumerate(FXBase.get_candles().close):
            self.__position['sequence'] = index
            position_buf = self.__position.copy()
            if position_buf['type'] == 'none':
                if math.isnan(sma[index]): continue

                trend = self.__check_trend(index, c_price)
                if trend is None: continue
                direction = self.__find_thrust(index, trend)
                if direction is None: continue
                self.__create_position(index, direction)
            else:
                self.__judge_settle_position(index, c_price)

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
        candles = FXBase.get_candles()
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
        if direction == 'long':
            entry_price = FXBase.get_candles().high[index-1]
            stoploss    = FXBase.get_candles().low[index-1] - self.__STOPLOSS_BUFFER_pips
        elif direction == 'short':
            entry_price = FXBase.get_candles().low[index-1]
            stoploss    = FXBase.get_candles().high[index-1] + self.__STOPLOSS_BUFFER_pips

        self.__position = {
            'sequence': index, 'price': entry_price, 'stoploss': stoploss,
            'type': direction, 'time': FXBase.get_candles().time[index]
        }
        self.__hist_positions[direction].loc[index] = self.__position

    def __trail_stoploss(self, index, new_SL, position_type):
        self.__position['stoploss'] = new_SL
        position_after_trailing = self.__position.copy()
        position_after_trailing['type'] = 'trail'
        self.__hist_positions[position_type] =  pd.concat([
            self.__hist_positions[position_type],
            pd.DataFrame(position_after_trailing, index=[index])
        ])

    def __judge_settle_position(self, i, c_price):
        candles       = FXBase.get_candles()
        parabolic     = self.__indicators['SAR']
        position_type = self.__position['type']
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
            M10_candles = self.__client.request_latest_candles(
                target_datetime=row.time,
                granularity='M10',
                # TODO: granurarityがDの時しか正常動作しない
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
            M10_candles = self.__client.request_latest_candles(
                target_datetime=row.time,
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
