"""Base class for other readers to inherit from."""

import abc
import datetime as dt
import json
import os
import re
from importlib import resources
from typing import Iterable
from urllib.parse import urlparse

import requests
import toml
from bs4 import BeautifulSoup
from langchain.docstore.document import Document
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.chat_models import ChatOllama

from parliai_public import dates


class BaseReader(metaclass=abc.ABCMeta):
    """
    A base class for readers to inherit.

    This class is not to be used in practice except for inheritance.

    To make your own reader class, you can inherit from this base class
    and implement the following methods:

    - `retrieve_latest_entries`: gather the URLs of the latest pages to
      be read, analysed, and rendered by the class
    - `_read_metadata` (static): extract whatever metadata you might
      need from the HTML soup of a web page and its URL
    - `_read_contents` (static): extract the core (text) content from
      the HTML soup of a web page
    - `render`: create a Markdown string to summarise the relevant
      content on a web page

    Parameters
    ----------
    urls : list[str]
        List of URLs from which to gather content.
    terms : Iterable[str], optional
        Key terms to filter content on. By default, we look for any
        mention of `Office for National Statistics` or `ONS`.
    dates : list[dt.date], optional
        List of dates from which to pull entries. The `parliai_public.dates`
        module may be of help. If not specified, only yesterday is used.
    outdir : str, default="out"
        Location of a directory in which to write outputs.
    prompt : str, optional
        System prompt provided to the LLM. If not specified, this is
        read from the default configuration file.
    llm_name : str, optional
        Full name of the LLM (or version) to be accessed. Must be one
        available in Ollama and previously downloaded locally.
    llm : ChatOllama, optional
        Chat model wrapper.
    """

    _default_config: str = "base.toml"
    _source: None | str = None

    def __init__(
        self,
        urls: list[str],
        terms: None | Iterable[str] = None,
        dates: None | list[dt.date] = None,
        outdir: str = "out",
        prompt: None | str = None,
        llm_name: None | str = None,
        llm: None | ChatOllama = None,
        inconsistency_statement: None | str = None,
    ) -> None:
        self.urls = urls
        base_config = toml.load("src/parliai_public/_config/base.toml")
        self.terms = terms or base_config["keywords"]
        self.inconsistency_statement = (
            inconsistency_statement or base_config["inconsistency_statement"]
        )
        self.dates = dates or [dt.date.today() - dt.timedelta(days=1)]
        self.outdir = outdir

        config = self._load_config()
        self.prompt = prompt or config["prompt"]
        self.llm_name = llm_name or config["llm_name"]
        self.llm = llm

    @classmethod
    def _load_config(cls, path: None | str = None) -> dict:
        """
        Load a configuration file from disk.

        If no path is supplied, the default is used for the class.

        Parameters
        ----------
        path : str, optional
            Path to configuration file. If `None`, the default is used.

        Returns
        -------
        config : dict
            Dictionary containing configuration details.
        """

        if isinstance(path, str):
            return toml.load(path)

        where = resources.files("parliai_public._config")
        with resources.as_file(where.joinpath(cls._default_config)) as c:
            config = toml.load(c)

        return config

    @classmethod
    def from_toml(cls, path: None | str = None) -> "BaseReader":
        """
        Create an instance of the class from a configuration TOML file.

        A complete configuration file will include all parameters listed
        in the doc-string of this class.

        Parameters
        ----------
        path : str, optional
            Path to configuration file. If `None`, the default is used.

        Returns
        -------
        reader : BaseReader
            reader instance.
        """

        config = cls._load_config(path)

        start = config.pop("start", None)
        end = config.pop("end", None)
        window = config.pop("window", None)
        form = config.pop("form", "%Y-%m-%d")

        config["dates"] = None
        if start or end or window:
            config["dates"] = dates.list_dates(start, end, window, form)

        return cls(**config)

    def check_contains_terms(self, string: str) -> bool:
        """
        Check whether a string contains any of the search terms.

        If you have not specified any search terms, this function
        returns `True`.

        This function determines a term is contained in the search
        string using a regular expression. Using the standard `in`
        operator on two strings would lead to false positives. For
        instance, it would say the term "dog" is in the phrase
        "dogmatism is the greatest of mental obstacles to human
        happiness," which is not our intention.

        Instead, we flag a term as being present if it appears at either
        end of the string or in the middle with certain surrounding
        characters:

        - The term may be preceded by whitespace, square brackets or
          parentheses.
        - The term may be followed by whitespace, brackets, or a small
          selection of punctuation, including things like commas and
          full stops.

        Parameters
        ----------
        string : str
            String to be checked.

        Returns
        -------
        contains : bool
            Whether the string contains any search terms.
        """

        terms = self.terms
        if not terms:
            return True

        string = string.lower()
        for term in map(str.lower, terms):
            match = re.search(
                rf"(^|(?<=[\('\[\s])){term}(?=[\)\]\s!?.,:;'-]|$)", string
            )
            if match:
                return True

        return False

    def make_outdir(self) -> None:
        """
        Create the output directory for a run.

        Attributes
        ----------
        outdir : str
            Updated output directory, defined by the runtime parameters.
        """

        start, end = min(self.dates), max(self.dates)
        period = ".".join(map(dt.date.isoformat, [start, end]))
        name = ".".join((period, self.llm_name))

        outdir = os.path.join(self.outdir, name)
        outdir = self._tag_outdir(outdir)

        os.makedirs(outdir)
        self.outdir = outdir

    def _tag_outdir(self, outdir: str) -> str:
        """
        Determine a unique version for the output directory and tag it.

        If the output directory already exists, then we add a number tag
        to the end of the directory name. This number is incremental.

        Parameters
        ----------
        outdir : str
            Output directory path.

        Returns
        -------
        outdir : str
            Potentially updated directory path.
        """

        if not os.path.exists(outdir):
            return outdir

        tag = 1
        while os.path.exists(updated := ".".join((outdir, str(tag)))):
            tag += 1

        return updated

    @abc.abstractmethod
    def retrieve_latest_entries(self) -> list[str]:
        """
        Replace with method for getting the latest entries to analyse.

        Returns
        -------
        entries : list[str]
            List of web pages from which to draw down relevant
            information.
        """

    def get(self, url: str, check: bool = True) -> None | BeautifulSoup:
        """
        Retrieve the HTML soup for a web page.

        Parameters
        ----------
        url : str
            Link to the web page.
        check : bool, default=True
            Whether to check the page for any relevant terms. Default is
            to do so.

        Returns
        -------
        soup : None | bs4.BeautifulSoup
            HTML soup of the web page if the page contains any relevant
            terms. Otherwise, `None`.
        """

        page = requests.get(url)
        soup = BeautifulSoup(page.content, "html.parser")
        if (not check) or (
            check and self.check_contains_terms(soup.get_text())
        ):
            return soup

    def read(self, url: str) -> None | dict:
        """
        Read a web page, and return its contents if it is relevant.

        Parameters
        ----------
        url : str
            Link to the web page to read.

        Returns
        -------
        page : None | dict
            If the web page is relevant, return a dictionary format of
            the page text and metadata. Otherwise, `None`.
        """

        soup = self.get(url)
        page = None
        if soup is not None:
            metadata = self._read_metadata(url, soup)
            contents = self._read_contents(soup)
            page = {**metadata, **contents}

        return page

    @abc.abstractmethod
    def _read_metadata(self, url: str, soup: BeautifulSoup) -> dict:
        """
        Replace with method to read metadata from an entry.

        Parameters
        ----------
        url : str
            URL of the entry.
        soup : bs4.BeautifulSoup
            HTML soup of the entry.

        Returns
        -------
        metadata : dict
            Dictionary containing the relevant metadata.
        """

    @abc.abstractmethod
    def _read_contents(self, soup: BeautifulSoup) -> dict:
        """
        Replace with method to read text content from some HTML soup.

        Parameters
        ----------
        soup : bs4.BeautifulSoup
            HTML soup of a webpage.

        Returns
        -------
        text : dict
            Dictionary containing any of the relevant contents on the
            webpage in plain-text format.
        """

    def instantiate_llm(self) -> None:
        """Instantiate LLM object per user specification."""

        # Temporary override to default to Gemma (known/tested LLM)
        self.llm_name = "gemma"
        self.llm = ChatOllama(model=self.llm_name, temperature=0)

        return None

    def analyse(self, transcript: dict) -> dict:
        """
        Send some text to the LLM for analysis (and receive a response).

        Parameters
        ----------
        transcript : dict
            Web page transcript with a `text` entry to be analysed.

        Returns
        -------
        transcript : dict
            Updated transcript with the LLM response.
        """

        chunks = self._split_text_into_chunks(transcript["text"])

        responses = []
        for chunk in chunks:
            if self.check_contains_terms(chunk.page_content):
                response = self._analyse_chunk(chunk)

                # failed check
                if not self._check_response(response, chunk):
                    response += f"\n\n{self.inconsistency_statement}"
                    print("LLM response inconsistent with source.")

                responses.append(response)

        transcript["response"] = "\n\n".join(responses)

        return transcript

    def clean_response(self, response: str):
        """
        Remove 'Sure....:' preamble if gemma model used.

        Parameters
        ----------
        response : str
            Raw response from LLM.

        Returns
        -------
        response : str
            Cleaned response.
        """

        response = re.sub(r"^Sure(.*?\:)\s*", "", response)

        return response

    @staticmethod
    def _split_text_into_chunks(
        text: str,
        sep: str = ". ",
        size: int = 4000,
        overlap: int = 1000,
    ) -> list[Document]:
        r"""
        Split a debate into chunks to be processed by the LLM.

        Some of the speeches within a single debate can get very large,
        making them intractable for the LLM.

        Parameters
        ----------
        text : str
            Text to be split.
        sep : str
            Separator to define natural chunks. Defaults to `. `.
        size : int
            Chunk size to aim for. Defaults to 20,000 tokens.
        overlap : int
            Overlap between chunks. Defaults to 4,000 tokens.

        Returns
        -------
        chunks : list[Document]
            Chunked-up text for processing.
        """

        splitter = RecursiveCharacterTextSplitter(
            separators=sep,
            chunk_size=size,
            chunk_overlap=overlap,
            length_function=len,
            keep_separator=False,
            is_separator_regex=False,
        )

        return splitter.create_documents([text])

    def _analyse_chunk(self, chunk: Document) -> str:
        """
        Extract the relevant content from a chunk using LLM.

        Parameters
        ----------
        chunk : langchain.docstore.document.Document
            Document with the chunk contents to be processed.

        Returns
        -------
        response : str
            LLM response, lightly formatted.
        """

        prompt_template = PromptTemplate(
            input_variables=["keywords", "text"], template=self.prompt
        )
        prompt = prompt_template.format(
            keywords=self.terms, text=chunk.page_content
        )

        llm = self.llm
        response = llm.invoke(prompt).content.strip()
        if self.llm_name == "gemma":
            response = self.clean_response(response)

        return response

    def _check_response(self, response: str, chunk: Document) -> bool:
        """Check if LLM response appears verbatim in original text.

        Parameters
        ----------
        response : str
            LLM response, lightly formatted.
        chunk : langchain.docstore.document.Document
            Document with the chunk contents.

        Returns
        -------
        passed : bool
            True/False the LLM response is present exactly in the original.
        """

        # TODO: string formatting function to reduce code
        original = chunk.page_content.lower()
        original = re.sub(r"[^\w\s]", "", original)

        passed = False

        for el in response.split(". "):
            el = el.lower()
            el = re.sub(r"[^\w\s]", "", el)

            if el.lower() not in original:
                passed = False
                return passed
            else:
                passed = True

        return passed

    def save(self, page: dict) -> None:
        """
        Save an HTML entry to a more compact JSON format.

        We use the metadata to create a file path for the JSON data. The
        file itself is called `{content["idx"]}.json` and it is saved at
        `self.outdir` under the `{content["cat"]}` directory if the
        entry has a category. Otherwise, it is saved in `self.outdir`.

        Parameters
        ----------
        page : dict
            Dictionary containing the contents and metadata of the
            entry.
        """

        cat, idx = page.get("cat"), page.get("idx")

        root = os.path.join(self.outdir, "data")
        where = root if cat is None else os.path.join(root, cat)
        os.makedirs(where, exist_ok=True)

        with open(os.path.join(where, f"{idx}.json"), "w") as f:
            json.dump(page, f, indent=4)

    @abc.abstractmethod
    def render(self, transcript: dict) -> str:
        """
        Replace with a method to render an entry in Markdown.

        Parameters
        ----------
        transcript : dict
            Dictionary containing the metadata and contents of the web
            page to be rendered. This dictionary also includes the LLM
            response(s) for that page.

        Returns
        -------
        rendering : str
            A rendering of the page and its metadata in Markdown format.
        """

    def make_header(self, urls: list[str] = None) -> str:
        """
        Make the header for a summary report.

        Parameters
        ----------
        urls : list[str], optional
            List of URLs to report in summary. If not specified, which
            is the expected user behaviour, the URLs used by the reader
            will be used.

        Returns
        -------
        header : str
            Markdown string with details of the reporting date, period
            covered, and source of materials.
        """

        form = "%a, %d %b %Y"
        today = dt.date.today().strftime(form)

        dates = self.dates
        if len(dates) == 1:
            period = dates[-1].strftime(form)
        else:
            start = min(dates).strftime(form)
            end = max(dates).strftime(form)
            period = f"{start} to {end}"

        urls = urls or self.urls
        source = f"Based on information from {self._source}:\n"
        links = []
        for url in urls:
            parsed = urlparse(url)
            link = url.replace(f"{parsed.scheme}://", "", 1)
            links.append(f"- [{link}]({url})")

        header = "\n".join(
            (
                f"Publication date: {today}",
                f"Period covered: {period}",
                f"Search terms: {self.terms}",
                f"Model used: {self.llm_name}",
                "\n".join((source, *links)),
            )
        )

        return header
