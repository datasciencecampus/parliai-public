"""Unit tests for the `theyworkforyou` module."""

from unittest import mock

from bs4 import BeautifulSoup, Tag
from hypothesis import given, provisional, settings
from hypothesis import strategies as st

from parliai_public.readers.theyworkforyou import Debates

from ...common import ST_DATES
from .strategies import (
    st_daily_boards,
    st_debate_soups,
    st_debate_transcripts,
    st_entry_urls,
    st_metadatas,
    st_speech_soups,
    st_tags,
)

settings.register_profile("ci", deadline=None)
settings.load_profile("ci")


def mocked_debates(
    urls=None,
    terms=None,
    dates=None,
    outdir="out",
    prompt=None,
    llm_name=None,
):
    """Create a mocked and checked debates reader."""

    with mock.patch("parliai_public.Debates._load_config") as load:
        load.return_value = {
            "prompt": "",
            "llm_name": "gemma",
        }
        reader = Debates(
            urls,
            terms,
            dates,
            outdir,
            prompt,
            llm_name,
        )

    load.assert_called_once_with()

    return reader


@given(
    st.lists(provisional.urls(), min_size=1, max_size=5, unique=True),
    st.lists(ST_DATES, min_size=1, unique=True),
)
def test_list_latest_pages(urls, dates):
    """Test the method for retrieving the daily board pages."""

    reader = mocked_debates(urls=urls, dates=dates)

    pages = reader._list_latest_pages()

    assert isinstance(pages, list)
    assert all(isinstance(page, str) for page in pages)
    assert len(pages) == len(urls) * len(dates)

    for date in dates:
        hits = sum(page.endswith(date.isoformat()) for page in pages)
        assert hits == len(urls)


@given(
    st.lists(
        st.tuples(st.text(min_size=1), st.sampled_from(("", ".mh"))),
        min_size=1,
    )
)
def test_remove_multi_link_statements(parts):
    """Test the method for removing those that end with `.mh`."""

    reader = mocked_debates()
    pages = ["".join(pair) for pair in parts]

    filtered = reader._remove_multi_link_statements(pages)

    assert isinstance(filtered, list)
    assert all(isinstance(page, str) for page in filtered)
    for page in pages:
        if page.endswith(".mh"):
            assert page not in filtered
        else:
            assert page in filtered


@given(st.lists(st_daily_boards(), min_size=1))
def test_retrieve_latest_entries(boards):
    """Test the core link retriever."""

    urls, hrefs, soups = [], [], []
    for url, href, soup in boards:
        urls.append(url)
        hrefs.extend(href)
        soups.append(soup)

    reader = mocked_debates()

    with (
        mock.patch("parliai_public.Debates._list_latest_pages") as llp,
        mock.patch("parliai_public.Debates.get") as get,
        mock.patch(
            "parliai_public.Debates._remove_multi_link_statements"
        ) as rms,
    ):
        llp.return_value = urls
        get.side_effect = soups
        rms.side_effect = lambda x: x
        entries = reader.retrieve_latest_entries()

    assert isinstance(entries, list)
    assert len(entries) == len(hrefs)
    for entry, href in zip(entries, hrefs):
        assert isinstance(entry, str)
        assert entry == "https://theyworkforyou.com" + href

    llp.assert_called_once_with()

    assert get.call_count == len(soups)
    for call, url in zip(get.call_args_list, urls):
        assert call.args == (url,)
        assert call.kwargs == {"check": False}

    rms.assert_called_once_with(entries)


@given(st_metadatas())
def test_read_metadata(meta):
    """Test the debates metadata extractor works correctly."""

    block, date, idx, cat, url = meta

    soup = mock.MagicMock()
    soup.find.return_value.get_text.return_value = block

    reader = mocked_debates()

    metadata = reader._read_metadata(url, soup)

    assert isinstance(metadata, dict)
    assert tuple(metadata.keys()) == ("cat", "idx", "title", "date", "url")
    assert metadata["cat"] == cat
    assert metadata["idx"] == idx
    assert block.startswith(metadata["title"])
    assert metadata["date"] in url
    assert metadata["date"] == date.strftime("%Y-%m-%d")
    assert metadata["url"] == url

    soup.find.assert_called_once_with("title")
    soup.find.return_value.get_text.assert_called_once_with()


@given(st_debate_soups())
def test_read_contents(debate):
    """Test the logic of the content reader method."""

    soup, speakers, positions, hrefs, contents = debate
    reader = mocked_debates()

    with mock.patch("parliai_public.Debates._process_speech") as process:
        process.side_effect = lambda x: x
        content = reader._read_contents(soup)

    assert isinstance(content, dict)
    assert list(content.keys()) == ["speeches"]

    speeches = content["speeches"]
    assert isinstance(speeches, list) and len(speeches) == len(speakers)
    for speech, speaker, position, href, text in zip(
        speeches, speakers, positions, hrefs, contents
    ):
        assert isinstance(speech, Tag)
        assert speaker in speech.get_text()
        assert position in speech.get_text()
        assert speech.find("a").get("href") == href
        assert text in speech.get_text()

    process.call_count == len(speakers)
    for call, speech in zip(process.call_args_list, content["speeches"]):
        assert call.args == (speech,)


