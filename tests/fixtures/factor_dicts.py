import numpy as np

DUMMY_FACTOR_DICTS = [
    {
        'open': 129.15, 'high': 130.461, 'low': 129.025, 'close': 130.204,
        'time': '2020-03-24 09:00:00', 'entryable': np.nan, 'entryable_price': np.nan,
        'stoD_over_stoSD': True,
        'band_+2σ': 130.8310671150085, 'band_-2σ': 126.1347328849913, 'stoD_3': 80.85504506413038, 'stoSD_3': 65.35383457466865,
        'support': 127.36, 'regist': 132.053
    }, {
        'open': 130.20600000000002, 'high': 131.439, 'low': 130.15200000000002, 'close': 131.124,
        'time': '2020-03-24 13:00:00', 'entryable': np.nan, 'entryable_price': np.nan,
        'stoD_over_stoSD': True,
        'band_+2σ': 130.99580488302018, 'band_-2σ': 126.51399511697952, 'stoD_3': 92.73154616606742,
        'stoSD_3': 79.13209879939662, 'support': 127.36, 'regist': 131.439
    }, {
        'open': 131.126, 'high': 131.296, 'low': 130.536, 'close': 130.79,
        'time': '2020-03-24 17:00:00', 'entryable': 'long', 'entryable_price': 131.14000000000001,
        'stoD_over_stoSD': True,
        'band_+2σ': 131.26188872967134, 'band_-2σ': 126.56531127032838, 'stoD_3': 87.91728966463067, 'stoSD_3': 87.16796029827616,
        'support': 127.36, 'regist': 131.439
    }, {
        'open': 130.79, 'high': 131.30700000000002, 'low': 130.428, 'close': 130.615,
        'time': '2020-03-24 21:00:00', 'entryable': None, 'entryable_price': np.nan,
        'stoD_over_stoSD': True,
        'band_+2σ': 131.47181141538556, 'band_-2σ': 126.60758858461418, 'stoD_3': 82.70913428536397, 'stoSD_3': 87.78599003868736,
        'support': 127.36, 'regist': 131.439
    },
    {'open': 133.476, 'high': 133.6, 'low': 133.22899999999998, 'close': 133.378, 'time': '2020-04-01 01:00:00', 'entryable': np.nan, 'entryable_price': np.nan, 'stoD_over_stoSD': True, 'band_+2σ': 134.5569549058887, 'band_-2σ': 132.55964509411115, 'stoD_3': 17.272227088875955, 'stoSD_3': 30.74676026942556, 'support': 129.865, 'regist': 134.627},
    {'open': 133.38, 'high': 133.454, 'low': 132.575, 'close': 132.952, 'time': '2020-04-01 05:00:00', 'entryable': np.nan, 'entryable_price': np.nan, 'stoD_over_stoSD': True, 'band_+2σ': 134.5439096983719, 'band_-2σ': 132.586490301628, 'stoD_3': 15.877894441491067, 'stoSD_3': 19.491009992322088, 'support': 132.575, 'regist': 134.627},
    {'open': 132.95, 'high': 133.34, 'low': 132.76, 'close': 132.998, 'time': '2020-04-01 09:00:00', 'entryable': np.nan, 'entryable_price': np.nan, 'stoD_over_stoSD': True, 'band_+2σ': 134.5197091225411, 'band_-2σ': 132.63449087745875, 'stoD_3': 19.408905301270117, 'stoSD_3': 17.519675610545722, 'support': 132.575, 'regist': 134.627},
    {'open': 133.0, 'high': 133.484, 'low': 132.589, 'close': 132.73, 'time': '2020-04-01 13:00:00', 'entryable': np.nan, 'entryable_price': np.nan, 'stoD_over_stoSD': True, 'band_+2σ': 134.4720024255887, 'band_-2σ': 132.70899757441117, 'stoD_3': 19.914673207606445, 'stoSD_3': 18.400490983455885, 'support': 132.575, 'regist': 134.627},
    # index=8
    {'open': 132.733, 'high': 133.085, 'low': 132.489, 'close': 132.597, 'time': '2020-04-01 17:00:00', 'entryable': 'short', 'entryable_price': 132.733, 'stoD_over_stoSD': True, 'band_+2σ': 134.53588958972944, 'band_-2σ': 132.5775104102704, 'stoD_3': 17.03089067730669, 'stoSD_3': 18.784823062061093, 'support': 132.489, 'regist': 134.627},
    {'open': 132.597, 'high': 133.278, 'low': 132.541, 'close': 133.09, 'time': '2020-04-01 21:00:00', 'entryable': np.nan, 'entryable_price': np.nan, 'stoD_over_stoSD': True, 'band_+2σ': 134.48132556739353, 'band_-2σ': 132.53677443260636, 'stoD_3': 27.644299834277664, 'stoSD_3': 21.529954573063605, 'support': 132.489, 'regist': 134.627},
    {'open': 133.088, 'high': 133.274, 'low': 133.006, 'close': 133.164, 'time': '2020-04-02 01:00:00', 'entryable': np.nan, 'entryable_price': np.nan, 'stoD_over_stoSD': True, 'band_+2σ': 134.33940701296592, 'band_-2σ': 132.5568929870339, 'stoD_3': 45.98739270911952, 'stoSD_3': 30.220861073567963, 'support': 132.489, 'regist': 134.627},
    {'open': 133.162, 'high': 133.326, 'low': 132.984, 'close': 133.32399999999998, 'time': '2020-04-02 05:00:00', 'entryable': np.nan, 'entryable_price': np.nan, 'stoD_over_stoSD': True, 'band_+2σ': 134.31419159604062, 'band_-2σ': 132.54460840395924, 'stoD_3': 70.72026800669856, 'stoSD_3': 48.11732018336525, 'support': 132.489, 'regist': 134.627},
    {'open': 133.326, 'high': 133.894, 'low': 132.873, 'close': 133.08100000000002, 'time': '2020-04-02 09:00:00', 'entryable': np.nan, 'entryable_price': np.nan, 'stoD_over_stoSD': True, 'band_+2σ': 134.3127150074638, 'band_-2σ': 132.5160849925361, 'stoD_3': 64.63134176219056, 'stoSD_3': 60.44633415933621, 'support': 132.489, 'regist': 133.894},
    {'open': 133.079, 'high': 133.8, 'low': 132.548, 'close': 133.507, 'time': '2020-04-02 13:00:00', 'entryable': np.nan, 'entryable_price': np.nan, 'stoD_over_stoSD': True, 'band_+2σ': 134.32176880002058, 'band_-2σ': 132.52553119997927, 'stoD_3': 65.81724169793802, 'stoSD_3': 67.05628382227572, 'support': 132.489, 'regist': 133.894}
]
