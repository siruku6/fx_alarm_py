from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

import src.trade_rules.stoploss as stoploss_strategy


# - - - - - - - - - - - - - - - - - - - - - - - -
#                Driver of logics
# - - - - - - - - - - - - - - - - - - - - - - - -
def generate_repulsion_column(candles: pd.DataFrame, ema: pd.Series) -> np.ndarray:
    method_thrust_checker = np.frompyfunc(repulsion_exist, 6, 1)
    result: np.ndarray = method_thrust_checker(
        candles["trend"],
        ema.shift(1),
        candles["high"].shift(2),
        candles["high"].shift(1),
        candles["low"].shift(2),
        candles["low"].shift(1),
    )
    return result


def generate_entryable_prices(candles: pd.DataFrame, spread: float) -> np.ndarray:
    """
    Generate possible prices assuming that entries are done

    Parameters
    ----------
    candles : pd.DataFrame
        Index:
            Any
        Columns:
            Name: open,      dtype: float64 (required)
            Name: entryable, dtype: object  (required)
    spread : float

    Returns
    -------
    np.ndarray
    """
    result: np.ndarray = np.full_like(candles["open"], np.nan, dtype=np.float64)
    long_index: pd.Series = candles["entryable"] == "long"
    short_index: pd.Series = candles["entryable"] == "short"

    # TODO: 実際には open で entry することはなかなかできない
    result[long_index] = candles.loc[long_index, "open"] + spread
    result[short_index] = candles.loc[short_index, "open"]
    return result


def commit_positions_by_loop(factor_dicts: List[dict]) -> pd.DataFrame:
    """
    Parameters
    ----------
    factor_dicts : list of dict
        keys => [
            'open', 'high', 'low', 'close', 'time',
            'entryable', 'entryable_price', 'stoD_over_stoSD',
            'sigma*2_band', 'sigma*-2_band', 'stoD_3', 'stoSD_3', 'support', 'regist'
        ]
    """
    loop_objects = factor_dicts  # コピー変数: loop_objects への変更は factor_dicts にも及ぶ
    entry_direction = factor_dicts[0]["entryable"]  # 'long', 'short' or nan

    for index, one_frame in enumerate(loop_objects):
        entry_direction = __trade_routine(entry_direction, factor_dicts, index, one_frame)

    return pd.DataFrame.from_dict(factor_dicts)[
        ["entryable_price", "position", "exitable_price", "exit_reason", "possible_stoploss"]
    ]


def __trade_routine(
    entry_direction: str,
    factor_dicts: List[dict],
    index: int,
    one_frame: pd.Series,
) -> str:
    # entry 中でなければ continue
    if entry_direction not in ("long", "short"):
        entry_direction = __reset_next_position(factor_dicts, index, entry_direction)
        return entry_direction

    previous_frame = factor_dicts[index - 1]
    one_frame["possible_stoploss"] = stoploss_strategy.support_or_registance(
        entry_direction, previous_frame["support"], previous_frame["regist"]
    )

    exit_price, exit_type, exit_reason = __decide_exit_price(
        entry_direction, one_frame, previous_frame=previous_frame
    )
    # exit する理由がなければ continue
    if exit_price is None:
        return entry_direction

    # exit した場合のみここに到達する
    one_frame.update(exitable_price=exit_price, position=exit_type, exit_reason=exit_reason)
    __tmp_delay_irregular_entry(factor_dicts, index)  # HACK: 暫定措置
    entry_direction = __reset_next_position(factor_dicts, index, entry_direction)
    return entry_direction


def __reset_next_position(factor_dicts: List[dict], index: int, entry_direction: str) -> str:
    if factor_dicts[-1]["time"] == factor_dicts[index]["time"]:
        return "It is the last"

    factor_dicts[index + 1]["position"] = entry_direction = factor_dicts[index + 1]["entryable"]
    return entry_direction


def __decide_exit_price(
    entry_direction: str, one_frame: pd.Series, previous_frame: pd.Series
) -> Tuple[float, str, str]:
    if entry_direction == "long":
        # edge_price = one_frame['high']
        exit_type = "sell_exit"
    elif entry_direction == "short":
        # edge_price = one_frame['low']
        exit_type = "buy_exit"

    exit_price: Optional[float]
    exit_reason: Optional[str]
    exit_price, exit_reason = __exit_by_stoploss(one_frame)
    if exit_price is not None:
        return exit_price, exit_type, exit_reason  # type: ignore

    # if is_exitable_by_bollinger(edge_price, one_frame['sigma*2_band'], one_frame['sigma*-2_band']):
    #     exit_price = one_frame['sigma*2_band'] if entry_direction == 'long' else one_frame['sigma*-2_band']
    if is_exitable(entry_direction, one_frame, previous_frame):
        exit_price = one_frame["open"]  # 'low'] if entry_direction == 'long' else one_frame['high']
        exit_reason = "Stochastics of both long and target-span are crossed"
    return exit_price, exit_type, exit_reason  # type: ignore


