import math
from scipy.stats   import linregress
from chart_watcher import FXBase

#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #
#     トレンドライン生成・ブレイクポイント判定処理
#  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #  #
class Indicators(FXBase):
    def __init__(self):
        result = self.__generate_trendlines()
        if 'success' in result:
            print(result['success'])
        else:
            print(result['error'])


    def __get_local_extremum(self, start, end, bool_high):
        ''' 高値(high) / 安値(low)の始点 / 支点を取得
            チャートを単回帰分析し、結果直線よりも上（下）の値だけで再度単回帰分析...
            を繰り返し、2～3点に絞り込む
            local_extremum 又は extremal: 局所的極値のこと、極大値と極小値両方を指す（数学用語） '''
        sign = 'high' if bool_high else 'low'
        extremals = FXBase.candles[start:end+1]
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
    def __generate_trendlines(self, span=20, min_interval=3):
        if FXBase.candles is None: return { 'error': 'データが存在しません' }
        trendlines = { 'high': [], 'low': [] }

        # [下降・上昇]の２回ループ
        for bool_high in [True, False]:
            high_or_low = 'high' if bool_high else 'low'
            sign        = 1      if bool_high else -1

            # for i in array[start:end-1:step]:
            for i in FXBase.candles.index[::span/2]:
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
                    trendline = regression[0] * FXBase.candles['time_id'][i:i+span*2] + regression[1]
                    trendline.name = 'x_%s' % str(i)
                    trendlines[high_or_low].append(trendline)

        self.desc_trends = pd.concat(trendlines['high'], axis=1)
        self.asc_trends  = pd.concat(trendlines['low'],  axis=1)
        return { 'success': 'トレンドラインを生成しました' }

    def get_breakpoints(self):
        ''' トレンドブレイク箇所を配列で返す：今は下降トレンドのブレイクのみ '''
        close_candles = FXBase.candles.copy().close
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
                    # i, i+1 の行に Nan が入っている場合もスキップ
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
        return trendbreaks

if __name__ == '__main__':
    import chart_watcher as cw
    c_watcher = cw.ChartWatcher()
    c_watcher.request_chart()
    g_indi = Indicators()
    if FXBase.candles is None:
        print('表示可能なデータが存在しません')
    else:
        print(g_indi.desc_trends.tail())
