"""Example tests for the base reader class."""

import requests
from bs4 import BeautifulSoup

from ...common import ToyReader


def test_does_not_match_for_extra_abbreviations():
    """Ensure the string checker does not flag ONS+ abbreviations."""

    reader = ToyReader(urls=[], terms=["ONS"])
    strings = (
        "The ONSR is the Only National Sandwich Ranking.",
        "I AM UNLUCKY! SOME MIGHT SAY I AM DONSY!",
    )

    for string in strings:
        assert not reader.check_contains_terms(string)


def test_81_add_ons_not_matched():
    """Ensure the example from #81 does not match."""

    reader = ToyReader([], terms=["ONS"])
    url = "https://theyworkforyou.com/wrans/?id=2024-04-12.21381.h"

    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    assert not reader.check_contains_terms(soup.get_text())
