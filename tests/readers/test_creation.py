"""Unit tests for instantiation methods of our readers."""

import datetime as dt
from unittest import mock

from hypothesis import HealthCheck, given, provisional, settings
from hypothesis import strategies as st

from parliai_public.readers import Debates, WrittenAnswers

from ..common import ST_DATES, ST_FREE_TEXT, TODAY, ToyReader, where_what

ST_OPTIONAL_STRINGS = st.one_of((st.just(None), ST_FREE_TEXT))
YESTERDAY = TODAY - dt.timedelta(days=1)


@settings(suppress_health_check=(HealthCheck.too_slow,))
@given(
    st.sampled_from((ToyReader, Debates, WrittenAnswers)),
    st.lists(provisional.urls(), max_size=5),
    st.one_of((st.just(None), st.lists(ST_FREE_TEXT, max_size=5))),
    st.one_of(st.just(None), st.lists(ST_DATES, min_size=1, max_size=5)),
    ST_FREE_TEXT,
    ST_OPTIONAL_STRINGS,
)
def test_init(reader_class, urls, terms, dates, outdir, prompt):
    """Test instantiation occurs correctly."""

    where, what = where_what(reader_class)
    if reader_class is WrittenAnswers:
        urls = reader_class._supported_urls

    config = {
        "prompt": "",
        "llm_name": "gemma",
    }
    with mock.patch(f"{where}._load_config") as load:
        load.return_value = config
        reader = reader_class(urls, terms, dates, outdir, prompt)

    default_terms = ["Office for National Statistics", "ONS"]
    assert isinstance(reader, what)
    assert reader.urls == urls
    assert reader.terms == default_terms if not terms else terms
    assert reader.dates == [YESTERDAY] if dates is None else dates
    assert reader.outdir == outdir
    assert reader.prompt == ("" if prompt is None else prompt)
    assert reader.llm_name == "gemma"

    load.assert_called_once_with()


@given(
    st.sampled_from((ToyReader, Debates, WrittenAnswers)),
    ST_OPTIONAL_STRINGS,
    st.lists(provisional.urls(), max_size=5),
    st.lists(ST_FREE_TEXT, max_size=5),
    ST_FREE_TEXT,
)
def test_from_toml_no_dates(reader_class, path, urls, terms, text):
    """
    Test that an instance can be made from a configuration file.

    In this test, we do not configure any of the date parameters, so
    every reader instance should have the same `dates` attribute:
    yesterday.
    """

    where, what = where_what(reader_class)
    if reader_class is WrittenAnswers:
        urls = reader_class._supported_urls

    with (
        mock.patch(f"{where}._load_config") as loader,
        mock.patch("parliai_public.dates.list_dates") as lister,
    ):
        loader.return_value = {
            "urls": urls,
            "terms": terms,
            "outdir": text,
            "prompt": text,
            "llm_name": "gemma",
        }
        reader = reader_class.from_toml(path)

    assert isinstance(reader, what)
    assert reader.dates == [YESTERDAY]
    assert loader.return_value["dates"] is None
    assert loader.call_count == 2
    assert loader.call_args_list == [mock.call(path), mock.call()]

    lister.assert_not_called()


@given(
    st.sampled_from((ToyReader, Debates, WrittenAnswers)),
    ST_DATES.map(dt.date.isoformat),
)
def test_from_toml_with_start(reader_class, start):
    """
    Check the config constructor works with a start date.

    The actual date list construction is mocked here.
    """
    where, what = where_what(reader_class)

    with (
        mock.patch(f"{where}._load_config") as loader,
        mock.patch("parliai_public.dates.list_dates") as lister,
    ):
        loader.return_value = {
            "urls": [],
            "start": start,
            "prompt": "",
            "llm_name": "gemma",
        }
        lister.return_value = ["dates"]
        reader = reader_class.from_toml()

    assert isinstance(reader, what)
    assert reader.dates == ["dates"]

    assert "start" not in loader.return_value
    assert loader.return_value.get("dates") == ["dates"]

    lister.assert_called_once_with(start, None, None, "%Y-%m-%d")


