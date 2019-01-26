import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
# import mpl_finance

class FigureDrawer():
    def draw_df_on_plt(self, df):
        '''DataFrameを受け取って、各columnを描画'''
        # エラー防止処理
        if df is None:
            return { 'error': 'データがありません' }
        if type(df) is not pd.core.frame.DataFrame:
            return { 'error': 'DataFrame型以外が渡されました' }

        # 描画
        fig, ax = plt.subplots()
        ax.set_title('IMINASHI GRAPH')
        # http://sinhrks.hatenablog.com/entry/2015/06/18/221747
        for key, column in df.iteritems():
            ax.plot(df.index, column.values, label=key)
        plt.legend(loc='upper right')
        plt.savefig('figure.png')
        return { 'success': '入力データから画像を生成しました' }

if __name__ == '__main__':
    # データ生成・整形
    import random
    import numpy  as np
    import pandas as pd
    xs = range(1, 284)
    y  = [x * random.randint(436, 875) for x in xs]
    y2 = np.sin(xs) * 50000
    df = pd.DataFrame({ 'y': y, 'sin': y2 }, index=xs)

    # 描画
    drawer = FigureDrawer()
    result = drawer.draw_df_on_plt(df=df)

    # 結果表示
    if 'success' in result:
        print(result['success'], '(^ワ^*)')
    else:
        print(result['error'],   '(´・ω・`)')
