import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mpl_finance
import chart_watcher as watcher

class FigureDrawer():
    def __init__(self):
        self.__figure, (self.__axis1) = \
            plt.subplots(nrows=1, ncols=1, figsize=(20,10), dpi=200)
        self.__axis1.set_title('FX candles')

    def draw_df_on_plt(self, df):
        ''' DataFrameを受け取って、各columnを描画 '''
        # エラー防止処理
        if df is None:
            return { 'error': 'データがありません' }
        if type(df) is not pd.core.frame.DataFrame:
            return { 'error': 'DataFrame型以外が渡されました' }

        # 描画
        # http://sinhrks.hatenablog.com/entry/2015/06/18/221747
        for key, column in df.iteritems():
            self.__axis1.plot(df.index, column.values, label=key)
        return { 'success': 'dfを描画' }

    def draw_candles(self):
        ''' 取得済みチャートを描画 '''
        mpl_finance.candlestick2_ohlc(
            self.__axis1,
            opens  = watcher.FXBase.candles.open.values,
            highs  = watcher.FXBase.candles.high.values,
            lows   = watcher.FXBase.candles.low.values,
            closes = watcher.FXBase.candles.close.values,
            width=0.6, colorup='#77d879', colordown='#db3f3f'
        )
        return { 'success': 'チャートを描画' }

    def create_png(self):
        ''' 描画済みイメージをpngファイルに書き出す '''
        plt.legend(loc='upper right')
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
    w = watcher.ChartWatcher()
    if 'error' in w.request_chart():
        print('失敗')
        exit()

    # 描画
    drawer = FigureDrawer()
    drawer.draw_df_on_plt(df=watcher.FXBase.candles.drop('time', axis=1))
    drawer.draw_candles()
    result = drawer.create_png()

    # 結果表示
    if 'success' in result:
        print(result['success'], '(^ワ^*)')
    else:
        print(result['error'],   '(´・ω・`)')
