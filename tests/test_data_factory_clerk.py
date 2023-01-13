from typing import List

import pandas as pd

from src.data_factory_clerk import mark_entryable_rows

# import pytest


class TestMarkEntryableRows:
    def test_default(self, dummy_trend_candles: List[dict]):
        entry_filters: List[str] = ["in_the_band", "band_expansion"]

        candles: pd.DataFrame = pd.DataFrame.from_dict(dummy_trend_candles, orient="columns")
        candles: pd.DataFrame = candles.assign(in_the_band=False, band_expansion=False)
        candles.loc[10:12, "in_the_band"] = True
        candles.loc[11:, "band_expansion"] = True

        mark_entryable_rows(entry_filters, candles)
        expected: pd.Series = pd.Series(
            [
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                candles.loc[11, "thrust"],
                candles.loc[12, "thrust"],
                None,
                None,
            ],
            name="entryable",
        )

        pd.testing.assert_series_equal(candles["entryable"], expected)
