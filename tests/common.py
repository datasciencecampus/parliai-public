"""
Common strategies and utilities used across multiple test modules.

Any real-world details or samples used as constants were correct when
taken on 2024-03-06.
"""

import datetime as dt
import string

from dateutil import relativedelta as rd
from hypothesis import strategies as st
from langchain_community.chat_models import ChatOllama

from parliai_public.readers.base import BaseReader


class ToyReader(BaseReader):
    """A toy class to allow testing our abstract base class."""

    def retrieve_latest_entries(self):
        """Allow testing with toy method."""

    @staticmethod
    def _read_metadata(url, soup):
        """Allow testing with toy static method."""

    @staticmethod
    def _read_contents(soup):
        """Allow testing with toy static method."""

    def render(self, response, page):
        """Allow testing with toy method."""

    def _summary_template(self):
        """Allow testing with toy method."""


def where_what(reader):
    """Get the right location and class for testing a reader."""

    what = reader
    if reader is ToyReader:
        what = BaseReader

    where = ".".join((what.__module__, what.__name__))

    return where, what


def default_llm() -> ChatOllama:
    """Instantiate default LLM object for use in testing."""

    llm = llm = ChatOllama(
        model="gemma",
        temperature=0,
    )

    return llm


MPS_SAMPLE = [
    (
        "Bob Seely",
        "Conservative, Isle of Wight",
        "https://www.theyworkforyou.com/mp/25645/bob_seely/isle_of_wight",
    ),
    (
        "Mark Logan",
        "Conservative, Bolton North East",
        "https://www.theyworkforyou.com/mp/25886/mark_logan/bolton_north_east",
    ),
    (
        "Nigel Huddleston",
        "Conservative, Mid Worcestershire",
        "https://www.theyworkforyou.com/mp/25381/nigel_huddleston/mid_worcestershire",
    ),
    (
        "Heather Wheeler",
        "Conservative, South Derbyshire",
        "https://www.theyworkforyou.com/mp/24769/heather_wheeler/south_derbyshire",
    ),
    (
        "Ian Paisley Jnr",
        "DUP, North Antrim",
        "https://www.theyworkforyou.com/mp/13852/ian_paisley_jnr/north_antrim",
    ),
    (
        "Matthew Offord",
        "Conservative, Hendon",
        "https://www.theyworkforyou.com/mp/24955/matthew_offord/hendon",
    ),
    (
        "John Howell",
        "Conservative, Henley",
        "https://www.theyworkforyou.com/mp/14131/john_howell/henley",
    ),
    (
        "Robert Goodwill",
        "Conservative, Scarborough and Whitby",
        "https://www.theyworkforyou.com/mp/11804/robert_goodwill/scarborough_and_whitby",
    ),
    (
        "Naseem Shah",
        "Labour, Bradford West",
        "https://www.theyworkforyou.com/mp/25385/naseem_shah/bradford_west",
    ),
    (
        "Amy Callaghan",
        "Scottish National Party, East Dunbartonshire",
        "https://www.theyworkforyou.com/mp/25863/amy_callaghan/east_dunbartonshire",
    ),
]

GOV_DEPARTMENTS = [
    "Attorney General's Office",
    "Cabinet Office",
    "Department for Business and Trade",
    "Department for Culture, Media and Sport",
    "Department for Education",
    "Department for Energy Security and Net Zero",
    "Department for Environment, Food and Rural Affairs",
    "Department for Levelling Up, Housing and Communities",
    "Department for Science, Innovation and Technology",
    "Department for Transport",
    "Department for Work and Pensions",
    "Department of Health and Social Care",
    "Export Credits Guarantee Department",
    "Foreign, Commonwealth and Development Office",
    "HM Treasury",
    "Home Office",
    "Ministry of Defence",
    "Ministry of Justice",
    "Northern Ireland Office",
    "Office of the Advocate General for Scotland",
    "Office of the Leader of the House of Commons",
    "Office of the Leader of the House of Lords",
    "Office of the Secretary of State for Scotland",
    "Office of the Secretary of State for Wales",
]

SEARCH_TERMS = (
    "ONS",
    "Office for National Statistics",
    "National Statistician",
)

TODAY = dt.date.today()
ST_DATES = st.dates(TODAY - rd.relativedelta(years=4), TODAY)

ST_FREE_TEXT = st.text(
    string.ascii_letters + string.digits + ".:;!?-", min_size=1
)

MODEL_NAMES = ["llama3", "mistral", "openhermes"]

GEMMA_PREAMBLES = [
    "Sure! Here is the text you are looking for: \nMy right honourable friend...",
    "Sure - here is the quote: My right honourable friend...",
    "Sure!The following contains references to your search terms:My right honourable friend...",
]
