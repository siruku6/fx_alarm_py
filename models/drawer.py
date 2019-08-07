# pyplot 指定可能な colors list
# https://pythondatascience.plavox.info/matplotlib/%E8%89%B2%E3%81%AE%E5%90%8D%E5%89%8D

import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import mpl_finance
from models.oanda_py_client import FXBase

matplotlib.use('Agg')


class FigureDrawer():

    PLOT_TYPE = {
        'dot': 0, 'long': 1, 'short': 2, 'trail': 3, 'exit': 4, 'break': 5,
        'simple-line': 11, 'dashed-line': 12
    }
    POS_TYPE = {'neutral': 0, 'over': 1, 'beneath': 2}

    def __init__(self):
        self.init_figure()

    def init_figure(self):
        ''' 生成画像の初期設定 '''
        self.__figure, (self.__axis1, self.__axis2) = plt.subplots(
            nrows=2, ncols=1, gridspec_kw={'height_ratios': [3, 1]},
            figsize=(8, 4), dpi=144
        )
        # INFO: https://zaburo-ch.github.io/post/20141217_0/
        self.__figure.subplots_adjust(left=0.03, right=0.92, bottom=0.03, top=0.92, hspace=0.35)

    def close_all(self):
        # https://stackoverflow.com/questions/21884271/warning-about-too-many-open-figures
        plt.close('all')

    def draw_df_on_plt(self, d_frame, plot_type, color='black', nolabel=None, plt_id=1):
        ''' DataFrameを受け取って、各columnを描画 '''
        # エラー防止処理
        if d_frame is None:
            return {'error': '[Drawer] データがありません'}
        if type(d_frame) is not pd.core.frame.DataFrame:
            return {'error': '[Drawer] DataFrame型以外が渡されました'}

        plt_axis = self.__axis1 if plt_id == 1 else self.__axis2

        # 描画
        # http://sinhrks.hatenablog.com/entry/2015/06/18/221747
        if plot_type == FigureDrawer.PLOT_TYPE['simple-line']:
            for key, column in d_frame.iteritems():
                plt_axis.plot(d_frame.index, column.values, label=nolabel or key, c=color, linewidth=0.6)
        elif plot_type == FigureDrawer.PLOT_TYPE['dashed-line']:
            for key, column in d_frame.iteritems():
                plt_axis.plot(d_frame.index, column.values, label=nolabel or key, c=color, linestyle='dashed', linewidth=0.6)
        elif plot_type == FigureDrawer.PLOT_TYPE['dot']:
            for key, column in d_frame.iteritems():
                plt_axis.scatter(x=d_frame.index, y=column.values, label=nolabel or key, c=color, marker='d', s=2)

        print('[Drawer] ', d_frame.columns[0], 'を描画')
        return {'success': 'd_frameを描画'}

    def draw_positionDf_on_plt(self, df, plot_type=PLOT_TYPE['long'], nolabel=None):
        ''' __hist_positionsから抽出したdfを受け取って描画 '''
        trade_marker_size = 15
        if plot_type == FigureDrawer.PLOT_TYPE['long']:
            color = 'white'
            edgecolors = 'red'
            label = 'long'
            mark = '^'
        elif plot_type == FigureDrawer.PLOT_TYPE['short']:
            color = 'white'
            edgecolors = 'blue'
            label = 'short'
            mark = 'v'
        elif plot_type == FigureDrawer.PLOT_TYPE['trail']:
            color = 'orange'
            edgecolors = None
            label = 'trail'
            mark = '_'
        elif plot_type == FigureDrawer.PLOT_TYPE['exit']:
            color = 'red'
            edgecolors = None
            label = 'exit'
            mark = 'x'

        if plot_type == FigureDrawer.PLOT_TYPE['trail']:
            y = df.stoploss
        else:
            y = df.price
        self.__axis1.scatter(
            x=df.sequence, y=y,
            marker=mark, edgecolors=edgecolors, label=nolabel or label,
            color=color, s=trade_marker_size, linewidths=0.7
        )

    # INFO: 今は使われていない
    # def draw_indexes_on_plt(self, index_array, plot_type=PLOT_TYPE['long'], pos=POS_TYPE['neutral']):
    #     ''' index_arrayを受け取って、各値(int)を描画 '''
    #     if plot_type == FigureDrawer.PLOT_TYPE['break']:
    #         size = 10
    #         mark = 'o'
    #         if pos:
    #             color = 'red'
    #             label = 'GC'
    #         else:
    #             color = 'blue'
    #             label = 'DC'
    #
    #     if pos == FigureDrawer.POS_TYPE['over']:
    #         gap = 1.0005
    #     elif pos == FigureDrawer.POS_TYPE['beneath']:
    #         gap = 0.9995
    #     else :
    #         gap = 1.0
    #
    #     self.__axis1.scatter(
    #         x=index_array,
    #         y=FXBase.get_candles().close[index_array] * gap,
    #         marker=mark, color=color, edgecolors=edgecolors,
    #         label=label, s=size
    #     )

    def draw_candles(self, start=0, end=None):
        ''' 取得済みチャートを描画 '''
        target_candles = FXBase.get_candles()[start:end]
        mpl_finance.candlestick2_ohlc(
            self.__axis1,
            opens=target_candles.open.values,
            highs=target_candles.high.values,
            lows=target_candles.low.values,
            closes=target_candles.close.values,
            width=0.6, colorup='#77d879', colordown='#db3f3f'
        )
        return {'success': 'チャートを描画', 'time': target_candles.time}

    def create_png(self, instrument, granularity, sr_time, num=0):
        ''' 描画済みイメージをpngファイルに書き出す '''
        # OPTIMIZE: x軸目盛の分割数...今はこれでいいが、最適化する
        num_break_xticks_into = 12

        # X軸の見た目を整える
        self.__axis1.set_title('{inst}-{granularity} candles (len={len})'.format(
            inst=instrument, granularity=granularity, len=len(FXBase.get_candles())
        ))
        self.__axis1.yaxis.tick_right()
        self.__axis2.yaxis.tick_right()

        # INFO: axis1
        plt.sca(self.__axis1)
        xticks_number = int(len(sr_time) / num_break_xticks_into)
        if xticks_number > 0:
            xticks_index = range(0, len(sr_time), xticks_number)
            # INFO: 日付から表示するため、先頭12文字目から取る
            xticks_display = [sr_time.values[i][5:16] for i in xticks_index]
            plt.xticks(xticks_index, xticks_display, rotation=30, fontsize='small')
            plt.legend(loc='best', fontsize=8)
            plt.grid(which='major', linestyle='dashed')

        # INFO: axis2
        plt.sca(self.__axis2)
        plt.hlines([20, 80], 0, len(sr_time), color='lightgray', linestyle='dashed', linewidth=0.5)
        if xticks_number > 0:
            plt.xticks(xticks_index, [])
            # plt.tick_params(labelbottom=False)
        plt.grid(linestyle='dashed')
        plt.legend(loc='upper left', fontsize=8)

        plt.savefig('tmp/figure_{num}.png'.format(num=num))
        return {'success': '[Drawer] 描画済みイメージをpng化 {}'.format(num + 1)}
