from models.chart_watcher import FXBase
import models.analyzer as analyzer
import models.drawer   as drawer
import math
import pandas as pd

class Trader():
    def __init__(self):
        self.__ana    = analyzer.Analyzer()
        self.__drawer = drawer.FigureDrawer()
        result = self.__ana.calc_indicators()

        if 'success' in result:
            self.__indicators = self.__ana.get_indicators()
            self.__position = { 'none': 0.0 }
            # TODO: 入値とstop値も持てるdataframeに変更する
            self.__e_points = { 'up': [], 'down': [] }
            self.__x_points = []

    #
    # public
    #
    def auto_verify_trading_rule(self):
        self.__judge_swing_entry()
        return self.__indicators

    def draw_chart(self):
        drwr = self.__drawer
        drwr.draw_df_on_plt(df=self.__indicators.loc[:, ['20SMA']], plot_type=drwr.PLOT_TYPE['simple-line'], color='lightskyblue')
        drwr.draw_df_on_plt(df=self.__indicators.loc[:, ['10EMA']], plot_type=drwr.PLOT_TYPE['simple-line'], color='cyan')
        drwr.draw_df_on_plt(df=self.__indicators.loc[:, ['SAR']],   plot_type=drwr.PLOT_TYPE['dot'],         color='purple')
        # drwr.draw_df_on_plt(df=self.desc_trends, plot_type=drwr.PLOT_TYPE['dashed-line'], color='navy')
        # drwr.draw_df_on_plt(df=self.asc_trends,  plot_type=drwr.PLOT_TYPE['dashed-line'], color='navy')
        drwr.draw_indexes_on_plt(index_array=self.__e_points['up'],   dot_type=drwr.DOT_TYPE['long'])
        drwr.draw_indexes_on_plt(index_array=self.__e_points['down'], dot_type=drwr.DOT_TYPE['short'])
        drwr.draw_indexes_on_plt(index_array=self.__x_points,         dot_type=drwr.DOT_TYPE['exit'])
        # drwr.draw_indexes_on_plt(index_array=self.jump_trendbreaks,   dot_type=drwr.DOT_TYPE['break'], pos=drwr.POS_TYPE['over'])
        # drwr.draw_indexes_on_plt(index_array=self.fall_trendbreaks,   dot_type=drwr.DOT_TYPE['break'], pos=drwr.POS_TYPE['beneath'])
        drwr.draw_candles()
        result = drwr.create_png()
        return {
            'success': {
                'msg': 'チャート分析、png生成完了',
                # メール送信フラグ: 今は必要ない
                'alart_necessary': False
            }
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
            parabo = parabolic[i]
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

        def find_thrust(index, trend, c_price):
            if trend == 'bull' and c_price > high_candles[i-1]:
                result = 'buy'
            elif trend == 'bear' and c_price < low_candles[i-1]:
                result = 'sell'
            else:
                result = None
            return result

        def create_position(index, result, c_price):
            print(index, ': take position !')
            if result == 'buy':
                self.__position = { 'buy': c_price, 'stop': low_candles[index-1] - StopLoss_buffer_pips }
                self.__e_points['up'].append(index)
            else:
                self.__position = { 'sell': c_price, 'stop': high_candles[index-1] + StopLoss_buffer_pips }
                self.__e_points['down'].append(index)

        def settle_position(i, c_price):
            if 'buy' in self.__position:
                if low_candles[i-1] - StopLoss_buffer_pips > self.__position['stop']:
                    self.__position['stop'] = low_candles[i-1] - StopLoss_buffer_pips
                if self.__position['stop'] > low_candles[i] or parabolic[i] > c_price:
                    self.__position = { 'none': 0.0 }
                    self.__x_points.append(i)
                    # ここでファイルにも書き込み
                    print(i, ': settle position !')
            elif 'sell' in self.__position:
                if high_candles[i-1] + StopLoss_buffer_pips < self.__position['stop']:
                    self.__position['stop'] = high_candles[i-1] + StopLoss_buffer_pips
                if self.__position['stop'] < high_candles[i] or parabolic[i] < c_price:
                    self.__position = { 'none': 0.0 }
                    self.__x_points.append(i)
                    # ここでファイルにも書き込み
                    print(i, ': settle position !')

        for i, c_price in enumerate(close_candles):
            position_buf = self.__position.copy()
            if 'none' in self.__position:
                if math.isnan(sma[i]): continue

                trend = check_trend(i, c_price)
                if trend == None: continue
                result = find_thrust(i, trend, c_price)
                if result == None: continue
                create_position(i, result, c_price)
            else:
                settle_position(i, c_price)

            if not position_buf == self.__position:
                print('# recent position {pos}'.format(pos=self.__position))
