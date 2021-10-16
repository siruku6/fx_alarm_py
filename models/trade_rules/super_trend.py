from typing import List, Tuple
import numpy as np
import pandas as pd


class SuperTrend:
    RELATED_INDICATOR: List[str] = ['st_upper_band', 'st_lower_band', 'ema_200']

    def __init__(self):
        pass

    # OPTIMIZE: too slow !!!
    def generate_base_indicators(self, df, look_back: int = 10, multiplier: int = 3) -> pd.DataFrame:
        '''
        Generate upper and lower band for Super Trend
        '''
        atr: pd.Series = self.__generate_average_true_range(df, look_back)

        # Temporary both bands and trend
        hl_avg: pd.Series = (df['high'] + df['low']) / 2
        df['st_upper_band'] = (hl_avg + multiplier * atr)
        df['st_lower_band'] = (hl_avg - multiplier * atr)
        df['is_up_trend'] = np.full(len(df), False)

        st_upper_band, st_lower_band, is_up_trend = self.__adjust_bands_and_trend(df)
        st_upper_band, st_lower_band = self.__erase_unnecessary_band_points(st_upper_band, st_lower_band, is_up_trend)
        ema_200: pd.Series = df['close'].ewm(span=200).mean()
        return pd.concat([st_upper_band, st_lower_band, ema_200], axis=1, join='inner')

    def __generate_average_true_range(self, df: pd.DataFrame, look_back: int = 10) -> pd.Series:
        '''
        ATR (Average True Raneg)
            True Range is the biggest in
                (high - low)
                (high - previous close)
                (low - previous close)
            ATR is the moving average of True Range.
        '''
        tr1: pd.Series = df['high'] - df['low']
        tr2: pd.Series = abs(df['high'] - df['close'].shift(1))
        tr3: pd.Series = abs(df['low'] - df['close'].shift(1))
        tr: pd.Series = pd.concat([tr1, tr2, tr3], axis=1, join='inner').max(axis=1)
        atr: pd.Series = tr.ewm(look_back).mean()
        return atr

    def __adjust_bands_and_trend(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        tmp_df = df[['close', 'st_upper_band', 'st_lower_band', 'is_up_trend']].copy()

        len_df: int = len(tmp_df.index)
        for i in range(1, len_df):
            current: int = i
            previous: int = i - 1

            # print(i, st_upper_band.index.values)
            if tmp_df['close'][current] > tmp_df['st_upper_band'][previous]:  # 現在の終値が前のバンド上限を上回っていた場合は上昇トレンドと判定
                tmp_df['is_up_trend'][current] = True
            elif tmp_df['close'][current] < tmp_df['st_lower_band'][previous]:  # 現在の終値が前のバンド下限を下回っていた場合は下降トレンドと判定
                tmp_df['is_up_trend'][current] = False
            else:
                tmp_df['is_up_trend'][current] = tmp_df['is_up_trend'][previous]

                if tmp_df['is_up_trend'][current] and tmp_df['st_lower_band'][current] < tmp_df['st_lower_band'][previous]:  # 上昇トレンドかつ現在のバンド下限が前のバンド下限を下回っていた場合は前のバンド下限が継続
                    tmp_df['st_lower_band'][current] = tmp_df['st_lower_band'][previous]
                elif (not tmp_df['is_up_trend'][current]) and tmp_df['st_upper_band'][current] > tmp_df['st_upper_band'][previous]:  # 下降トレンドかつ現在のバンド上限が前のバンド上限を上回っていた場合は前のバンド上限が継続
                    tmp_df['st_upper_band'][current] = tmp_df['st_upper_band'][previous]

        return tmp_df['st_upper_band'], tmp_df['st_lower_band'], tmp_df['is_up_trend']

    def __erase_unnecessary_band_points(self, st_upper_band, st_lower_band, is_up_trend) -> Tuple[pd.Series, pd.Series]:
        # 上昇トレンドの場合はバンド上限を消し、下降トレンドの場合はバンド下限を消す
        for i in range(len(st_upper_band)):
            if is_up_trend[i]:
                st_upper_band[i] = np.nan
            elif not is_up_trend[i]:
                st_lower_band[i] = np.nan

        return st_upper_band, st_lower_band
