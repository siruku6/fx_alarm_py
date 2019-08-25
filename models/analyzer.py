import math
import pandas as pd
# from scipy.stats import linregress
from models.oanda_py_client import FXBase


class Analyzer():
    # For Trendline
    MAX_EXTREMAL_CNT = 3

    # For Parabolic
    INITIAL_AF = 0.02
    MAX_AF = 0.2

    def __init__(self):
        self.__indicators = {
            'SMA': None,
            'EMA': None,
            'SIGMA*2_BAND': None,
            'SIGMA*-2_BAND': None,
            'SIGMA*3_BAND': None,
            'SIGMA*-3_BAND': None,
            'SAR': None,
            'stoD': None,
            'stoSD': None
        }

        # Trendline
        self.desc_trends = None
        self.asc_trends = None
        self.jump_trendbreaks = None
        self.fall_trendbreaks = None

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                       Driver                        #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    def calc_indicators(self):
        if FXBase.get_candles() is None:
            return {'error': '[ERROR] Analyzer: 分析対象データがありません'}
        self.__calc_SMA()
        self.__calc_EMA()
        self.__calc_bollinger_bands()
        self.__calc_parabolic()
        self.__indicators['stoD'] = self.__calc_STOD(window_size=5)
        self.__indicators['stoSD'] = self.__calc_STOSD(window_size=5)
        # result = self.__calc_trendlines()
        # if 'success' in result:
        #     print(result['success'])
        #     self.__get_breakpoints()
        #     return { 'success': '[Analyzer] indicators算出完了' }
        # else:
        #     return { 'error': '[Analyzer] indicators算出失敗' }
        return {'success': '[Analyzer] indicators算出完了'}

    def get_indicators(self):
        indicators = pd.concat(
            [
                self.__indicators['SMA'],
                self.__indicators['50SMA'],
                self.__indicators['EMA'],
                self.__indicators['SIGMA*2_BAND'],
                self.__indicators['SIGMA*-2_BAND'],
                self.__indicators['SIGMA*3_BAND'],
                self.__indicators['SIGMA*-3_BAND'],
                self.__indicators['SAR'],
                self.__indicators['stoD'],
                self.__indicators['stoSD']
            ],
            axis=1
        )
        return indicators

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                  Moving Average                     #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    def __calc_SMA(self, window_size=20):
        ''' 単純移動平均線を生成 '''
        close = FXBase.get_candles().close
        # mean()後の .dropna().reset_index(drop = True) を消去中
        sma = pd.Series.rolling(close, window=window_size).mean()
        self.__indicators['SMA'] = pd.DataFrame(sma).rename(columns={'close': '20SMA'})
        sma50 = pd.Series.rolling(close, window=50).mean()
        self.__indicators['50SMA'] = pd.DataFrame(sma50).rename(columns={'close': '50SMA'})       

    def __calc_EMA(self, window_size=10):
        ''' 指数平滑移動平均線を生成 '''
        # TODO: scipyを使うと早くなる
        # https://qiita.com/toyolab/items/6872b32d9fa1763345d8
        ema = FXBase.get_candles().close.ewm(span=window_size).mean()
        self.__indicators['EMA'] = pd.DataFrame(ema).rename(columns={'close': '10EMA'})

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                  Bollinger Bands                    #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    def __calc_bollinger_bands(self, window_size=20):
        '''ボリンジャーバンドを生成'''
        close = FXBase.get_candles().close
        mean = pd.Series.rolling(close, window=window_size).mean()
        standard_deviation = pd.Series.rolling(close, window=window_size).std()

        self.__indicators['SIGMA*2_BAND'] = \
            pd.DataFrame(mean + standard_deviation * 2) \
              .rename(columns={'close': 'band_+2σ'})
        self.__indicators['SIGMA*-2_BAND'] = \
            pd.DataFrame(mean - standard_deviation * 2) \
              .rename(columns={'close': 'band_-2σ'})
        self.__indicators['SIGMA*3_BAND'] = \
            pd.DataFrame(mean + standard_deviation * 3) \
              .rename(columns={'close': 'band_+3σ'})
        self.__indicators['SIGMA*-3_BAND'] = \
            pd.DataFrame(mean - standard_deviation * 3) \
              .rename(columns={'close': 'band_-3σ'})

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                     TrendLine                       #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # # iterate dataframe
    # # https://stackoverflow.com/questions/7837722/what-is-the-most-efficient-way-to-loop-through-dataframes-with-pandas
    # def __calc_trendlines(self, span=20, min_interval=3):
    #     if FXBase.get_candles() is None:
    #         return {'error': '[Analyzer] データが存在しません'}
    #     FXBase.set_timeID()
    #     trendlines = {'high': [], 'low': []}

    #     # [下降・上昇]の２回ループ
    #     for bool_high in [True, False]:
    #         high_or_low = 'high' if bool_high else 'low'
    #         sign = 1 if bool_high else -1

    #         # for i in array[start:end-1:step]:
    #         for i in FXBase.get_candles().index[::int(span / 2)]:
    #             extremals = self.__get_local_extremum(i, i + span, bool_high=bool_high)
    #             if len(extremals) < 2:
    #                 continue
    #             # abs : 絶対値をとる
    #             # if abs(extremals.index[0] - extremals.index[1]) < min_interval:
    #             #     continue
    #             regression = linregress(
    #                 x=extremals['time_id'],
    #                 y=extremals[high_or_low],
    #             )
    #             # print(regression[0]*sign < 0.0, '傾き: ', regression[0], ', 切片: ', regression[1], )
    #             if regression[0] * sign < 0.0: # 傾き
    #                 trendline = regression[0] * FXBase.get_candles().time_id[i:i + span * 2] + regression[1]
    #                 trendline.name = 'x_%s' % str(i)
    #                 trendlines[high_or_low].append(trendline)

    #     self.desc_trends = pd.concat(trendlines['high'], axis=1)
    #     self.asc_trends = pd.concat(trendlines['low'], axis=1)
    #     return {'success': '[Analyzer] トレンドラインを生成しました'}

    # def __get_local_extremum(self, start, end, bool_high):
    #     ''' 高値(high) / 安値(low)の始点 / 支点を取得
    #         チャートを単回帰分析し、結果直線よりも上（下）の値だけで再度単回帰分析...
    #         を繰り返し、2～3点に絞り込む
    #         local_extremum 又は extremal: 局所的極値のこと。
    #         極大値と極小値両方を指す（数学用語） '''
    #     sign = 'high' if bool_high else 'low'
    #     extremals = FXBase.get_candles(start, end + 1)
    #     while len(extremals) > Analyzer.MAX_EXTREMAL_CNT:
    #         regression = linregress(x=extremals['time_id'], y=extremals[sign],)
    #         if bool_high:
    #             extremals = extremals.loc[
    #                 extremals[sign] > regression[0] * extremals['time_id'] + regression[1]
    #             ]
    #         else:
    #             extremals = extremals.loc[
    #                 extremals[sign] < regression[0] * extremals['time_id'] + regression[1]
    #             ]
    #     return extremals

    # def __get_breakpoints(self):
    #     ''' トレンドブレイク箇所を配列で返す：今は下降トレンドのブレイクのみ '''
    #     close_candles = FXBase.get_candles().copy().close
    #     trendbreaks = {'jump': [], 'fall': []}

    #     for bool_jump in [True, False]:
    #         if bool_jump:
    #             jump_or_fall = 'jump'
    #             trendlines = self.desc_trends
    #         else:
    #             jump_or_fall = 'fall'
    #             trendlines = self.asc_trends

    #         for _col_name, trend_line in trendlines.iteritems():
    #             # x=i,i+1 が両方ともトレンドラインを突破したら breakpoint とする
    #             for i in range(0, len(close_candles)):
    #                 # i, i+1 がトレンドラインに存在しない場合にスキップ
    #                 if not(i in trend_line.index) or not(i + 1 in trend_line.index):
    #                     continue
    #                 if math.isnan(trend_line[i]) or math.isnan(trend_line[i + 1]):
    #                     continue
    #                 if bool_jump:
    #                     if trend_line[i] < close_candles[i] and \
    #                        trend_line[i + 1] < close_candles[i + 1]:
    #                         trendbreaks[jump_or_fall].append(i + 1)
    #                         break
    #                 else:
    #                     if trend_line[i] > close_candles[i] and \
    #                        trend_line[i + 1] > close_candles[i + 1]:
    #                         trendbreaks[jump_or_fall].append(i + 1)
    #                         break

    #     self.jump_trendbreaks = trendbreaks['jump']
    #     self.fall_trendbreaks = trendbreaks['fall']
    #     return trendbreaks

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
        bull = True
        acceleration_factor = Analyzer.INITIAL_AF
        extreme_price = FXBase.get_candles().high[0]
        temp_sar_array = [FXBase.get_candles().low[0]]

        for i, row in FXBase.get_candles().iterrows():
            current_high = row.high
            current_low = row.low
            last_sar = temp_sar_array[-1]

            # レートがparabolicに触れたときの処理
            if self.__parabolic_is_touched(
                bull=bull,
                current_parabo=last_sar,
                current_h=current_high, current_l=current_low
            ):
                temp_sar = extreme_price
                acceleration_factor = Analyzer.INITIAL_AF
                if bull:
                    bull = False
                    extreme_price = current_low
                else:
                    bull = True
                    extreme_price = current_high
            else:
                if bull and extreme_price < current_high:
                    extreme_price = current_high
                    acceleration_factor = min(
                        acceleration_factor + Analyzer.INITIAL_AF,
                        Analyzer.MAX_AF
                    )
                elif not bull and extreme_price > current_low:
                    extreme_price = current_low
                    acceleration_factor = min(
                        acceleration_factor + Analyzer.INITIAL_AF,
                        Analyzer.MAX_AF
                    )
                temp_sar = last_sar + acceleration_factor * (extreme_price - last_sar)

            if i == 0:
                temp_sar_array[-1] = temp_sar
            else:
                temp_sar_array.append(temp_sar)
        self.__indicators['SAR'] = pd.DataFrame(data=temp_sar_array, columns=['SAR'])

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                    Stochastic                       #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # http://www.algo-fx-blog.com/stochastics-python/
    def __calc_STOK(self, window_size=5):
        ''' ストキャスの%Kを計算 '''
        candles = FXBase.get_candles()
        stoK = ((candles.close - candles.low.rolling(window=window_size, center=False).min()) / (
            candles.high.rolling(window=window_size, center=False).max() -
            candles.low.rolling(window=window_size, center=False).min()
        )) * 100
        return stoK

    def __calc_STOD(self, window_size):
        ''' ストキャスの%Dを計算（%Kの3日SMA） '''
        stoK = self.__calc_STOK(window_size)
        stoD = stoK.rolling(window=3, center=False).mean()
        stoD.name = 'stoD:3'
        return stoD

    def __calc_STOSD(self, window_size):
        ''' ストキャスの%SDを計算（%Dの3日SMA） '''
        stoD = self.__calc_STOD(window_size)
        stoSD = stoD.rolling(window=3, center=False).mean()
        stoSD.name = 'stoSD:3'
        return stoSD
