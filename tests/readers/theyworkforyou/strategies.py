"""Test strategies for the `Debates` class."""

import re
import string

from bs4 import BeautifulSoup, NavigableString, Tag
from hypothesis import provisional
from hypothesis import strategies as st

from ...common import GOV_DEPARTMENTS, MPS_SAMPLE, ST_DATES, ST_FREE_TEXT


@st.composite
def st_title_blocks(draw, date=None):
    """Create text for a title block in a parliamentary entry."""

    if date is None:
        date = draw(ST_DATES)

    title = draw(ST_FREE_TEXT)
    extra = draw(ST_FREE_TEXT)

    block = ": ".join((title, date.strftime("%d %b %Y"), extra))

    return block


@st.composite
def st_indices(draw, date=None):
    """Create an index for a parliamentary entry."""

    if date is None:
        date = draw(ST_DATES)

    prefix = draw(st.text(alphabet="abc", max_size=1))
    body = draw(st.integers(0, 10).map(str))

    idx = ".".join((date.strftime("%Y-%m-%d"), prefix, body, "h"))

    return idx


@st.composite
def st_metadatas(draw):
    """Create a metadata block for our parliamentary summary tests."""

    date = draw(ST_DATES)
    block = draw(st_title_blocks(date))
    idx = draw(st_indices(date))

    cat = draw(st.sampled_from(("lords", "debates", "whall")))
    url = "/".join((draw(provisional.urls()), cat, f"?id={idx}"))

    return block, date, idx, cat, url


@st.composite
def st_lead_metadatas(draw):
    """Create a lead block for a written answer test."""

    date = draw(ST_DATES)
    recipient = draw(st.sampled_from(GOV_DEPARTMENTS))

    lead = (
        f"{recipient} written question "
        f"- answered on {date.strftime('%d %B %Y')}"
    )

    return lead, recipient, date


@st.composite
def st_speeches(draw):
    """Create a speech and its details for a parliamentary test."""

    speaker, position, url = draw(st.sampled_from(MPS_SAMPLE))
    speech = draw(ST_FREE_TEXT)

    return speech, speaker, position, url


@st.composite
def st_daily_boards(draw):
    """Create some HTML soup to simulate a daily board."""

    date = draw(st.dates()).strftime("%Y-%m-%d")
    url = f"https://theyworkforyou.com/debates/?d={date}"

    st_href = st.text(
        string.digits + string.ascii_letters, min_size=1, max_size=5
    ).map(lambda x: f"/debates/{x}.h")

    hrefs = draw(st.lists(st_href, min_size=1, max_size=10))
    tags = [
        f'<a href={href} class="business-list__title"></a>' for href in hrefs
    ]
    soup = BeautifulSoup("\n".join(tags), "html.parser")

    return url, hrefs, soup


def extract_href(url):
    """Extract just the hyperlink reference from a URL."""

    match = re.search(r"(?<=.com)\/\w+\/\d+(?=\/)", url)

    if match is None:
        return url

    return match.group()


def format_speech_block(name, pos, href, text):
    """Get a speech block into HTML format."""

    html = '<div class="debate-speech__speaker-and-content">'
    html += '<h2 class="debate-speech__speaker">'
    html += f'<a href="{href}">'
    html += f'<strong class="debate-speech__speaker__name">{name}</strong>'
    html += f'<small class="debate-speech__speaker__position">{pos}</small>'
    html += "</a>"
    html += "</h2>"
    html += f'<div class="debate-speech__content"><p>{text}</p></div>'
    html += "</div>"

    return html


@st.composite
def st_speech_soups(draw):
    """Create some HTML soup for a speech block."""

    text, name, pos, url = draw(st_speeches())
    href = extract_href(url)
    html = format_speech_block(name, pos, href, text)

    return BeautifulSoup(html, "html.parser"), name, pos, href, text


@st.composite
def st_debate_soups(draw):
    """Create some HTML soup for a debate page."""

    speakers = draw(
        st.lists(
            st.sampled_from(MPS_SAMPLE),
            min_size=2,
            max_size=10,
            unique=True,
        )
    )

    names, positions, hrefs, texts = [], [], [], []
    html = ""
    for name, pos, url in speakers:
        href = extract_href(url)
        text = draw(ST_FREE_TEXT)
        names.append(name)
        positions.append(pos)
        hrefs.append(href)
        texts.append(text)

        html += format_speech_block(name, pos, href, text)

    return BeautifulSoup(html, "html.parser"), names, positions, hrefs, texts


@st.composite
def st_tags(draw):
    """Create a tag for processing."""

    name = draw(st.sampled_from(("a", "h1", "h2", "strong", "small", "p")))
    text = draw(st.text(string.ascii_letters + string.digits, min_size=1))

    tag = Tag(name=name)
    tag.insert(0, NavigableString(text))

    return tag, text


@st.composite
def st_entry_urls(
    draw, categories=("debates", "lords", "whall", "wms", "senedd", "sp", "ni")
):
    """Create a realistic URL for an entry."""

    category = draw(st.sampled_from(categories))
    date = draw(ST_DATES)
    idx = draw(st.uuids().map(str))
    index = f"?id={date}.{idx}"

    elements = filter(None, (category, index))

    return "/".join(("https://theyworkforyou.com", *elements))


@st.composite
def st_debate_transcripts(draw, max_size=10):
    """Create a transcript dictionary for a debate."""

    speakers = draw(
        st.lists(st.sampled_from(MPS_SAMPLE), min_size=2, max_size=max_size)
    )

    speeches = []
    for name, position, url in speakers:
        text = draw(ST_FREE_TEXT)
        speech = {
            "name": name,
            "position": position,
            "url": url,
            "text": text,
            "response": text,
        }
        speeches.append(speech)

    transcript = {
        "title": draw(ST_FREE_TEXT),
        "url": draw(provisional.urls()),
        "speeches": speeches,
    }

    return transcript


@st.composite
def st_written_transcripts(draw):
    """Create a transcript dictionary for a written answer entry."""

    transcript = draw(st_debate_transcripts(max_size=3))

    *questions, answer = transcript.pop("speeches")
    transcript["questions"] = questions
    transcript["answer"] = answer

    transcript["recipient"] = draw(st.sampled_from(GOV_DEPARTMENTS))

    date = draw(st.dates()).isoformat()
    transcript["date"] = date
    transcript["answered"] = date

    return transcript
