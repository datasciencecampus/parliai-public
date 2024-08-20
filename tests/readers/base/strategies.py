"""Composite strategies for testing the base reader."""

from hypothesis import strategies as st
from langchain.docstore.document import Document

from ...common import SEARCH_TERMS, ST_FREE_TEXT


@st.composite
def st_terms_and_texts(draw, terms=SEARCH_TERMS):
    """Create a possibly term-ridden string."""

    term = draw(st.lists(st.sampled_from(terms), max_size=1))
    string = draw(ST_FREE_TEXT)
    add_in = draw(st.booleans())

    text = " ".join((string, *term)) if add_in else string

    return term, text


@st.composite
def st_chunks_contains_responses(draw):
    """Create a set of chunks, booleans, and responses for a test."""

    chunks = draw(
        st.lists(
            ST_FREE_TEXT.map(lambda x: Document(page_content=x)),
            min_size=1,
            max_size=5,
        )
    )

    contains = [True, *(draw(st.booleans()) for _ in chunks[1:])]
    responses = [draw(ST_FREE_TEXT) for con in contains if con is True]

    return chunks, contains, responses
