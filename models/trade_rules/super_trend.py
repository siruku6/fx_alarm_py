from typing import List, Tuple
import numpy as np
import pandas as pd


class SuperTrend:
    RELATED_INDICATOR: List[str] = ['st_upper_band', 'st_lower_band', 'ema_200']

    def __init__(self):
        pass

    def generate_base_indicators(self, df: pd.DataFrame, window_size: int = 10, multiplier: int = 3) -> pd.DataFrame:
        '''
        Generate upper and lower band for Super Trend

        Parameters
        ----------
        df : pd.DataFrame
            Index:
                Any
            Columns:
                Name: high,  dtype: float64 (required)
                Name: low,   dtype: float64 (required)
                Name: close, dtype: float64 (required)

        Returns
        -------
        pd.DataFrame
        '''

        atr: pd.Series = self.__generate_atr(df[['high', 'low', 'close']], window_size)

        # Temporary both bands and trend
        hl_avg: pd.Series = (df['high'] + df['low']) / 2
        df['st_upper_band'] = (hl_avg + multiplier * atr)
        df['st_lower_band'] = (hl_avg - multiplier * atr)
        df['is_up_trend'] = np.full(len(df), False)

        tmp_df: pd.DataFrame = self.__adjust_bands_and_trend(df)
        bands: pd.DataFrame = self.__erase_unnecessary_band(tmp_df)
        ema_200: pd.Series = df['close'].ewm(span=200).mean().rename('ema_200')
        return pd.concat([bands, ema_200], axis=1, join='inner')

    def __generate_atr(self, df: pd.DataFrame, window_size: int = 10) -> pd.Series:
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
        atr: pd.Series = tr.ewm(window_size).mean()
        return atr

    def __adjust_bands_and_trend(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        tmp_df = df[['close', 'st_upper_band', 'st_lower_band', 'is_up_trend']].copy()
        tmp_dict = tmp_df.to_dict(orient='records')

        for current, row in enumerate(tmp_dict):
            previous: int = current - 1

            if row['close'] > tmp_dict[previous]['st_upper_band']:
                row['is_up_trend'] = True  # change to up trend
            elif row['close'] < tmp_dict[previous]['st_lower_band']:
                row['is_up_trend'] = False  # change to down trend
            else:
                row['is_up_trend'] = tmp_dict[previous]['is_up_trend']

                # At up trend, if lower_band is lower than previous lower_band, previous lower_band continues
                if row['is_up_trend'] \
                        and row['st_lower_band'] < tmp_dict[previous]['st_lower_band']:
                    row['st_lower_band'] = tmp_dict[previous]['st_lower_band']
                # At down trend, if upper_band is upper than previous upper_band, previous upper_band continues
                elif (not row['is_up_trend']) \
                        and row['st_upper_band'] > tmp_dict[previous]['st_upper_band']:
                    row['st_upper_band'] = tmp_dict[previous]['st_upper_band']

        return pd.DataFrame.from_dict(tmp_dict)

    def __erase_unnecessary_band(self, tmp_df) -> pd.DataFrame:
        '''
        Erase upper_band at up trend, and erase lower_band at down trend
        '''
        result: pd.DataFrame = tmp_df.copy()
        result.loc[result['is_up_trend'], 'st_upper_band'] = np.nan
        result.loc[~result['is_up_trend'], 'st_lower_band'] = np.nan

        return result
