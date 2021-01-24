import datetime
import matplotlib
import matplotlib.pyplot as plt
import mplfinance.original_flavor as mpf
import numpy as np
import pandas as pd

import models.tools.mathematics as mtmtcs
from models.candle_storage import FXBase

matplotlib.use('Agg')
matplotlib.rcParams['axes.xmargin'] = 0
# matplotlib.rcParams['figure.autolayout'] = False


class FigureDrawer():

    PLOT_TYPE = {
        'dot': 0, 'long': 1, 'short': 2, 'trail': 3, 'exit': 4, 'break': 5,
        'simple-line': 11, 'dashed-line': 12, 'bar': 13
    }
    POS_TYPE = {'neutral': 0, 'over': 1, 'beneath': 2}

    def __init__(self, rows_num, instrument):
        self.init_figure(rows_num)
        self._instrument = instrument

    def init_figure(self, rows_num=2):
        ''' 生成画像の初期設定 '''
        if rows_num == 2:
            self.__figure, self.__axes = plt.subplots(
                nrows=2, ncols=1, gridspec_kw={'height_ratios': [3, 1]},
                figsize=(8, 5), dpi=144
            )
        else:
            self.__figure, self.__axes = plt.subplots(
                nrows=3, ncols=1, gridspec_kw={'height_ratios': [7, 2, 1]},
                figsize=(8, 6), dpi=144
            )
            self.__axes[2].yaxis.tick_right()

        self.__axes[0].yaxis.tick_right()
        self.__axes[1].yaxis.tick_right()

        # INFO: https://zaburo-ch.github.io/post/20141217_0/
        self.__figure.subplots_adjust(left=0.05, right=0.90, bottom=0.18, top=0.92, hspace=0.05)

    def close_all(self):
        # https://stackoverflow.com/questions/21884271/warning-about-too-many-open-figures
        plt.close('all')

    # OPTIMIZE: Analyzerクラスと密結合なメソッドになってしまった
    def draw_indicators(self, d_frame):
        ''' DateFrameからindicatorを描画 '''
        # 60EMA is necessary?
        # self.draw_df_on_plt(d_frame.loc[:, ['60EMA']], FigureDrawer.PLOT_TYPE['dashed-line'], color='lime')

        simple_lines_df = d_frame[['20SMA', '10EMA', 'sigma*1_band', 'sigma*2_band']]
        colors = ('lightskyblue', 'cyan', 'midnightblue', 'royalblue')
        self.draw_df_on_plt(simple_lines_df, FigureDrawer.PLOT_TYPE['simple-line'], colors=colors)
        self.draw_df_on_plt(d_frame.loc[:, ['sigma*-1_band']], FigureDrawer.PLOT_TYPE['simple-line'], color='midnightblue', nolabel='_nolegend_')
        self.draw_df_on_plt(d_frame.loc[:, ['sigma*-2_band']], FigureDrawer.PLOT_TYPE['simple-line'], color='royalblue', nolabel='_nolegend_')
        self.draw_df_on_plt(d_frame.loc[:, ['SAR']], FigureDrawer.PLOT_TYPE['dot'], color='purple')
        self.draw_df_on_plt(d_frame.loc[:, ['stoD_3']], FigureDrawer.PLOT_TYPE['simple-line'], color='turquoise', plt_id=2)
        self.draw_df_on_plt(d_frame.loc[:, ['stoSD_3']], FigureDrawer.PLOT_TYPE['simple-line'], color='orangered', plt_id=2)
        # self.draw_df_on_plt(d_frame.loc[:, ['regist']], FigureDrawer.PLOT_TYPE['dot'], color='orangered', size=0.5)
        # self.draw_df_on_plt(d_frame.loc[:, ['support']], FigureDrawer.PLOT_TYPE['dot'], color='blue', size=0.5)

    def draw_long_indicators(self, candles, min_point):
        candles = candles.reset_index(drop=True)

        # INFO: calculate the height of long-indicators in the figure
        candle_digits = mtmtcs.int_log10(candles['close'].iat[0])
        gap = mtmtcs.generate_float_digits_of(candle_digits - 3)
        y_height = min_point - gap
        y_height2 = min_point - gap * 3

        if 'stoD_over_stoSD' in candles.columns:
            # long-stoc
            bull_long_stoc = candles.loc[candles['stoD_over_stoSD'], ['stoD_over_stoSD']].assign(stoD_over_stoSD=y_height)
            bear_long_stoc = candles.loc[~candles['stoD_over_stoSD'], ['stoD_over_stoSD']].assign(stoD_over_stoSD=y_height)
            self.draw_df_on_plt(bull_long_stoc, FigureDrawer.PLOT_TYPE['dot'], color='red')
            self.draw_df_on_plt(bear_long_stoc, FigureDrawer.PLOT_TYPE['dot'], color='blue', nolabel='_nolegend_')

            # long-trend
            self.draw_df_on_plt(candles.loc[:, ['long_10EMA']], FigureDrawer.PLOT_TYPE['simple-line'], color='lightslategray')
            self.draw_df_on_plt(candles.loc[:, ['long_20SMA']], FigureDrawer.PLOT_TYPE['simple-line'], color='darkslategray')

            bull_long_trend = candles.loc[candles['long_trend'] == 'bull', ['long_trend']].assign(long_trend=y_height2)
            bear_long_trend = candles.loc[candles['long_trend'] == 'bear', ['long_trend']].assign(long_trend=y_height2)
            self.draw_df_on_plt(bull_long_trend, FigureDrawer.PLOT_TYPE['dot'], color='green')
            self.draw_df_on_plt(bear_long_trend, FigureDrawer.PLOT_TYPE['dot'], color='red', nolabel='_nolegend_')

    def draw_df_on_plt(self, d_frame, plot_type, color='black', colors=None, size=1, nolabel=None, plt_id=1):
        ''' DataFrameを受け取って、各columnを描画 '''
        # エラー防止処理
        if type(d_frame) is not pd.core.frame.DataFrame:
            raise TypeError(
                '[Drawer] draw_df_on_plt cannot draw from except DataFrame: {}'.format(type(d_frame))
            )

        if colors is None:
            colors = [color] * len(d_frame.columns)
        plt_axis = self.__axes[plt_id - 1]
        # 描画
        # http://sinhrks.hatenablog.com/entry/2015/06/18/221747
        if plot_type == FigureDrawer.PLOT_TYPE['simple-line']:
            for (key, column), color in zip(d_frame.iteritems(), colors):
                plt_axis.plot(d_frame.index, column.values, label=nolabel or key, c=color, linewidth=0.5)
        elif plot_type == FigureDrawer.PLOT_TYPE['dashed-line']:
            for (key, column), color in zip(d_frame.iteritems(), colors):
                plt_axis.plot(d_frame.index, column.values, label=nolabel or key, c=color, linestyle='dashed', linewidth=0.5)
        elif plot_type == FigureDrawer.PLOT_TYPE['dot']:
            for (key, column), color in zip(d_frame.iteritems(), colors):
                plt_axis.scatter(x=d_frame.index, y=column.values, label=nolabel or key, c=color, marker='d', s=size, alpha=0.5)
        elif plot_type == FigureDrawer.PLOT_TYPE['bar']:
            for (key, column), color in zip(d_frame.iteritems(), colors):
                plt_axis.bar(x=np.arange(len(d_frame)), height=column.values, label=nolabel or key, width=0.6, color=color)

        return {'success': 'd_frameを描画'}

    def draw_positions_df(self, positions_df, plot_type=PLOT_TYPE['long'], size=20, nolabel=None):
        ''' __hist_positionsから抽出したdfを受け取って描画 '''
        if plot_type == FigureDrawer.PLOT_TYPE['long']:
            color = 'white'
            edgecolors = 'green'
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

        # HACK: price に Nan が含まれているとエラーが発生していたので除去している
        drawing_targets = positions_df.dropna()
        index = drawing_targets['sequence'] if 'sequence' in drawing_targets.columns else drawing_targets.index

        self.__axes[0].scatter(
            x=index, y=drawing_targets.price,
            marker=mark, edgecolors=edgecolors, label=nolabel or label,
            color=color, s=size, linewidths=0.7
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
    #     self.__axes[0].scatter(
    #         x=index_array,
    #         y=FXBase.get_candles().close[index_array] * gap,
    #         marker=mark, color=color, edgecolors=edgecolors,
    #         label=label, s=size
    #     )

    def draw_candles(self, target_candles):
        ''' 取得済みチャートを描画 '''
        mpf.candlestick2_ohlc(
            self.__axes[0],
            opens=target_candles.open.values,
            highs=target_candles.high.values,
            lows=target_candles.low.values,
            closes=target_candles.close.values,
            width=0.6, colorup='#77d879', colordown='#db3f3f'
        )
        return {'success': 'チャートを描画', 'time': target_candles.time}

    def draw_vertical_lines(self, indexes, vmin, vmax):
        self.__axes[0].vlines(indexes, vmin, vmax, color='yellow', linewidth=0.5)
        self.__axes[1].vlines(indexes, 0, 100, color='yellow', linewidth=0.5)

    def create_png(self, granularity, sr_time, num=0, filename=None):
        ''' 描画済みイメージをpngファイルに書き出す '''
        self.__axes[0].set_title('{inst}-{granularity} candles (len={len})'.format(
            inst=self._instrument, granularity=granularity, len=len(FXBase.get_candles())
        ))
        xticks_number, xticks_index = self.__prepare_xticks(sr_time)

        # INFO: axis1
        plt.sca(self.__axes[0])
        self.__apply_default_style(plt, xticks_number, indexes=xticks_index)

        # INFO: axis2
        plt.sca(self.__axes[1])
        self.__apply_default_style(plt, xticks_number, indexes=xticks_index)
        plt.hlines([20, 80], 0, len(sr_time), color='lightgray', linestyle='dashed', linewidth=0.5)
        plt.yticks([20, 80], [20, 80])

        if len(self.__axes) == 3:
            # INFO: axis3
            plt.sca(self.__axes[2])
            self.__apply_default_style(plt, xticks_number, indexes=xticks_index, legend=False)
            self.__axes[2].yaxis.set_major_locator(matplotlib.ticker.AutoLocator())
            # INFO: hist と backtest で桁が違うせいで問題になる, hist は pl が万単位
            # self.__axes[2].yaxis.set_minor_locator(matplotlib.ticker.MultipleLocator(1.0))

        # INFO: x軸の目盛表示
        if xticks_number > 0:
            # INFO: 日付から表示するため、先頭12文字目から取る
            xticks_display = [sr_time.values[i][5:16] for i in xticks_index]
            plt.tick_params(top=False, bottom=True)
            plt.xticks(xticks_index, xticks_display, rotation=30, fontsize=6)
            plt.xlabel('Datetime (UTC+00:00)', fontsize=6)

        png_filename = '{}_{}'.format(filename or 'figure', self._instrument)
        plt.savefig('tmp/images/{filename}_{num}_{date}.png'.format(
            filename=png_filename, num=num, date=datetime.datetime.strftime(datetime.datetime.now(), '%Y%m%d_%H%M%S')
        ))
        return {'success': '[Drawer] 描画済みイメージをpng化完了 {}'.format(num + 1)}

    def __prepare_xticks(self, sr_time):
        # OPTIMIZE: x軸目盛の分割数...今はこれでいいが、最適化する
        num_break_xticks_into = 24
        xticks_size = int(len(sr_time) / num_break_xticks_into)
        xticks_index = range(0, len(sr_time), xticks_size) if xticks_size > 0 else []
        return xticks_size, xticks_index

    def __apply_default_style(self, plt_module, xticks_num, indexes, legend=True):
        if xticks_num > 0:
            plt_module.xticks(indexes, [])
        if legend:
            plt_module.legend(loc='upper left', fontsize=4)  # best だと結構右に来て邪魔
        plt_module.grid(which='major', linestyle='dashed', linewidth=0.5)
