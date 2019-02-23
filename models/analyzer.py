import math
import pandas as pd
from scipy.stats          import linregress
from models.chart_watcher import FXBase
import models.drawer as drawer

class Analyzer():
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                  Moving Average                     #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    def __calc_SMA(self, window_size=20):
        ''' 単純移動平均線を生成 '''
        close      = FXBase.get_candles().close
        sma        = pd.Series.rolling(close, window=window_size).mean() #.dropna().reset_index(drop = True)
        self.__SMA = pd.DataFrame(sma).rename(columns={ 'close': '20SMA' })

    def __calc_EMA(self, window_size=10):
        ''' 指数平滑移動平均線を生成 '''
        # TODO: scipyを使うと早くなる
        # https://qiita.com/toyolab/items/6872b32d9fa1763345d8
        ema        = FXBase.get_candles().close.ewm(span=window_size).mean()
        self.__EMA = pd.DataFrame(ema).rename(columns={ 'close': '10EMA' })


    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                     TrendLine                       #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    def __get_local_extremum(self, start, end, bool_high):
        ''' 高値(high) / 安値(low)の始点 / 支点を取得
            チャートを単回帰分析し、結果直線よりも上（下）の値だけで再度単回帰分析...
            を繰り返し、2～3点に絞り込む
            local_extremum 又は extremal: 局所的極値のこと、極大値と極小値両方を指す（数学用語） '''
        sign = 'high' if bool_high else 'low'
        extremals = FXBase.get_candles()[start:end+1]
        while len(extremals) > 3:
            regression = linregress(x=extremals['time_id'], y=extremals[sign],)
            if bool_high:
                extremals = extremals.loc[
                    extremals[sign] > regression[0] * extremals['time_id'] + regression[1]
                ]
            else:
                extremals = extremals.loc[
                    extremals[sign] < regression[0] * extremals['time_id'] + regression[1]
                ]
        return extremals

    # iterate dataframe
    # https://stackoverflow.com/questions/7837722/what-is-the-most-efficient-way-to-loop-through-dataframes-with-pandas
    def __calc_trendlines(self, span=20, min_interval=3):
        if FXBase.get_candles() is None: return { 'error': 'データが存在しません' }
        FXBase.set_timeID()
        trendlines = { 'high': [], 'low': [] }

        # [下降・上昇]の２回ループ
        for bool_high in [True, False]:
            high_or_low = 'high' if bool_high else 'low'
            sign        = 1      if bool_high else -1

            # for i in array[start:end-1:step]:
            for i in FXBase.get_candles().index[::int(span/2)]:
                extremals = self.__get_local_extremum(i, i + span, bool_high=bool_high)
                if len(extremals) < 2:
                    continue
                # abs : 絶対値をとる
                # if abs(extremals.index[0] - extremals.index[1]) < min_interval:
                #     continue
                regression = linregress(
                    x = extremals['time_id'],
                    y = extremals[high_or_low],
                )
                print(regression[0]*sign < 0.0, '傾き: ', regression[0], ', 切片: ', regression[1], )
                if regression[0]*sign < 0.0: # 傾き
                    trendline = regression[0] * FXBase.get_candles().time_id[i:i+span*2] + regression[1]
                    trendline.name = 'x_%s' % str(i)
                    trendlines[high_or_low].append(trendline)

        self.desc_trends = pd.concat(trendlines['high'], axis=1)
        self.asc_trends  = pd.concat(trendlines['low'],  axis=1)
        return { 'success': 'トレンドラインを生成しました' }

    def __get_breakpoints(self):
        ''' トレンドブレイク箇所を配列で返す：今は下降トレンドのブレイクのみ '''
        close_candles = FXBase.get_candles().copy().close
        trendbreaks   = { 'jump': [], 'fall': [] }

        for bool_jump in [True, False]:
            if bool_jump:
                jump_or_fall = 'jump'
                trendlines   = self.desc_trends
            else:
                jump_or_fall = 'fall'
                trendlines   = self.asc_trends

            for col_name, trend_line in trendlines.iteritems():
                # x=i,i+1 が両方ともトレンドラインを突破したら breakpoint とする
                for i in range(0, len(close_candles)):
                    # i, i+1 がトレンドラインに存在しない場合にスキップ
                    if not(i in trend_line.index) or not(i+1 in trend_line.index):
                        continue
                    if math.isnan(trend_line[i]) or math.isnan(trend_line[i+1]):
                        continue
                    if bool_jump:
                        if trend_line[i]   < close_candles[i] and \
                           trend_line[i+1] < close_candles[i+1]:
                            trendbreaks[jump_or_fall].append(i+1)
                            break
                    else:
                        if trend_line[i]   > close_candles[i] and \
                           trend_line[i+1] > close_candles[i+1]:
                            trendbreaks[jump_or_fall].append(i+1)
                            break

        self.jump_trendbreaks = trendbreaks['jump']
        self.fall_trendbreaks = trendbreaks['fall']
        return trendbreaks

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                   Parabolic SAR                     #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    INITIAL_AF = 0.02
    MAX_AF     = 0.2

    def __parabolic_is_touched(self, bull, current_parabo, current_h, current_l):
        if bull:
            if current_parabo > current_l:
                return True
        else:
            if current_parabo < current_h:
                return True
        return False

    def __calc_parabolic(self):
        # 初期状態は上昇トレンドと仮定して計算
        bull                = True
        acceleration_factor = Analyzer.INITIAL_AF
        extreme_price       = FXBase.get_candles().high[0]
        self.__SARs         = [FXBase.get_candles().low[0]]

        for i, row in FXBase.get_candles().iterrows():
            current_high = FXBase.get_candles().high[i]
            current_low  = FXBase.get_candles().low[i]

            # レートがparabolicに触れたときの処理
            if self.__parabolic_is_touched(
                bull=bull,
                current_parabo=self.__SARs[-1],
                current_h=current_high, current_l=current_low
            ):
                parabolicSAR        = extreme_price
                acceleration_factor = Analyzer.INITIAL_AF
                if bull:
                    bull = False
                    extreme_price = current_low
                else:
                    bull = True
                    extreme_price = current_high

            else:
                if bull:
                    if extreme_price < current_high:
                        extreme_price       = current_high
                        acceleration_factor = min(acceleration_factor + Analyzer.INITIAL_AF, Analyzer.MAX_AF)
                else:
                    if extreme_price > current_low:
                        extreme_price       = current_low
                        acceleration_factor = min(acceleration_factor + Analyzer.INITIAL_AF, Analyzer.MAX_AF)
                parabolicSAR = self.__SARs[-1] + acceleration_factor * (extreme_price - self.__SARs[-1])

            if i == 0:
                self.__SARs[-1] = parabolicSAR
            else:
                self.__SARs.append(parabolicSAR)
        self.__SARs = pd.DataFrame(data=self.__SARs, columns=['SAR'])

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                    Entry judge                      #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    def __judge_swing_entry(self, StopLoss_buffer_pips=0.05):
        ''' スイングトレードのentry pointを検出 '''
        self.__position = { 'none': 0.0 }
        # TODO: 入値とstop値も持てるdataframeに変更する
        self.__e_points = { 'up': [], 'down': [] }
        self.__x_points = []

        high_candles  = FXBase.get_candles().high
        low_candles   = FXBase.get_candles().low
        close_candles = FXBase.get_candles().close
        sma           = self.__SMA['20SMA']
        ema           = self.__EMA['10EMA']

        def check_trend(index, c_price):
            parabo = self.__SARs['SAR'][i]
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
                if self.__position['stop'] > low_candles[i] or self.__SARs['SAR'][i] > c_price:
                    self.__position = { 'none': 0.0 }
                    self.__x_points.append(i)
                    # ここでファイルにも書き込み
                    print(i, ': settle position !')
            elif 'sell' in self.__position:
                if high_candles[i-1] + StopLoss_buffer_pips < self.__position['stop']:
                    self.__position['stop'] = high_candles[i-1] + StopLoss_buffer_pips
                if self.__position['stop'] < high_candles[i] or self.__SARs['SAR'][i] < c_price:
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

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                       Driver                        #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    def perform(self):
        self.__calc_SMA()
        self.__calc_EMA()
        self.__calc_parabolic()
        result = self.__calc_trendlines()
        if 'success' in result:
            self.__get_breakpoints()
            print(result['success'])
            self.__judge_swing_entry()
        return result

    def draw_chart(self):
        drwr = drawer.FigureDrawer()
        drwr.draw_df_on_plt(df=self.__SMA,       plot_type=drwr.PLOT_TYPE['simple-line'], color='lightskyblue')
        drwr.draw_df_on_plt(df=self.__EMA,       plot_type=drwr.PLOT_TYPE['simple-line'], color='cyan')
        drwr.draw_df_on_plt(df=self.__SARs,      plot_type=drwr.PLOT_TYPE['dot'],         color='purple')
        drwr.draw_df_on_plt(df=self.desc_trends, plot_type=drwr.PLOT_TYPE['dashed-line'], color='navy')
        drwr.draw_df_on_plt(df=self.asc_trends,  plot_type=drwr.PLOT_TYPE['dashed-line'], color='navy')
        drwr.draw_indexes_on_plt(index_array=self.__e_points['up'],   dot_type=drwr.DOT_TYPE['entry'])
        drwr.draw_indexes_on_plt(index_array=self.__e_points['down'], dot_type=drwr.DOT_TYPE['entry'])
        drwr.draw_indexes_on_plt(index_array=self.__x_points,         dot_type=drwr.DOT_TYPE['exit'])
        drwr.draw_indexes_on_plt(index_array=self.jump_trendbreaks,   dot_type=drwr.DOT_TYPE['break'], pos=drwr.POS_TYPE['over'])
        drwr.draw_indexes_on_plt(index_array=self.fall_trendbreaks,   dot_type=drwr.DOT_TYPE['break'], pos=drwr.POS_TYPE['beneath'])
        drwr.draw_candles()
        result = drwr.create_png()

        num = len(FXBase.get_candles())
        if self.jump_trendbreaks[-1] == num or self.fall_trendbreaks[-1] == num:
            alart_necessary = True
        else:
            alart_necessary = False

        return {
            'success': {
                'msg': 'チャート分析、png生成完了',
                'alart_necessary': alart_necessary
            }
        }
