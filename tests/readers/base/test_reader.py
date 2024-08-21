"""Unit tests for the `base` module."""

import datetime as dt
import json
import os
import pathlib
import re
import shutil
import string
import warnings
from unittest import mock

import pytest
from bs4 import BeautifulSoup
from hypothesis import example, given, provisional, settings
from hypothesis import strategies as st
from langchain.docstore.document import Document

from ...common import (
    GEMMA_PREAMBLES,
    MODEL_NAMES,
    ST_DATES,
    ST_FREE_TEXT,
    ToyReader,
    default_llm,
)
from .strategies import st_chunks_contains_responses, st_terms_and_texts

settings.register_profile("ci", deadline=None)
settings.load_profile("ci")


@given(ST_FREE_TEXT, st.dictionaries(ST_FREE_TEXT, ST_FREE_TEXT))
def test_load_config_from_path(path, config):
    """Test a dictionary can be "loaded" from a given path."""

    with mock.patch("parliai_public.readers.base.toml.load") as load:
        load.return_value = config
        loaded = ToyReader._load_config(path)

    assert isinstance(loaded, dict)
    assert loaded == config

    load.assert_called_once_with(path)


def test_load_config_default():
    """Test that the default config file can be loaded correctly."""

    # TODO: keywords hardcoded not ideal for flexible keywords
    expected = {
        "urls": [],
        "keywords": ["Office for National Statistics", "ONS"],
        "prompt": "",
        "outdir": "",
        "llm_name": "",
    }
    config = ToyReader._load_config()

    assert config == expected


@given(st_terms_and_texts())
@example((["ONS"], "Have you heard of the ONS?"))
@example((["ONS"], "ONS numbers are reliable."))
@example((["ONS"], "Mentions of other departments are like onions."))
def test_check_contains_terms(term_text):
    """Check the term checker works as it should."""

    term, text = term_text

    reader = ToyReader(urls=[], terms=term)
    contains = reader.check_contains_terms(text)

    if term:
        assert (term[0] in text) is contains
    else:
        assert contains is False


@given(
    st.lists(ST_DATES, min_size=1, max_size=14),
    st.sampled_from(("gemma", "chat-bison")),
)
def test_make_outdir(date_list, llm_name):
    """Check the output directory builder works as it should."""

    where = os.path.join("~", ".parliai_public", "test")
    tmpdir = pathlib.Path(where).expanduser()
    tmpdir.mkdir(parents=True, exist_ok=True)

    reader = ToyReader(
        urls=[], dates=date_list, outdir=tmpdir, llm_name=llm_name
    )

    with mock.patch(
        "parliai_public.readers.base.BaseReader._tag_outdir"
    ) as determiner:
        determiner.side_effect = lambda x: x
        reader.make_outdir()

    outdir, *others = list(tmpdir.glob("**/*"))
    start, end, *llm_parts = outdir.name.split(".")

    assert others == []
    assert dt.datetime.strptime(start, "%Y-%m-%d").date() == min(date_list)
    assert dt.datetime.strptime(end, "%Y-%m-%d").date() == max(date_list)
    assert ".".join(llm_parts) == llm_name

    shutil.rmtree(tmpdir)


@given(
    st.booleans(),
    (
        st.lists(st.booleans())
        .map(lambda bools: [*sorted(bools, reverse=True), False])
        .map(lambda bools: bools[: bools.index(False) + 1])
    ),
)
def test_tag_outdir(exist, exists):
    """Check the out directory tagger works."""

    reader = ToyReader(urls=[])

    with mock.patch(
        "parliai_public.readers.base.os.path.exists"
    ) as exists_checker:
        exists_checker.side_effect = [exist, *exists]
        outdir = reader._tag_outdir("out")

    out, *tags = outdir.split(".")
    assert out == "out"

    if exist:
        tag = tags[0]
        assert tags == [tag]
        assert tag == str(exists.index(False) + 1)
    else:
        assert not tags


