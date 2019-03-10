import math
import pandas as pd
from scipy.stats          import linregress
from models.chart_watcher import FXBase

class Analyzer():
    # For Trendline
    MAX_EXTREMAL_CNT = 3

    # For Parabolic
    INITIAL_AF = 0.02
    MAX_AF     = 0.2

    def __init__(self):
        self.__SMA  = None
        self.__EMA  = None
        self.__SAR  = []

        # Trendline
        self.desc_trends      = None
        self.asc_trends       = None
        self.jump_trendbreaks = None
        self.fall_trendbreaks = None

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                       Driver                        #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    def calc_indicators(self):
        self.__calc_SMA()
        self.__calc_EMA()
        self.__calc_parabolic()
        result = self.__calc_trendlines()
        if 'success' in result:
            print(result['success'])
            self.__get_breakpoints()
            return { 'success': '[Analyzer] indicators算出完了' }
        else:
            return { 'error': '[Analyzer] indicators算出失敗' }

    def get_indicators(self):
        indicators = pd.concat(
            [self.__SMA, self.__EMA, self.__SAR],
            axis=1
        )
        return indicators

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
            local_extremum 又は extremal: 局所的極値のこと。
            極大値と極小値両方を指す（数学用語） '''
        sign = 'high' if bool_high else 'low'
        extremals = FXBase.get_candles()[start:end+1]
        while len(extremals) > Analyzer.MAX_EXTREMAL_CNT:
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
        if FXBase.get_candles() is None: return { 'error': '[Analyzer] データが存在しません' }
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
                # print(regression[0]*sign < 0.0, '傾き: ', regression[0], ', 切片: ', regression[1], )
                if regression[0]*sign < 0.0: # 傾き
                    trendline = regression[0] * FXBase.get_candles().time_id[i:i+span*2] + regression[1]
                    trendline.name = 'x_%s' % str(i)
                    trendlines[high_or_low].append(trendline)

        self.desc_trends = pd.concat(trendlines['high'], axis=1)
        self.asc_trends  = pd.concat(trendlines['low'],  axis=1)
        return { 'success': '[Analyzer] トレンドラインを生成しました' }

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
        self.__SAR          = [FXBase.get_candles().low[0]]

        for i, row in FXBase.get_candles().iterrows():
            current_high = FXBase.get_candles().high[i]
            current_low  = FXBase.get_candles().low[i]

            # レートがparabolicに触れたときの処理
            if self.__parabolic_is_touched(
                bull=bull,
                current_parabo=self.__SAR[-1],
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
                        acceleration_factor = min(
                            acceleration_factor + Analyzer.INITIAL_AF,
                            Analyzer.MAX_AF
                        )
                else:
                    if extreme_price > current_low:
                        extreme_price       = current_low
                        acceleration_factor = min(
                            acceleration_factor + Analyzer.INITIAL_AF,
                            Analyzer.MAX_AF
                        )
                parabolicSAR = self.__SAR[-1] + acceleration_factor * (extreme_price - self.__SAR[-1])

            if i == 0:
                self.__SAR[-1] = parabolicSAR
            else:
                self.__SAR.append(parabolicSAR)
        self.__SAR = pd.DataFrame(data=self.__SAR, columns=['SAR'])
