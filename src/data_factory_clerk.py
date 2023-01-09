import pandas as pd

from src.analyzer import Analyzer
from src.candle_storage import FXBase
import src.trade_rules.base as base_rules


# -------------------------------------------------------------
# Public methods
# -------------------------------------------------------------
def prepare_indicators() -> pd.DataFrame:
    ana = Analyzer()
    ana.calc_indicators(
        FXBase.get_candles(),
        long_span_candles=FXBase.get_long_span_candles(),
    )
    indicators: pd.DataFrame = ana.get_indicators()

    candles: pd.DataFrame = _merge_long_indicators(ana.get_long_indicators())
    FXBase.set_candles(candles)
    return indicators


# -------------------------------------------------------------
# Private methods
# -------------------------------------------------------------
def _merge_long_indicators(long_indicators: pd.DataFrame) -> pd.DataFrame:
    candles: pd.DataFrame = FXBase.get_candles()
    if "stoD_over_stoSD" in candles.columns:
        return candles

    tmp_df = candles.merge(long_indicators, on="time", how="left")
    # tmp_df['long_stoD'].fillna(method='ffill', inplace=True)
    # tmp_df['long_stoSD'].fillna(method='ffill', inplace=True)
    tmp_df.loc[:, "stoD_over_stoSD"] = (
        tmp_df["stoD_over_stoSD"].fillna(method="ffill").fillna(False)
    )

    tmp_df["long_20SMA"].fillna(method="ffill", inplace=True)
    tmp_df["long_10EMA"].fillna(method="ffill", inplace=True)
    long_ma = (
        tmp_df[["long_10EMA", "long_20SMA"]]
        .copy()
        .rename(columns={"long_10EMA": "10EMA", "long_20SMA": "20SMA"})
    )
    tmp_df["long_trend"] = base_rules.generate_trend_column(long_ma, candles.close)

    return tmp_df
