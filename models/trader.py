from models.chart_watcher import FXBase
import models.analyzer as analyzer
import models.drawer   as drawer
import math
import pandas as pd

class Trader():
    def __init__(self):
        self.__ana    = analyzer.Analyzer()
        self.__drawer = drawer.FigureDrawer()
        self.__columns = ['sequence', 'price', 'stoploss', 'type']
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
        result = self.__demo_swing_trade()
        if 'success' in result: print(result['success'])

    def draw_chart(self):
        ''' チャートや指標をpngに描画 '''
        drwr = self.__drawer
        drwr.draw_df_on_plt(df=self.__indicators.loc[:, ['20SMA']], plot_type=drwr.PLOT_TYPE['simple-line'], color='lightskyblue')
        drwr.draw_df_on_plt(df=self.__indicators.loc[:, ['10EMA']], plot_type=drwr.PLOT_TYPE['simple-line'], color='cyan')
        drwr.draw_df_on_plt(df=self.__indicators.loc[:, ['SAR']],   plot_type=drwr.PLOT_TYPE['dot'],         color='purple')
        # drwr.draw_df_on_plt(df=self.desc_trends, plot_type=drwr.PLOT_TYPE['dashed-line'], color='navy')
        # drwr.draw_df_on_plt(df=self.asc_trends,  plot_type=drwr.PLOT_TYPE['dashed-line'], color='navy')
        # drwr.draw_indexes_on_plt(index_array=self.jump_trendbreaks,   plot_type=drwr.PLOT_TYPE['break'], pos=drwr.POS_TYPE['over'])
        # drwr.draw_indexes_on_plt(index_array=self.fall_trendbreaks,   plot_type=drwr.PLOT_TYPE['break'], pos=drwr.POS_TYPE['beneath'])
        drwr.draw_candles()
        df_pos = self.__hist_positions
        drwr.draw_positionDf_on_plt(df=df_pos['long'][df_pos['long'].type!='close'],   plot_type=drwr.PLOT_TYPE['long'])
        drwr.draw_positionDf_on_plt(df=df_pos['long'][df_pos['long'].type=='close'],   plot_type=drwr.PLOT_TYPE['exit'])
        drwr.draw_positionDf_on_plt(df=df_pos['short'][df_pos['short'].type!='close'], plot_type=drwr.PLOT_TYPE['short'])
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
        self.__hist_positions['long'].to_csv('./long_history.csv')
        self.__hist_positions['short'].to_csv('./short_history.csv')
        print('[Trader] ポジション履歴をcsv出力完了')

    #
    # private
    #
    def __demo_swing_trade(self, STOPLOSS_BUFFER_pips=0.5):
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
                stoploss = low_candles[index-1] - STOPLOSS_BUFFER_pips
            elif direction == 'short':
                stoploss = high_candles[index-1] + STOPLOSS_BUFFER_pips

            self.__position = {
                'sequence': index, 'price': c_price, 'stoploss': stoploss, 'type': direction
            }
            self.__hist_positions[direction].loc[index] = self.__position

        def judge_settle_position(i, c_price):
            position_type = self.__position['type']
            stoploss_price = self.__position['stoploss']
            if position_type == 'long':
                if low_candles[i-1] - STOPLOSS_BUFFER_pips > stoploss_price:
                    stoploss_price = low_candles[i-1] - STOPLOSS_BUFFER_pips
                    self.__trail_stoploss(index=i, new_SL=stoploss_price, position_type=position_type)
                if stoploss_price > low_candles[i]:
                    self.__settle_position(
                        index=i, price=stoploss_price, position_type=position_type
                    )
                elif parabolic[i] > c_price:
                    self.__settle_position(
                        index=i, price=c_price, position_type=position_type
                    )
            elif position_type == 'short':
                if high_candles[i-1] + STOPLOSS_BUFFER_pips < stoploss_price:
                    stoploss_price = high_candles[i-1] + STOPLOSS_BUFFER_pips
                    self.__trail_stoploss(index=i, new_SL=stoploss_price, position_type=position_type)
                if stoploss_price < high_candles[i]:
                    self.__settle_position(
                        index=i, price=stoploss_price, position_type=position_type
                    )
                elif parabolic[i] < c_price:
                    self.__settle_position(
                        index=i, price=c_price, position_type=position_type
                    )

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
                judge_settle_position(index, c_price)

            # # loop開始時と比較してpositionに変化があったら、状況をprintする
            # if not position_buf == self.__position:
            #     print('# recent position {pos}'.format(pos=self.__position))

        self.__hist_positions['long']  = self.__hist_positions['long'].reset_index(drop=True)
        self.__hist_positions['short'] = self.__hist_positions['short'].reset_index(drop=True)
        return { 'success': '[Trader] 売買判定終了' }

    def __trail_stoploss(self, index, new_SL, position_type):
        self.__position['stoploss'] = new_SL
        self.__hist_positions[position_type] =  pd.concat([
            self.__hist_positions[position_type],
            pd.DataFrame(self.__position, index=[index])
        ])

    def __settle_position(self, index, price, position_type):
        self.__position = { 'type': 'none' }
        self.__hist_positions[position_type] =  pd.concat([
            self.__hist_positions[position_type],
            pd.DataFrame([[index, price, 0.0, 'close']], columns=self.__columns)
        ])
