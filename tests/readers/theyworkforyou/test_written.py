"""Unit tests for the written answers reader."""

import warnings
from unittest import mock

import pytest
from hypothesis import given, provisional
from hypothesis import strategies as st

from parliai_public import WrittenAnswers

from .strategies import (
    st_debate_soups,
    st_lead_metadatas,
    st_speeches,
    st_written_transcripts,
)


def mocked_written(
    urls=None,
    terms=None,
    dates=None,
    outdir="out",
    prompt=None,
    llm_name=None,
):
    """Create a mocked and checked written answers reader."""

    urls = urls or WrittenAnswers._supported_urls

    with mock.patch("parliai_public.WrittenAnswers._load_config") as load:
        load.return_value = {
            "prompt": "",
            "llm_name": "gemma",
        }
        written = WrittenAnswers(
            urls,
            terms,
            dates,
            outdir,
            prompt,
            llm_name,
        )

    load.assert_called_once_with()

    return written


def mocked_caught_written(
    urls=None,
    terms=None,
    dates=None,
    outdir="out",
    prompt=None,
):
    """Create a mocked written answers reader without warnings."""

    with warnings.catch_warnings():
        return mocked_written(
            urls,
            terms,
            dates,
            outdir,
            prompt,
        )


@given(st.lists(provisional.urls(), min_size=1, max_size=5))
def test_init_warns(urls):
    """Test the reader gives a with unsupported URLs."""

    with pytest.warns(UserWarning, match="^URLs must be a list of supported"):
        _ = mocked_written(urls)


@given(st_lead_metadatas())
def test_read_metadata_from_lead(meta):
    """Test the lead metadata extractor works correctly."""

    lead, name, date = meta
    written = mocked_caught_written()

    soup = mock.MagicMock()
    soup.find.return_value.get_text.return_value = lead

    recipient, on = written._read_metadata_from_lead(soup)

    assert recipient == name
    assert on == date.isoformat()

    soup.find.assert_called_once_with("p", attrs={"class": "lead"})
    soup.find.return_value.get_text.assert_called_once_with()


@given(st_speeches(), st_lead_metadatas())
def test_read_metadata(speech, lead):
    """Test the full metadata extractor works correctly."""

    speech, speaker, position, url = speech
    _, recipient, on = lead

    written = mocked_caught_written()
    with (
        mock.patch("parliai_public.Debates._read_metadata") as super_extract,
        mock.patch(
            "parliai_public.WrittenAnswers._read_metadata_from_lead"
        ) as get_lead,
    ):
        super_extract.return_value = {"metadata": None}
        get_lead.return_value = (recipient, on)
        metadata = written._read_metadata(url, "soup")

    assert isinstance(metadata, dict)
    assert metadata == {
        "metadata": None,
        "recipient": recipient,
        "answered": on,
    }

    super_extract.assert_called_once_with(url, "soup")
    get_lead.assert_called_once_with("soup")


@given(st_debate_soups())
def test_read_contents(debate):
    """Test the content reader method."""

    soup, speakers, positions, hrefs, contents = debate
    reader = mocked_written()

    super_content = {
        "speeches": [
            {
                "name": speaker,
                "position": position,
                "url": href,
                "text": content,
            }
            for speaker, position, href, content in zip(
                speakers, positions, hrefs, contents
            )
        ]
    }

    with mock.patch("parliai_public.Debates._read_contents") as super_reader:
        super_reader.return_value = super_content
        content = reader._read_contents(soup)

    assert isinstance(content, dict)

    questions, answer = content.pop("questions"), content.pop("answer")

    assert content == {}
    assert isinstance(questions, list)
    assert questions == super_content["speeches"][:-1]
    assert isinstance(answer, dict)
    assert answer == super_content["speeches"][-1]


@given(st.booleans(), st_written_transcripts())
def test_analyse(contains, transcript):
    """
    Test the answer analyst method.

    Like many other tests, we only test the logic of this method rather
    than its ability to process a response. This approach avoids
    accessing the LLM without a realistic example and repeating work to
    test the `BaseReader.analyse()` method this method calls.
    """

    reader = mocked_written()

    with (
        mock.patch(
            "parliai_public.WrittenAnswers.check_contains_terms"
        ) as checker,
        mock.patch(
            "parliai_public.readers.base.BaseReader.analyse"
        ) as base_analyst,
    ):
        checker.return_value = contains
        base_analyst.side_effect = lambda x: x
        page = reader.analyse(transcript)

    assert page == transcript

    checker.assert_called_once_with(transcript["answer"]["text"])
    if contains:
        base_analyst.assert_called_once_with(transcript["answer"])
    else:
        base_analyst.assert_not_called()


@given(st_written_transcripts())
def test_render(transcript):
    """Test the written answer rendering looks right."""

    reader = mocked_written()

    with mock.patch(
        "parliai_public.WrittenAnswers._render_answer"
    ) as render_answer:
        render_answer.side_effect = lambda x: x["response"]
        rendering = reader.render(transcript)

    assert isinstance(rendering, str)
    assert len(rendering.split("\n\n")) == 3 + 2 * len(transcript["questions"])

    parts = rendering.split("\n\n")
    title = parts[0]
    assert transcript["title"] in title
    assert transcript["url"] in title

    questioners = parts[1:-2:2]
    for i, questioner in enumerate(questioners):
        question = transcript["questions"][i]
        assert question["name"] in questioner
        assert question["url"] in questioner
        assert question["position"] in questioner

    questions = parts[2:-2:2]
    for i, question in enumerate(questions):
        assert question == transcript["questions"][i]["text"].strip()

    metadata = parts[-2]
    assert transcript["recipient"] in metadata
    assert transcript["date"] in metadata
    assert transcript["answered"] in metadata

    answer = parts[-1]
    assert answer == transcript["answer"]["response"]

    render_answer.assert_called_once_with(transcript["answer"])


@given(st_speeches())
def test_render_answer_response(speech):
    """Test the answer renderer when there was an LLM response."""

    text, name, position, url = speech
    answer = {
        "name": name,
        "position": position,
        "url": url,
        "text": text,
        "response": text,
    }

    rendering = WrittenAnswers._render_answer(answer)

    assert isinstance(rendering, str)
    assert rendering.startswith("### Answered by ")
    assert len(rendering.split("\n\n")) == 2

    title, answer = rendering.split("\n\n")
    assert name in title
    assert url in title
    assert position in title
    assert answer == text


@given(st_speeches())
def test_render_answer_without_response(speech):
    """Test the answer renderer when there was no LLM response."""

    text, name, position, url = speech
    answer = {
        "name": name,
        "position": position,
        "url": url,
        "text": text,
    }

    rendering = WrittenAnswers._render_answer(answer)

    assert isinstance(rendering, str)
    assert rendering.startswith("### Answered by ")
    assert len(rendering.split("\n\n")) == 2

    title, answer = rendering.split("\n\n")
    assert name in title
    assert url in title
    assert position in title
    assert "does not mention" in answer