@given(
    st.sampled_from((ToyReader, Debates, WrittenAnswers)),
    ST_DATES.map(dt.date.isoformat),
)
def test_from_toml_with_end(reader_class, end):
    """Check the config constructor works with an end date."""

    where, what = where_what(reader_class)

    with (
        mock.patch(f"{where}._load_config") as loader,
        mock.patch("parliai_public.dates.list_dates") as lister,
    ):
        loader.return_value = {
            "urls": [],
            "end": end,
            "prompt": "",
            "llm_name": "gemma",
        }
        lister.return_value = ["dates"]
        reader = reader_class.from_toml()

    assert isinstance(reader, what)
    assert reader.dates == ["dates"]

    assert "end" not in loader.return_value
    assert loader.return_value.get("dates") == ["dates"]

    lister.assert_called_once_with(None, end, None, "%Y-%m-%d")


@given(
    st.sampled_from((ToyReader, Debates, WrittenAnswers)),
    st.tuples(ST_DATES, ST_DATES).map(
        lambda dates: sorted(map(dt.date.isoformat, dates))
    ),
)
def test_from_toml_with_endpoints(reader_class, endpoints):
    """Check the config constructor works with two endpoints."""

    where, what = where_what(reader_class)
    start, end = endpoints

    with (
        mock.patch(f"{where}._load_config") as loader,
        mock.patch("parliai_public.dates.list_dates") as lister,
    ):
        loader.return_value = {
            "urls": [],
            "start": start,
            "end": end,
            "prompt": "",
            "llm_name": "gemma",
        }
        lister.return_value = ["dates"]
        reader = reader_class.from_toml()

    assert isinstance(reader, what)
    assert reader.dates == ["dates"]

    assert "start" not in loader.return_value
    assert "end" not in loader.return_value
    assert loader.return_value.get("dates") == ["dates"]

    lister.assert_called_once_with(start, end, None, "%Y-%m-%d")


@given(
    st.sampled_from((ToyReader, Debates, WrittenAnswers)),
    st.integers(1, 14),
)
def test_from_toml_with_window(reader_class, window):
    """Check the config constructor works with a window."""

    where, what = where_what(reader_class)

    with (
        mock.patch(f"{where}._load_config") as loader,
        mock.patch("parliai_public.dates.list_dates") as lister,
    ):
        loader.return_value = {
            "urls": [],
            "window": window,
            "prompt": "",
            "llm_name": "gemma",
        }
        lister.return_value = ["dates"]
        reader = reader_class.from_toml()

    assert isinstance(reader, what)
    assert reader.dates == ["dates"]

    assert "end" not in loader.return_value
    assert loader.return_value.get("dates") == ["dates"]

    lister.assert_called_once_with(None, None, window, "%Y-%m-%d")


@given(
    st.sampled_from((ToyReader, Debates, WrittenAnswers)),
    ST_DATES.map(dt.date.isoformat),
    st.integers(1, 14),
)
def test_from_toml_with_end_and_window(reader_class, end, window):
    """Check the config constructor works with an end and a window."""

    where, what = where_what(reader_class)

    with (
        mock.patch(f"{where}._load_config") as loader,
        mock.patch("parliai_public.dates.list_dates") as lister,
    ):
        loader.return_value = {
            "urls": [],
            "end": end,
            "window": window,
            "prompt": "",
            "llm_name": "gemma",
        }
        lister.return_value = ["dates"]
        reader = reader_class.from_toml()

    assert isinstance(reader, what)
    assert reader.dates == ["dates"]

    assert "end" not in loader.return_value
    assert "window" not in loader.return_value
    assert loader.return_value.get("dates") == ["dates"]

    lister.assert_called_once_with(None, end, window, "%Y-%m-%d")
