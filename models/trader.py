from models.chart_watcher import FXBase
import models.analyzer as analyzer
import models.drawer   as drawer
import math
import pandas as pd

class Trader():
    def __init__(self):
        self.__ana    = analyzer.Analyzer()
        self.__drawer = drawer.FigureDrawer()
        self.__columns = ['price', 'stoploss', 'type']
        result = self.__ana.calc_indicators()

        if 'success' in result:
            print(result['success'])
            self.__indicators = self.__ana.get_indicators()
            self.__position = { 'type': 'none' }
            # TODO: 入値とstoploss値も持てるdataframeに変更する
            self.__hist_positions = {
                'long':  pd.DataFrame(columns=self.__columns),
                'short': pd.DataFrame(columns=self.__columns)
            }
            self.__x_points  = []
        else:
            print(result['error'])

    #
    # public
    #
    def auto_verify_trading_rule(self):
        result = self.__judge_swing_entry()
        if 'success' in result: print(result['success'])

    def draw_chart(self):
        drwr = self.__drawer
        drwr.draw_df_on_plt(df=self.__indicators.loc[:, ['20SMA']], plot_type=drwr.PLOT_TYPE['simple-line'], color='lightskyblue')
        drwr.draw_df_on_plt(df=self.__indicators.loc[:, ['10EMA']], plot_type=drwr.PLOT_TYPE['simple-line'], color='cyan')
        drwr.draw_df_on_plt(df=self.__indicators.loc[:, ['SAR']],   plot_type=drwr.PLOT_TYPE['dot'],         color='purple')
        # drwr.draw_df_on_plt(df=self.desc_trends, plot_type=drwr.PLOT_TYPE['dashed-line'], color='navy')
        # drwr.draw_df_on_plt(df=self.asc_trends,  plot_type=drwr.PLOT_TYPE['dashed-line'], color='navy')
        # drwr.draw_indexes_on_plt(index_array=self.jump_trendbreaks,   plot_type=drwr.PLOT_TYPE['break'], pos=drwr.POS_TYPE['over'])
        # drwr.draw_indexes_on_plt(index_array=self.fall_trendbreaks,   plot_type=drwr.PLOT_TYPE['break'], pos=drwr.POS_TYPE['beneath'])
        drwr.draw_candles()
        drwr.draw_positionDf_on_plt(df=self.__hist_positions['long'],  plot_type=drwr.PLOT_TYPE['long'])
        drwr.draw_positionDf_on_plt(df=self.__hist_positions['short'], plot_type=drwr.PLOT_TYPE['short'])
        drwr.draw_indexes_on_plt(index_array=self.__x_points,          plot_type=drwr.PLOT_TYPE['exit'])
        result = drwr.create_png()
        if 'success' in result: print(result['success'])
        return {
            'success': '[Trader] チャート分析、png生成完了',
            # メール送信フラグ: 今は必要ない
            'alart_necessary': False
        }

    #
    # private
    #
    def __judge_swing_entry(self, StopLoss_buffer_pips=0.05):
        ''' スイングトレードのentry pointを検出 '''
        high_candles  = FXBase.get_candles().high
        low_candles   = FXBase.get_candles().low
        close_candles = FXBase.get_candles().close
        sma           = self.__indicators['20SMA']
        ema           = self.__indicators['10EMA']
        parabolic     = self.__indicators['SAR']

        def check_trend(index, c_price):
            parabo = parabolic[index]
            if sma[index] < ema[index] and \
               ema[index] < c_price    and \
               parabo     < c_price:
                trend = 'bull'
            elif sma[index] > ema[index] and \
                 ema[index] > c_price    and \
                 parabo     > c_price:
                trend = 'bear'
            else:
                trend = None
            return trend

        def find_thrust(i, trend, c_price):
            if trend == 'bull' and c_price > high_candles[i-1]:
                direction = 'long'
            elif trend == 'bear' and c_price < low_candles[i-1]:
                direction = 'short'
            else:
                direction = None
            return direction

        def create_position(index, direction, c_price):
            if direction == 'long':
                stoploss = low_candles[index-1] - StopLoss_buffer_pips
            elif direction == 'short':
                stoploss = high_candles[index-1] + StopLoss_buffer_pips

            self.__position = {
                'price': c_price, 'stoploss': stoploss, 'type': direction
            }
            self.__hist_positions[direction].loc[index] = self.__position

        def settle_position(i, c_price):
            if self.__position['type'] == 'long':
                if low_candles[i-1] - StopLoss_buffer_pips > self.__position['stoploss']:
                    self.__position['stoploss'] = low_candles[i-1] - StopLoss_buffer_pips
                if self.__position['stoploss'] > low_candles[i] or parabolic[i] > c_price:
                    self.__position = { 'type': 'none' }
                    self.__x_points.append(i)
                    # TODO: ここでファイルにも書き込み
            elif self.__position['type'] == 'short':
                if high_candles[i-1] + StopLoss_buffer_pips < self.__position['stoploss']:
                    self.__position['stoploss'] = high_candles[i-1] + StopLoss_buffer_pips
                if self.__position['stoploss'] < high_candles[i] or parabolic[i] < c_price:
                    self.__position = { 'type': 'none' }
                    self.__x_points.append(i)
                    # TODO: ここでファイルにも書き込み

        for index, c_price in enumerate(close_candles):
            position_buf = self.__position.copy()
            if self.__position['type'] == 'none':
                if math.isnan(sma[index]): continue

                trend = check_trend(index, c_price)
                if trend is None: continue
                direction = find_thrust(index, trend, c_price)
                if direction is None: continue
                create_position(index, direction, c_price)
            else:
                settle_position(index, c_price)

            # # loop開始時と比較してpositionに変化があったら、状況をprintする
            # if not position_buf == self.__position:
            #     print('# recent position {pos}'.format(pos=self.__position))

        return { 'success': '[Trader] 売買判定終了' }
