# pyplot 指定可能な colors list
# https://pythondatascience.plavox.info/matplotlib/%E8%89%B2%E3%81%AE%E5%90%8D%E5%89%8D

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mpl_finance
from models.chart_watcher import FXBase

class FigureDrawer(FXBase):
    PLOT_TYPE = { 'dot': 0, 'simple-line': 1, 'dashed-line': 2 }

    def __init__(self):
        self.__figure, (self.__axis1) = \
            plt.subplots(nrows=1, ncols=1, figsize=(10,5), dpi=200)
        self.__axis1.set_title('FX candles')

    def draw_df_on_plt(self, df, plot_type=PLOT_TYPE['simple-line'], color='black'):
        ''' DataFrameを受け取って、各columnを描画 '''
        # エラー防止処理
        if df is None:
            return { 'error': 'データがありません' }
        if type(df) is not pd.core.frame.DataFrame:
            return { 'error': 'DataFrame型以外が渡されました' }

        # 描画
        # http://sinhrks.hatenablog.com/entry/2015/06/18/221747
        if plot_type == FigureDrawer.PLOT_TYPE['simple-line']:
            for key, column in df.iteritems():
                self.__axis1.plot(df.index, column.values, label=key, c=color)
        elif plot_type == FigureDrawer.PLOT_TYPE['dashed-line']:
            for key, column in df.iteritems():
                self.__axis1.plot(df.index, column.values, label=key, c=color, linestyle='dashed', linewidth=0.7)
        elif plot_type == FigureDrawer.PLOT_TYPE['dot']:
            for key, column in df.iteritems():
                self.__axis1.scatter(df.index, column.values, label=key, c=color, marker='d', s=3)
        return { 'success': 'dfを描画' }

    def draw_indexes_on_plt(self, array, over_candle=True):
        ''' arrayを受け取って、各値(int)を描画 '''
        if over_candle:
            gap   = 1.0005
            color = 'red'
            label = 'GC'
        else:
            gap   = 0.9995
            color = 'blue'
            label = 'DC'
        self.__axis1.scatter(
            array,
            FXBase.candles.close[array]*gap,
            marker='o', color=color, label=label, s=20
        )

    def draw_candles(self):
        ''' 取得済みチャートを描画 '''
        mpl_finance.candlestick2_ohlc(
            self.__axis1,
            opens  = self.candles.open.values,
            highs  = self.candles.high.values,
            lows   = self.candles.low.values,
            closes = self.candles.close.values,
            width=0.6, colorup='#77d879', colordown='#db3f3f'
        )
        return { 'success': 'チャートを描画' }

    def create_png(self):
        ''' 描画済みイメージをpngファイルに書き出す '''
        ## X軸の見た目を整える
        xticks_number  = 12 # 12本(60分)刻みに目盛りを書く
        xticks_index   = range(0, len(FXBase.candles), xticks_number)
        xticks_display = [FXBase.candles.time.values[i][11:16] for i in xticks_index] # 時間を切り出すため、先頭12文字目から取る
        self.__axis1.yaxis.tick_right()
        self.__axis1.yaxis.grid(color='lightgray', linestyle='dashed')
        plt.sca(self.__axis1)
        plt.xticks(xticks_index, xticks_display)
        plt.legend(loc='upper left')
        plt.savefig('figure.png')
        return { 'success': '描画済みイメージをpng化' }

    def get_sample_df(self):
        ''' サンプルdf生成 '''
        import random
        import numpy  as np
        xs = range(1, 284)
        y  = [x * random.randint(436, 875) for x in xs]
        y2 = np.sin(xs) * 50000
        df = pd.DataFrame({ 'y': y, 'sin': y2 }, index=xs)
        return df

if __name__ == '__main__':
    import chart_watcher as watcher
    w = watcher.ChartWatcher()
    if 'error' in w.request_chart():
        print('失敗')
        exit()

    # 描画
    drawer = FigureDrawer()
    # drawer.draw_df_on_plt(df=watcher.FXBase.candles.drop('time', axis=1))
    drawer.draw_candles()
    result = drawer.create_png()

    # 結果表示
    if 'success' in result:
        print(result['success'], '(^ワ^*)')
    else:
        print(result['error'],   '(´・ω・`)')