def __exit_by_stoploss(one_frame: pd.Series) -> Tuple[Optional[float], Optional[str]]:
    """stoploss による exit の判定"""
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None

    if one_frame["low"] < one_frame["possible_stoploss"] < one_frame["high"]:
        exit_price = one_frame["possible_stoploss"]
        exit_reason = "Hit stoploss"
    return exit_price, exit_reason


def __tmp_delay_irregular_entry(factor_dicts: List[dict], index: int) -> None:
    one_frame = factor_dicts[index]
    # HACK: long なのに buy_exit などの逆行減少があるときは entryを消しておく (暫定措置)
    long_buy_exit = one_frame["entryable"] == "long" and one_frame["position"] == "buy_exit"
    short_sell_exit = one_frame["entryable"] == "short" and one_frame["position"] == "sell_exit"

    if long_buy_exit or short_sell_exit:
        # delay entry
        factor_dicts[index + 1].update(
            entryable=one_frame["entryable"], entryable_price=one_frame["entryable_price"]
        )
        one_frame.update(entryable_price=None)


# - - - - - - - - - - - - - - - - - - - - - - - -
#                  Trade Logics
# - - - - - - - - - - - - - - - - - - - - - - - -
def repulsion_exist(
    trend: str,
    previous_ema: float,
    two_before_high: float,
    previous_high: float,
    two_before_low: float,
    previous_low: float,
) -> Optional[str]:
    """
    "long": the price surpass 10ema in bull trend
    "short": the price underperform 10ema in bear trend
    1, 2本前の足から見て、trend方向にcrossしていればentry可のsignを出す
    """
    # OPTIMIZE: rising, falling は試験的に削除したが、検証が必要
    #   => 他の条件が整っていさえすれば、早いタイミングでエントリーするようになった
    if trend == "bull":
        # rising = two_before_high < previous_high
        touch_ema = two_before_low < previous_ema or previous_low < previous_ema
        leave_from_ema = previous_ema < previous_high
        # if rising and leave_from_ema and touch_ema:
        if leave_from_ema and touch_ema:
            return "long"
    elif trend == "bear":
        # falling = two_before_low > previous_low
        touch_ema = previous_ema < two_before_high or previous_ema < previous_high
        leave_from_ema = previous_ema > previous_low
        # if falling and leave_from_ema and touch_ema:
        if leave_from_ema and touch_ema:
            return "short"
    return None


def is_exitable_by_bollinger(
    spot_price: float,
    plus_2sigma: float,
    minus_2sigma: float,
) -> bool:
    bollinger_is_touched: bool = spot_price < minus_2sigma or plus_2sigma < spot_price

    if bollinger_is_touched:
        return True
    else:
        return False


def is_exitable(entry_direction: str, one_frame: pd.Series, previous_frame: pd.Series) -> bool:
    result: bool = (
        _exitable_by_long_stoccross(
            entry_direction,
            long_stod_greater=one_frame["stoD_over_stoSD"],
        )
        and _exitable_by_stoccross(
            entry_direction,
            stod=one_frame["stoD_3"],
            stosd=one_frame["stoSD_3"],
        )
        and _exitable_by_stoccross(
            entry_direction,
            stod=previous_frame["stoD_3"],
            stosd=previous_frame["stoSD_3"],
        )
    )
    return result


# INFO: stod, stosd は、直前の足の確定値を使う
#   その方が、forward test に近い結果を出せるため
def _exitable_by_stoccross(position_type: str, stod: float, stosd: float) -> bool:
    stoc_crossed: bool = ((position_type == "long") and (stod < stosd)) or (
        (position_type == "short") and (stod > stosd)
    )

    if stoc_crossed:
        return True
    else:
        return False


def _exitable_by_long_stoccross(entry_direction: str, long_stod_greater: bool) -> bool:
    stoc_crossed: bool = ((entry_direction == "long") and not long_stod_greater) or (
        (entry_direction == "short") and long_stod_greater
    )

    if stoc_crossed:
        return True
    else:
        return False