@given(provisional.urls(), ST_FREE_TEXT, st.booleans())
def test_get_with_check(url, content, contains):
    """Test the soup getter method."""

    reader = ToyReader(urls=[])

    page = mock.MagicMock()
    page.content = content
    with (
        mock.patch("parliai_public.readers.base.requests.get") as get,
        mock.patch(
            "parliai_public.readers.base.BaseReader.check_contains_terms"
        ) as check,
    ):
        get.return_value = page
        check.return_value = contains
        soup = reader.get(url)

    if contains is True:
        assert isinstance(soup, BeautifulSoup)
        assert soup.get_text() == content
    else:
        assert soup is None

    get.assert_called_once_with(url)
    check.assert_called_once_with(content)


@given(provisional.urls(), ST_FREE_TEXT)
def test_get_without_check(url, content):
    """Test the soup getter method when ignoring the checker."""

    reader = ToyReader(urls=[])

    page = mock.MagicMock()
    page.content = content
    with (
        mock.patch("parliai_public.readers.base.requests.get") as get,
        mock.patch(
            "parliai_public.readers.base.BaseReader.check_contains_terms"
        ) as check,
    ):
        get.return_value = page
        soup = reader.get(url, check=False)

    assert isinstance(soup, BeautifulSoup)
    assert soup.get_text() == content

    get.assert_called_once_with(url)
    check.assert_not_called()


@given(provisional.urls(), st.sampled_from((None, "soup")))
def test_read(url, soup):
    """
    Test the logic of the generic read method.

    Since the method relies on two abstract methods, we mock them here,
    and just test that the correct order of events passes.
    """

    reader = ToyReader(urls=[])

    with (
        mock.patch("parliai_public.readers.base.BaseReader.get") as get,
        mock.patch(__name__ + ".ToyReader._read_metadata") as read_metadata,
        mock.patch(__name__ + ".ToyReader._read_contents") as read_contents,
    ):
        get.return_value = soup
        read_metadata.return_value = {"metadata": "foo"}
        read_contents.return_value = {"contents": "bar"}
        page = reader.read(url)

    if soup is None:
        assert page is None
        read_metadata.assert_not_called()
        read_contents.assert_not_called()
    else:
        assert page == {"metadata": "foo", "contents": "bar"}
        read_metadata.assert_called_once_with(url, soup)
        read_contents.assert_called_once_with(soup)


@given(
    st.sampled_from((None, "cat", "dog", "fish", "bird")),
    ST_DATES.map(dt.date.isoformat),
    st.text(string.ascii_lowercase),
)
def test_save(cat, date, code):
    """
    Test the method for saving dictionaries to JSON.

    We cannot use `given` and the `tmp_path` fixture at once, so we
    create a test directory and delete it with each run. It's not
    perfect, but it works. If this test fails, manually delete the
    `~/.parliai_public/test` directory to ensure there are no strange side
    effects.
    """

    where = os.path.join(
        "~", ".parliai_public", "test", ".".join(map(str, (cat, date, code)))
    )
    tmpdir = pathlib.Path(where).expanduser()
    tmpdir.mkdir(parents=True, exist_ok=True)

    idx = ".".join((date, code, "h"))
    content = {"cat": cat, "idx": idx, "date": date}

    reader = ToyReader(urls=[], outdir=tmpdir)
    reader.save(content)

    items = list(tmpdir.glob("**/*"))

    if cat is None:
        assert len(items) == 2
        assert items == [tmpdir / "data", tmpdir / "data" / f"{idx}.json"]
    else:
        assert len(items) == 3
        assert items == [
            tmpdir / "data",
            tmpdir / "data" / cat,
            tmpdir / "data" / cat / f"{idx}.json",
        ]

    with open(items[-1], "r") as f:
        assert content == json.load(f)

    shutil.rmtree(tmpdir)


