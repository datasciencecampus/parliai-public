"""Example regression tests for the written answers reader."""

import requests
from bs4 import BeautifulSoup

from parliai_public import WrittenAnswers


def test_read_metadata_from_lead_2024_02_29_16305():
    """Test the lead extractor on entry 2024-02-29.16305."""

    url = "https://theyworkforyou.com/wrans/?id=2024-02-29.16305.h"
    page = requests.get(url)
    soup = BeautifulSoup(page.content, "html.parser")

    recipient, on = WrittenAnswers._read_metadata_from_lead(soup)

    assert recipient == "Northern Ireland Office"
    assert on == "2024-03-06"


def test_answer_does_not_mention_terms_2024_02_19_HL2510():
    """
    Test the output of entry 2024-02-19.HL2510 is parsed right.

    The answer to this written question does not mention the ONS, so we
    assert that the parsed response reflects that. Meanwhile, the
    question *does* mention the ONS.
    """

    url = "https://www.theyworkforyou.com/wrans/?id=2024-02-19.HL2510.h"
    tool = WrittenAnswers.from_toml()

    transcript = tool.read(url)
    assert isinstance(transcript, dict)
    assert len(transcript["questions"]) == 1

    question = transcript["questions"][0]
    assert tool.check_contains_terms(question["text"])

    answer = transcript["answer"]
    assert not tool.check_contains_terms(answer["text"])

    output = tool.render(transcript)
    answerer = (
        "[Lord Offord of Garvel](https://theyworkforyou.com/peer/?p=26052)"
        " (Parliamentary Under Secretary of State"
        " (Department for Business and Trade))"
    )
    assert f"### Answered by {answerer}" in output
    assert output.endswith("Answer does not mention any search terms.")


def test_multiple_questions_rendering_2024_03_20_19670():
    """Test for multiple questions like in entry 2024-03-20.19670."""

    url = "https://www.theyworkforyou.com/wrans/?id=2024-03-20.19670.h"
    tool = WrittenAnswers.from_toml()

    transcript = tool.read(url)
    assert isinstance(transcript, dict)

    questions = transcript["questions"]
    answer = transcript["answer"]
    assert len(questions) == 2
    assert isinstance(answer, dict)

    output = tool.render(transcript)
    for question in questions:
        assert question["name"] in output
        assert question["position"] in output
        assert question["url"] in output


def test_pick_up_answer_block_2024_03_27_HL3698():
    """
    Test the output of entry 2024-03-27.HL3698.

    Taken from issue #53, the answer block doesn't get rendered.
    """

    url = "https://www.theyworkforyou.com/wrans/?id=2024-03-27.HL3698.h"
    tool = WrittenAnswers.from_toml()

    transcript = tool.read(url)
    assert isinstance(transcript, dict)
    assert len(transcript["questions"]) == 1

    answer = transcript["answer"]
    assert tool.check_contains_terms(answer["text"])

    output = tool.render(transcript)
    answerer = (
        "[Baroness Vere of Norbiton](https://theyworkforyou.com/peer/?p=25587)"
        " (The Parliamentary Secretary, HM Treasury)"
    )
    assert f"### Answered by {answerer}" in output
    assert not output.endswith(answerer)
