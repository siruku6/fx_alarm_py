from typing import Optional

import numpy as np
import pandas as pd

# from scipy.stats import linregress


class Analyzer:
    INDICATOR_NAMES = (
        # 60EMA is necessary?
        "20SMA",
        "10EMA",
        "60EMA",
        "sigma*1_band",
        "sigma*-1_band",
        "sigma*2_band",
        "sigma*-2_band",
        "SAR",
        "stoD",
        "stoSD",
        "support",
        "regist",
    )

    # For Trendline
    MAX_EXTREMAL_CNT = 3

    # For Parabolic
    INITIAL_AF = 0.02
    MAX_AF = 0.2

    def __init__(self, indicator_names=None):
        self.__indicator_list = indicator_names or Analyzer.INDICATOR_NAMES
        self.__indicators = {name: None for name in self.__indicator_list + ("long_indicators",)}
        self.__base_candles = None

        # # Trendline
        # self.desc_trends = None
        # self.asc_trends = None
        # self.jump_trendbreaks = None
        # self.fall_trendbreaks = None

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                       Driver                        #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    def calc_indicators(self, candles, long_span_candles=None, stoc_only=False):
        if candles is None or candles.empty:
            print("[ERROR] Analyzer: 分析対象データがありません")
            exit()

        self.__base_candles = candles.copy()
        self.__indicators["time"] = candles["time"].copy()
        if long_span_candles is not None:
            self.__indicators["long_indicators"] = self.__prepare_long_indicators(long_span_candles)

        result_msg = {"success": "[Analyzer] indicators算出完了"}
        if stoc_only is True:
            return result_msg

        target_indicators = (
            name
            for name in self.__indicator_list
            if name in ("20SMA", "10EMA", "60EMA", "SAR", "stoD", "stoSD", "regist", "support")
        )
        for target in target_indicators:
            self.__indicators[target] = self.__calc(target)
        if "sigma*1_band" in self.__indicator_list:
            self.__calc_bollinger_bands(band_width=1)
        if "sigma*2_band" in self.__indicator_list:
            self.__calc_bollinger_bands(band_width=2)

        # result = self.__calc_trendlines()
        # if 'success' in result:
        #     print(result['success'])
        #     self.__get_breakpoints()
        return result_msg

    def __calc(self, target, **kwargs):
        method_dict = {
            "20SMA": self.__calc_sma,
            "10EMA": self.__calc_ema,
            "60EMA": self.__calc_60ema,
            "SAR": self.__calc_parabolic,
            "stoD": self.__calc_stod,
            "stoSD": self.__calc_stosd,
            "regist": self.__calc_registance,
            "support": self.__calc_support,
        }
        return method_dict.get(target)(**kwargs)

    def get_indicators(
        self, start: Optional[int] = None, end: Optional[int] = None
    ) -> pd.DataFrame:
        indicators = pd.concat(
            [self.__indicators[name] for name in ("time",) + self.__indicator_list], axis=1
        )[start:end]
        return indicators

    def get_long_indicators(self):
        return self.__indicators["long_indicators"]

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                  Moving Average                     #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    def __calc_sma(self, closes=None, window_size=20):
        """単純移動平均線を生成"""
        close_candles = closes if closes is not None else self.__base_candles.loc[:, "close"]
        # mean()後の .dropna().reset_index(drop = True) を消去中
        sma = pd.Series.rolling(close_candles, window=window_size).mean()
        return pd.DataFrame(sma).rename(columns={"close": "20SMA"})

    def __calc_ema(self, closes=None, window_size=10):
        """指数平滑移動平均線を生成"""
        close_candles = closes if closes is not None else self.__base_candles.loc[:, "close"]
        # TODO: scipyを使うと早くなる
        # https://qiita.com/toyolab/items/6872b32d9fa1763345d8
        ema = close_candles.ewm(span=window_size).mean()
        return pd.DataFrame(ema).rename(columns={"close": "{}EMA".format(window_size)})

    def __calc_60ema(self, closes=None):
        return self.__calc_ema(closes, window_size=60)

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                  Bollinger Bands                    #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    def __calc_bollinger_bands(self, band_width=1, window_size=20):
        """ボリンジャーバンドを生成"""
        close_candles = self.__base_candles.close
        mean = pd.Series.rolling(close_candles, window=window_size).mean()
        standard_deviation = pd.Series.rolling(close_candles, window=window_size).std()
        positive_band_name = "sigma*{}_band".format(band_width)
        negative_band_name = "sigma*-{}_band".format(band_width)

        self.__indicators[positive_band_name] = pd.DataFrame(
            mean + standard_deviation * band_width
        ).rename(columns={"close": positive_band_name})
        self.__indicators[negative_band_name] = pd.DataFrame(
            mean - standard_deviation * band_width
        ).rename(columns={"close": negative_band_name})

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                     TrendLine                       #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # # iterate dataframe
    # https://stackoverflow.com/questions/7837722/what-is-the-most-efficient-way-to-loop-through-dataframes-with-pandas
    # def __calc_trendlines(self, span=20, min_interval=3):
    #     if FXBase.get_candles() is None:
    #         return {'error': '[Analyzer] データが存在しません'}
    #     FXBase.set_time_id()
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
    def calc_next_parabolic(self, last_sar, extr_price, acceleration_f=INITIAL_AF):
        return last_sar + acceleration_f * (extr_price - last_sar)

    def __parabolic_is_touched(self, bull, current_parabo, current_h, current_l):
        touch_lower_parabo = bull and (current_parabo > current_l)
        touch_upper_parabo = not bull and (current_parabo < current_h)
        if touch_lower_parabo or touch_upper_parabo:
            return True

        return False

    def __calc_parabolic(self):
        candles = self.__base_candles
        # 初期値
        acceleration_factor = Analyzer.INITIAL_AF
        # INFO: 初期状態は上昇トレンドと仮定して計算
        bull = True
        extreme_price = candles.high[0]
        temp_sar_array = [candles.low[0]]

        # HACK: dataframeのまま処理するより、to_dictで辞書配列化した方が処理が早い
        candles_array = candles.to_dict("records")
        # for i, row in candles.iterrows():
        for i, row in enumerate(candles_array):
            current_high = row["high"]
            current_low = row["low"]
            last_sar = temp_sar_array[-1]

            # レートがparabolicに触れたときの処理
            if self.__parabolic_is_touched(
                bull=bull, current_parabo=last_sar, current_h=current_high, current_l=current_low
            ):
                temp_sar = extreme_price
                acceleration_factor = Analyzer.INITIAL_AF
                extreme_price = current_low if bull else current_high
                bull = not bull
            else:
                # SARの仮決め
                # temp_sar = last_sar + acceleration_factor * (extreme_price - last_sar)
                temp_sar = self.calc_next_parabolic(
                    last_sar=last_sar, extr_price=extreme_price, acceleration_f=acceleration_factor
                )

                # AFの更新
                if (
                    (bull and extreme_price < current_high)
                    or not bull
                    and (extreme_price > current_low)
                ):
                    acceleration_factor = min(
                        acceleration_factor + Analyzer.INITIAL_AF, Analyzer.MAX_AF
                    )

                # SARの調整 値が更新されすぎないように抑える
                # 極値(extreme_price)の更新
                if bull:
                    temp_sar = min(
                        temp_sar, candles_array[i - 1]["low"], candles_array[i - 2]["low"]
                    )
                    extreme_price = max(extreme_price, current_high)
                else:
                    temp_sar = max(
                        temp_sar, candles_array[i - 1]["high"], candles_array[i - 2]["high"]
                    )
                    extreme_price = min(extreme_price, current_low)

            if i == 0:
                temp_sar_array[-1] = temp_sar
            else:
                temp_sar_array.append(temp_sar)
        return pd.DataFrame(data=temp_sar_array, columns=["SAR"])

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                    Stochastic                       #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    def __prepare_long_indicators(self, long_span_candles):
        tmp_candles = long_span_candles.copy().reset_index()
        tmp_candles["time"] = tmp_candles["time"].map(str)
        # INFO: stoc
        tmp_candles["long_stoD"] = self.__calc_stod(candles=tmp_candles, window_size=5)
        tmp_candles["long_stoSD"] = self.__calc_stosd(candles=tmp_candles, window_size=5)
        tmp_candles["stoD_over_stoSD"] = tmp_candles["long_stoD"] > tmp_candles["long_stoSD"]

        # INFO: moving_averages
        tmp_candles["long_20SMA"] = self.__calc_sma(tmp_candles.close)
        tmp_candles["long_10EMA"] = self.__calc_ema(tmp_candles.close)

        return tmp_candles[
            ["long_stoD", "long_stoSD", "stoD_over_stoSD", "long_20SMA", "long_10EMA", "time"]
        ].copy()

    # http://www.algo-fx-blog.com/stochastics-python/
    def __calc_stok(self, candles, window_size=5):
        """ストキャスの%Kを計算"""
        stok = (
            (candles.close - candles.low.rolling(window=window_size, center=False).min())
            / (
                candles.high.rolling(window=window_size, center=False).max()
                - candles.low.rolling(window=window_size, center=False).min()
            )
        ) * 100
        return stok

    def __calc_stod(self, candles=None, window_size=5):
        """ストキャスの%Dを計算（%Kの3日SMA）"""
        tmp_candles = candles if candles is not None else self.__base_candles

        stok = self.__calc_stok(candles=tmp_candles, window_size=window_size)
        stod = stok.rolling(window=3, center=False).mean()
        stod.name = "stoD_3"
        return stod

    def __calc_stosd(self, candles=None, window_size=5):
        """ストキャスの%SDを計算（%Dの3日SMA）"""
        tmp_candles = candles if candles is not None else self.__base_candles

        stod = self.__calc_stod(candles=tmp_candles, window_size=window_size)
        stosd = stod.rolling(window=3, center=False).mean()
        stosd.name = "stoSD_3"
        return stosd

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    #                Support / Registance                 #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    def __calc_registance(self):
        high_candles = self.__base_candles.loc[:, "high"]
        regist_points = (
            (pd.Series.rolling(high_candles, window=7).max() == high_candles)
            & (high_candles.shift(1) < high_candles)
            & (high_candles > high_candles.shift(-1))
        )
        regist_plots = self.__generate_sup_regi_plots("regist", regist_points, high_candles)
        return regist_plots

    def __calc_support(self):
        low_candles = self.__base_candles.loc[:, "low"]
        support_points = (
            (pd.Series.rolling(low_candles, window=7).min() == low_candles)
            & (low_candles.shift(1) > low_candles)
            & (low_candles < low_candles.shift(-1))
        )
        support_plots = self.__generate_sup_regi_plots("support", support_points, low_candles)
        return support_plots

    def __generate_sup_regi_plots(self, name, target_points, high_or_low_candles):
        return (
            pd.Series(np.where(target_points, high_or_low_candles, None))
            .fillna(method="ffill")
            .rename(name, inplace=True)
        )
