import models.trade_rules.base as base
import numpy as np
import pandas as pd

def test_generate_stoc_allows_column():
    indicators = pd.DataFrame.from_dict(
        {
            'no_trend': [None, 20, 30, False],
            'long_no_entry': ['bull', 20, 30, False],
            'long_entry': ['bull', 50, 30, True],
            'long_high_entry': ['bull', 85, 90, True],
            'short_no_entry': ['bear', 85, 30, False],
            'short_entry': ['bear', 70, 80, True],
            'short_high_entry': ['bear', 15, 5, True],
        }, columns=['trend', 'stoD_3', 'stoSD_3', 'expected_result'], orient='index'
    ).astype(
        {'trend': str, 'stoD_3': 'float32', 'stoSD_3': 'float32', 'expected_result': 'object'}
    )

    result = base.generate_stoc_allows_column(indicators, indicators['trend'])
    assert np.all(result == indicators['expected_result'])