@given(st_chunks_contains_responses())
def test_analyse(params):
    """Test the logic of the analyse method."""

    chunks, contains, responses = params
    reader = ToyReader(urls=[], llm=default_llm)

    with (
        mock.patch(
            "parliai_public.readers.base.BaseReader._split_text_into_chunks"
        ) as splitter,
        mock.patch(
            "parliai_public.readers.base.BaseReader.check_contains_terms"
        ) as checker,
        mock.patch(
            "parliai_public.readers.base.BaseReader._analyse_chunk"
        ) as analyser,
    ):
        splitter.return_value = chunks
        checker.side_effect = contains
        analyser.side_effect = responses
        response = reader.analyse({"text": "foo"})

    assert isinstance(response, dict) and "response" in response
    assert response["response"].split("\n\n") == responses

    splitter.assert_called_once_with("foo")

    assert checker.call_count == len(chunks)
    assert [call.args for call in checker.call_args_list] == [
        (chunk.page_content,) for chunk in chunks
    ]

    assert analyser.call_count == sum(contains)
    filtered = filter(lambda x: x[1], zip(chunks, contains))
    for (chunk, contain), call in zip(filtered, analyser.call_args_list):
        assert contain
        assert call.args == (chunk,)


@given(
    st.text(
        ["\n", " ", *string.ascii_letters],
        min_size=100,
        max_size=500,
    ),
    st.sampled_from((100, 250, 500)),
    st.sampled_from((0, 5, 10)),
)
def test_split_text_into_chunks(text, size, overlap):
    """
    Test the text splitter method.

    Currently, we do not do any rigorous testing. Work in progress.
    """

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        chunks = ToyReader._split_text_into_chunks(
            text, sep="\n", size=size, overlap=overlap
        )

    assert isinstance(chunks, list)
    assert all(isinstance(chunk, Document) for chunk in chunks)


@given(
    ST_FREE_TEXT.map(lambda x: Document(page_content=x)),
    st.text(" ", max_size=5),
)
@pytest.mark.skip("""Temporarily skipping. Test hangs. Actual LLM call.""")
def test_analyse_chunk(chunk, pad):
    """
    Test the chunk analyser.

    This function actually interacts with the LLM, so we mock that part
    and check the logic holds up.
    """

    reader = ToyReader(urls=[], prompt="{text}", llm=default_llm())

    with mock.patch("parliai_public.readers.base.ChatOllama") as chat:
        chat.return_value.invoke.return_value.content = f"response{pad}"
        response = reader._analyse_chunk(chunk)

    assert response == "response"

    chat.assert_called_once()
    chat.return_value.invoke.assert_called_once_with(chunk.page_content)


@given(
    st.lists(ST_DATES, min_size=1, unique=True),
    st.lists(provisional.urls(), min_size=1, max_size=5, unique=True),
)
def test_make_header(dates, urls):
    """Test the summary header looks right."""

    reader = ToyReader(dates=dates, urls=urls)

    header = reader.make_header()

    publication, period, _, _, source, _, *links = header.split("\n")

    assert re.search(r"\w+, \d{1,2} \w+ \d{4}$", publication) is not None
    assert period.startswith("Period covered: ")

    _, period = period.split(": ")
    date_regex = r"\w+, \d{1,2} \w+ \d{4}"
    if len(dates) == 1:
        assert re.match(rf"{date_regex}$", period) is not None
    else:
        assert re.match(rf"{date_regex} to {date_regex}$", period) is not None

    assert str(reader._source) in source

    for url, link in zip(urls, links):
        assert link.startswith("- ")
        assert url in link


@given(st.one_of(st.sampled_from(MODEL_NAMES)))
def test_instantiate_llm(llm_name):
    """Test that all model requests other than gemma revert to default."""

    reader = ToyReader(urls=[], llm_name=llm_name)
    _ = reader.instantiate_llm()
    assert reader.llm == default_llm()


@given(st.sampled_from(GEMMA_PREAMBLES))
def test_clean_response(response):
    """Test 'Sure...: ' gemma preamble is consistently removed."""

    reader = ToyReader(urls=[])
    assert reader.clean_response(response) == "My right honourable friend..."
