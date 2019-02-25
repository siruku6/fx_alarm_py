# pyplot 指定可能な colors list
# https://pythondatascience.plavox.info/matplotlib/%E8%89%B2%E3%81%AE%E5%90%8D%E5%89%8D

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mpl_finance
from models.chart_watcher import FXBase

class FigureDrawer():

    PLOT_TYPE = { 'dot':     0, 'simple-line': 1, 'dashed-line': 2 }
    DOT_TYPE  = { 'entry':   0, 'exit':        1, 'break':       2 }
    POS_TYPE  = { 'neutral': 0, 'over':        1, 'beneath':     2 }

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
                self.__axis1.plot(df.index, column.values, label=key, c=color, linewidth=1.0)
        elif plot_type == FigureDrawer.PLOT_TYPE['dashed-line']:
            for key, column in df.iteritems():
                self.__axis1.plot(df.index, column.values, label=key, c=color, linestyle='dashed', linewidth=0.5)
        elif plot_type == FigureDrawer.PLOT_TYPE['dot']:
            for key, column in df.iteritems():
                self.__axis1.scatter(df.index, column.values, label=key, c=color, marker='d', s=3)
        return { 'success': 'dfを描画' }

    def draw_indexes_on_plt(self, index_array, dot_type=DOT_TYPE['entry'], pos=POS_TYPE['neutral']):
        ''' index_arrayを受け取って、各値(int)を描画 '''
        if dot_type == FigureDrawer.DOT_TYPE['entry']:
            size  = 40
            color = 'red'
            label = 'entry'
            mark  = 'v'
        elif dot_type == FigureDrawer.DOT_TYPE['exit']:
            size  = 40
            color = 'red'
            label = 'exit'
            mark  = 'x'
        elif dot_type == FigureDrawer.DOT_TYPE['break']:
            size = 10
            mark = 'o'
            if pos:
                color = 'red'
                label = 'GC'
            else:
                color = 'blue'
                label = 'DC'

        if pos == FigureDrawer.POS_TYPE['over']:
            gap = 1.0005
        elif pos == FigureDrawer.POS_TYPE['beneath']:
            gap = 0.9995
        else :
            gap = 1.0

        self.__axis1.scatter(
            index_array,
            FXBase.get_candles().close[index_array] * gap,
            marker=mark, color=color, facecolor=None,
            label=label, s=size
        )

    def draw_candles(self):
        ''' 取得済みチャートを描画 '''
        mpl_finance.candlestick2_ohlc(
            self.__axis1,
            opens  = FXBase.get_candles().open.values,
            highs  = FXBase.get_candles().high.values,
            lows   = FXBase.get_candles().low.values,
            closes = FXBase.get_candles().close.values,
            width=0.6, colorup='#77d879', colordown='#db3f3f'
        )
        return { 'success': 'チャートを描画' }

    def create_png(self):
        ''' 描画済みイメージをpngファイルに書き出す '''
        ## X軸の見た目を整える
        candles        = FXBase.get_candles()
        # xticks_number  = 12 # 12本(60分)刻みに目盛りを書く
        xticks_number  = int(len(candles) / 16) # 現画像サイズだとジャストな数
        xticks_index   = range(0, len(candles), xticks_number)
        xticks_display = [candles.time.values[i][11:16] for i in xticks_index] # 時間を切り出すため、先頭12文字目から取る
        self.__axis1.yaxis.tick_right()
        self.__axis1.yaxis.grid(color='lightgray', linestyle='dashed', linewidth=0.5)
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
    if 'error' in w.reload_chart():
        print('失敗')
        exit()

    # 描画
    drawer = FigureDrawer()
    # drawer.draw_df_on_plt(df=FXBase.get_candles().drop('time', axis=1))
    drawer.draw_candles()
    result = drawer.create_png()

    # 結果表示
    if 'success' in result:
        print(result['success'], '(^ワ^*)')
    else:
        print(result['error'],   '(´・ω・`)')
