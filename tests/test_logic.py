from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.logic import _is_open, _is_reasonable_hour, is_reasonable


class TestIsReasonable:
    def test_ok(self):
        with patch("src.logic.datetime") as mock_datetime:
            # NOTE: Friday
            mock_datetime.utcnow.return_value = datetime(2022, 6, 17, 10, 0, tzinfo=timezone.utc)
            assert is_reasonable()

    def test_not_reasonable(self):
        with patch("src.logic.datetime") as mock_datetime:
            # NOTE: Saturday
            mock_datetime.utcnow.return_value = datetime(2022, 6, 18, 10, 0, tzinfo=timezone.utc)
            assert is_reasonable() is False


class TestIsReasonableHour:
    @pytest.mark.parametrize(
        "hour, expected",
        (
            (19, True),  # 4 o'clock (Asia/Tokyo)
            (20, False),
            (21, False),
            (22, True),  # 7 o'clock (Asia/Tokyo)
        ),
    )
    def test_default(self, hour: int, expected: bool):
        result: bool = _is_reasonable_hour(hour)
        assert result is expected


class TestIsOpen:
    @pytest.mark.parametrize(
        "dt, expected",
        (
            (datetime(2022, 6, 13, tzinfo=timezone.utc), True),  # Mon
            (datetime(2022, 6, 14, tzinfo=timezone.utc), True),  # Tue
            (datetime(2022, 6, 15, tzinfo=timezone.utc), True),  # Wed
            (datetime(2022, 6, 16, tzinfo=timezone.utc), True),  # Thu
            (datetime(2022, 6, 17, 22, 59, tzinfo=timezone.utc), True),  # Fri
            (datetime(2022, 6, 19, 19, 00, tzinfo=timezone.utc), True),  # Sun
        ),
    )
    def test_ok(self, dt: datetime, expected: bool):
        result: bool = _is_open(dt)
        assert result is expected

    @pytest.mark.parametrize(
        "dt, expected",
        (
            (datetime(2022, 6, 17, 23, 0, tzinfo=timezone.utc), False),  # Fri
            (datetime(2022, 6, 18, tzinfo=timezone.utc), False),  # Sat
            (datetime(2022, 6, 19, 18, 59, tzinfo=timezone.utc), False),  # Sun
        ),
    )
    def test_closed(self, dt: datetime, expected: bool):
        result: bool = _is_open(dt)
        assert result is expected
