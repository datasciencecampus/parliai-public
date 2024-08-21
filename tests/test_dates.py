"""Unit tests for the `dates` module."""

import datetime as dt
from unittest import mock

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from parliai_public import dates

from .common import ST_DATES, TODAY


def check_date_list(date_list, start, end):
    """Check the properties of the date list itself."""

    assert isinstance(date_list, list)
    assert all(isinstance(date, dt.date) for date in date_list)
    assert min(date_list) == start
    assert max(date_list) == end

    for i, date in enumerate(date_list[:-1]):
        assert (date_list[i + 1] - date).days == 1


def check_mocked_components(
    formatter, checker, start=None, end=None, window=None
):
    """Check the formatter and checker mocked objects."""

    assert formatter.call_count == 2
    assert formatter.call_args_list == [
        mock.call(limit, "%Y-%m-%d") for limit in (start, end)
    ]

    checker.assert_called_once_with(start, end, window)


@given(
    st.tuples(ST_DATES, ST_DATES).map(sorted),
    st.one_of(st.just(None), st.integers(1, 14)),
)
def test_list_dates_with_endpoints(endpoints, window):
    """
    Check the date lister works for start and end points.

    We also check that the end points are always used even when a window
    is also provided.
    """

    start, end = endpoints

    with (
        mock.patch("parliai_public.dates._format_date") as formatter,
        mock.patch("parliai_public.dates._check_date_parameters") as checker,
    ):
        formatter.side_effect = [start, end]
        date_list = dates.list_dates(start, end, window)

    check_date_list(date_list, start, end)
    check_mocked_components(formatter, checker, start, end, window)


@given(ST_DATES, st.integers(1, 14))
def test_list_dates_with_look_behind(end, window):
    """Check the date lister works for looking back from an endpoint."""

    with (
        mock.patch("parliai_public.dates._format_date") as formatter,
        mock.patch("parliai_public.dates._check_date_parameters") as checker,
    ):
        formatter.side_effect = [None, end]
        date_list = dates.list_dates(end=end, window=window)

    check_date_list(date_list, end - dt.timedelta(window - 1), end)
    check_mocked_components(formatter, checker, end=end, window=window)


@given(ST_DATES)
def test_list_dates_with_single_date(end):
    """Check the date lister works for a single date."""

    with (
        mock.patch("parliai_public.dates._format_date") as formatter,
        mock.patch("parliai_public.dates._check_date_parameters") as checker,
    ):
        formatter.side_effect = [None, end]
        date_list = dates.list_dates(end=end)

    check_date_list(date_list, end, end)
    check_mocked_components(formatter, checker, end=end)


@given(st.one_of(st.just(None), ST_DATES))
def test_format_date_with_none_or_date(date):
    """Check the date formatter does nothing with `None` or a date."""

    assert dates._format_date(date) is date


@given(st.datetimes(min_value=dt.datetime(2000, 1, 1)))
def test_format_date_with_datetime(datetime):
    """Check the date formatter works for datetime objects."""

    assert dates._format_date(datetime) == datetime.date()


@given(ST_DATES, st.sampled_from(("%Y-%m-%d", "%d/%m/%Y", "%a, %d %b %Y")))
def test_format_date_with_date_string(date, form):
    """Check the date formatter works for date strings."""

    assert dates._format_date(date.strftime(form), form) == date


@given(ST_DATES, st.integers(1, 14))
def test_check_date_parameters_warns_for_start_and_window(start, window):
    """Check the date parameter checker warns given start and window."""

    with pytest.warns(UserWarning, match="Ignoring window"):
        dates._check_date_parameters(start, TODAY, window)


@given(st.dates(min_value=TODAY + dt.timedelta(days=1)))
def test_check_date_parameters_raises_for_end_in_the_future(end):
    """Check the date parameter checker raises given a future end."""

    message = "End date must not be in the future."
    with pytest.raises(ValueError, match=message):
        dates._check_date_parameters(None, end, None)


@given(st.dates(min_value=TODAY + dt.timedelta(days=1)))
def test_check_date_parameters_raises_for_start_in_the_future(start):
    """Check the date parameter checker raises given a future start."""

    message = "Start date must not be in the future."
    with pytest.raises(ValueError, match=message):
        dates._check_date_parameters(start, TODAY, None)


@given(st.tuples(ST_DATES, ST_DATES).map(sorted))
def test_check_date_parameters_raises_for_start_after_end(endpoints):
    """Check the checker raises given a start later than its end."""

    end, start = endpoints

    assume(start != end)

    message = "Start date must not be after end date."
    with pytest.raises(ValueError, match=message):
        dates._check_date_parameters(start, end, None)
