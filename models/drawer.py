# pyplot 指定可能な colors list
# https://pythondatascience.plavox.info/matplotlib/%E8%89%B2%E3%81%AE%E5%90%8D%E5%89%8D

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mpl_finance
from models.chart_watcher import FXBase

class FigureDrawer():

    PLOT_TYPE = {
        'dot': 0, 'long':  1, 'short': 2, 'exit': 3, 'break': 4,
        'simple-line': 11, 'dashed-line': 12
    }
    POS_TYPE  = { 'neutral': 0, 'over': 1, 'beneath': 2 }

    def __init__(self):
        self.__figure, (self.__axis1) = \
            plt.subplots(nrows=1, ncols=1, figsize=(10,5), dpi=200)
        self.__axis1.set_title('FX candles')

    def draw_df_on_plt(self, df, plot_type=PLOT_TYPE['simple-line'], color='black'):
        ''' DataFrameを受け取って、各columnを描画 '''
        # エラー防止処理
        if df is None:
            return { 'error': '[Drawer] データがありません' }
        if type(df) is not pd.core.frame.DataFrame:
            return { 'error': '[Drawer] DataFrame型以外が渡されました' }

        # 描画
        # http://sinhrks.hatenablog.com/entry/2015/06/18/221747
        if plot_type == FigureDrawer.PLOT_TYPE['simple-line']:
            for key, column in df.iteritems():
                self.__axis1.plot(x=df.index, y=column.values, label=key, c=color, linewidth=1.0)
        elif plot_type == FigureDrawer.PLOT_TYPE['dashed-line']:
            for key, column in df.iteritems():
                self.__axis1.plot(x=df.index, y=column.values, label=key, c=color, linestyle='dashed', linewidth=0.5)
        elif plot_type == FigureDrawer.PLOT_TYPE['dot']:
            for key, column in df.iteritems():
                self.__axis1.scatter(x=df.index, y=column.values, label=key, c=color, marker='d', s=3)
        return { 'success': 'dfを描画' }

    def draw_positionDf_on_plt(self, df, plot_type=PLOT_TYPE['long']):
        trade_marker_size = 40
        if plot_type == FigureDrawer.PLOT_TYPE['long']:
            edgecolors = 'red'
            label = 'long'
            mark  = '^'
        elif plot_type == FigureDrawer.PLOT_TYPE['short']:
            edgecolors = 'blue'
            label = 'short'
            mark  = 'v'
        self.__axis1.scatter(x=df.index, y=df.price,
            marker=mark, edgecolors=edgecolors, label=label,
            color='white', s=trade_marker_size
        )

    def draw_indexes_on_plt(self, index_array, plot_type=PLOT_TYPE['long'], pos=POS_TYPE['neutral']):
        ''' index_arrayを受け取って、各値(int)を描画 '''
        trade_marker_size = 40
        if plot_type == FigureDrawer.PLOT_TYPE['exit']:
            size  = trade_marker_size
            color = 'red'
            edgecolors = None
            label = 'exit'
            mark  = 'x'
        elif plot_type == FigureDrawer.PLOT_TYPE['break']:
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
            x=index_array,
            y=FXBase.get_candles().close[index_array] * gap,
            marker=mark, color=color, edgecolors=edgecolors,
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
        # 現画像サイズだとジャストな数:16
        num_break_xticks_into = 16

        ## X軸の見た目を整える
        candles        = FXBase.get_candles()
        xticks_number  = int(len(candles) / num_break_xticks_into)
        xticks_index   = range(0, len(candles), xticks_number)
        xticks_display = [candles.time.values[i][11:16] for i in xticks_index] # 時間を切り出すため、先頭12文字目から取る
        self.__axis1.yaxis.tick_right()
        self.__axis1.yaxis.grid(color='lightgray', linestyle='dashed', linewidth=0.5)
        plt.sca(self.__axis1)
        plt.xticks(xticks_index, xticks_display)
        plt.legend(loc='best')
        plt.savefig('figure.png')
        return { 'success': '[Drawer] 描画済みイメージをpng化' }

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
    drawer.draw_candles()
    result = drawer.create_png()

    # 結果表示
    if 'success' in result:
        print(result['success'], '(^ワ^*)')
    else:
        print(result['error'],   '(´・ω・`)')