@given(st_speech_soups())
def test_process_speech(speech):
    """
    Test the logic of the speech processor.

    The core processing is done downstream, so this test checks
    high-level things like that the right functions are called with the
    right arguments.
    """

    soup, name, position, href, text = speech
    reader = mocked_debates()

    with (
        mock.patch(
            "parliai_public.Debates._extract_speaker_details"
        ) as extract_details,
        mock.patch(
            "parliai_public.Debates._extract_speech_text"
        ) as extract_text,
    ):
        extract_details.return_value = (name, position, href)
        extract_text.return_value = text
        processed = reader._process_speech(soup)

    assert isinstance(processed, dict)
    assert processed == dict(name=name, position=position, url=href, text=text)

    extract_details.assert_called_once_with(soup)
    extract_text.assert_called_once_with(soup)


@given(st_speech_soups())
def test_extract_speaker_details(speech):
    """Test the speaker details extractor."""

    soup, name, position, href, _ = speech
    reader = mocked_debates()

    with mock.patch("parliai_public.Debates._get_detail_text") as get_detail:
        get_detail.side_effect = lambda x: x.get_text()
        speaker, pos, url = reader._extract_speaker_details(soup)

    assert speaker == name
    assert pos == position
    assert url == f"https://theyworkforyou.com{href}"

    assert get_detail.call_count == 2
    assert [
        call.args == (detail,)
        for call, detail in zip(get_detail.call_args_list, (name, position))
    ]


def test_extract_speaker_details_none():
    """Test the details extractor skips when there is no speaker."""

    soup = BeautifulSoup()
    reader = mocked_debates()

    with mock.patch("parliai_public.Debates._get_detail_text") as get_detail:
        name, position, url = reader._extract_speaker_details(soup)

    assert name is None
    assert position is None
    assert url is None

    get_detail.assert_not_called()


@given(st_tags())
def test_get_detail_text_valid(tag):
    """Check the detail getter works for valid `bs4.Tag` inputs."""

    tag, text = tag
    detail = Debates._get_detail_text(tag)

    assert detail == text


def test_get_detail_text_none():
    """Check the detail getter does nothing for `None` input."""

    detail = Debates._get_detail_text(None)

    assert detail is None


@given(st_speech_soups())
def test_extract_speech_text(speech):
    """Check the speech text extractor."""

    soup, *_, text = speech
    reader = mocked_debates()

    extracted = reader._extract_speech_text(soup)

    assert extracted == text.strip()


@given(
    st.lists(st.booleans(), min_size=20, max_size=20), st_debate_transcripts()
)
def test_analyse(contains, transcript):
    """
    Test the speech analyst.

    We check the logic of the `Debates.analyse()` method here rather
    than its ability to analyse a debate transcript. Doing so would
    require accessing the LLM which is costly and time-consuming. So, we
    mock out the super method.
    """

    reader = mocked_debates()

    with (
        mock.patch("parliai_public.Debates.check_contains_terms") as checker,
        mock.patch(
            "parliai_public.readers.base.BaseReader.analyse"
        ) as base_analyst,
    ):
        checker.side_effect = contains
        base_analyst.side_effect = lambda x: x
        page = reader.analyse(transcript)

    assert page == transcript

    speeches = transcript["speeches"]
    checker_calls = checker.call_args_list
    analyst_calls = base_analyst.call_args_list
    for contain, speech in zip(contains, speeches):
        checker_calls.pop(0).args == (speech["text"],)
        if contain:
            call = analyst_calls.pop(0)
            assert call.args == (speech,)

    assert checker_calls == []
    assert analyst_calls == []


@given(st_entry_urls())
def test_parliament_label_valid(url):
    """Check the labeller works as it should for valid URLs."""

    reader = mocked_debates()

    tag = reader.parliament_label(url)

    LABEL_LOOKUP = {
        "debates": "House of Commons",
        "lords": "House of Lords",
        "whall": "Westminster Hall",
        "wms": "UK Ministerial statement",
        "senedd": "Senedd / Welsh Parliament",
        "sp": "Scottish Parliament",
        "ni": "Northern Ireland Assembly",
    }

    assert isinstance(tag, str)
    assert tag == LABEL_LOOKUP.get(url.split("/")[3])


@given(st_entry_urls(categories=[None]))
def test_parliament_label_invalid(url):
    """Check the labeller catches an error for invalid URLs."""

    reader = mocked_debates()

    assert reader.parliament_label(url) == "Unclassified"


@given(st_debate_transcripts())
def test_render(transcript):
    """Test that a transcript rendering looks right."""

    reader = mocked_debates()

    rendering = reader.render(transcript)

    assert isinstance(rendering, str)
    assert len(rendering.split("\n\n")) == 1 + 2 * len(transcript["speeches"])

    title = rendering.split("\n\n")[0]
    assert transcript["title"] in title
    assert transcript["url"] in title

    speakers = rendering.split("\n\n")[1::2]
    for speaker, speech in zip(speakers, transcript["speeches"]):
        assert speech["name"] in speaker
        assert speech["url"] in speaker
        assert speech["position"] in speaker

    texts = rendering.split("\n\n")[2::2]
    for text, speech in zip(texts, transcript["speeches"]):
        assert text == speech["response"]
