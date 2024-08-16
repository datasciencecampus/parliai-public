"""Functions for handling dates for our reader classes."""

import datetime as dt
import warnings


def list_dates(
    start: None | str | dt.date | dt.datetime = None,
    end: None | str | dt.date | dt.datetime = None,
    window: None | int = None,
    form: str = "%Y-%m-%d",
) -> list[dt.date]:
    """
    Create a continuous list of dates.

    Currently, we support three ways of defining your list:

    1. End-points: start and end dates
    2. Look behind: optional end date and a window
    3. Single date: optional end date

    We do not allow for looking ahead, but that may be introduced in a
    future release.

    Parameters
    ----------
    start : str | dt.date | dt.datetime, optional
        Start of the period. If not specified, this is ignored.
    end : str | dt.date | dt.datetime, optional
        End of the period. If not specified, this is taken as today.
    window : int, optional
        Number of days to look back from `end`. If `start` is specified,
        this is ignored.
    form : str, default="%Y-%m-%d"
        Format of any date strings.

    Returns
    -------
    dates : list[dt.date]
        List of dates.
    """
    start = _format_date(start, form)
    end = _format_date(end, form) or dt.date.today()

    _check_date_parameters(start, end, window)

    window = window or 1
    if isinstance(start, dt.date):
        window = (end - start).days + 1

    return [end - dt.timedelta(days=x) for x in range(window)][::-1]


def _format_date(
    date: None | str | dt.date | dt.datetime, form: str = "%Y-%m-%d"
) -> None | dt.date:
    """
    Format a date-like object into a proper `dt.date`.

    Dates and `None` pass straight through. Meanwhile, date(time)
    strings are converted into datetime objects and then datetime
    objects are turned into dates.

    Parameters
    ----------
    date : None | str | dt.date | dt.datetime
        Date-like object to be converted.
    form : str, default="%Y-%m-%d"
        Format of date string.

    Returns
    -------
    date : None | dt.date
        Formatted date object, or a passed-through `None`.
    """
    if isinstance(date, str):
        date = dt.datetime.strptime(date, form)
    if isinstance(date, dt.datetime):
        date = date.date()

    return date


def _check_date_parameters(
    start: None | dt.date, end: dt.date, window: None | int
) -> None:
    """
    Check the provided date-forming parameters are valid.

    Valid combinations are start and end points, an end and a window, or
    just an end. The checks mostly check for logical consistency - such
    as not having dates in the future.

    Parameters
    ----------
    start : None | dt.date
        Start of period.
    end : dt.date
        End of period.
    window : None | int
        Length of period.

    Warns
    -----
    UserWarning
        If a start and window are provided, we warn the user that the
        window will be ignored.

    Raises
    ------
    ValueError
        If either start or end are in the future, or if start is later
        than end.
    """
    if start and window:
        message = "Ignoring window as start and end dates specified."
        warnings.warn(message, UserWarning)

    if end > dt.date.today():
        raise ValueError("End date must not be in the future.")

    if isinstance(start, dt.date):
        if start > dt.date.today():
            raise ValueError("Start date must not be in the future.")
        if start > end:
            raise ValueError("Start date must not be after end date.")
