"""Tools to summarise ONS activity in Parliament via TheyWorkForYou."""

import datetime as dt
import re
import warnings
from typing import Iterable

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
from langchain_community.chat_models import ChatOllama

from .base import BaseReader


class Debates(BaseReader):
    """
    Class to summarise ONS activity in parliamentary debate.

    All of the content from which we extract relevant activity comes
    from the [TheyWorkForYou](https://theyworkforyou.com) organisation's
    website.

    Parameters
    ----------
    urls : list[str]
        List of URLs from which to gather content. These must be
        top-level TheyWorkForYou links for bulletins such as
        `https://theyworkforyou.com/debates`.
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
        available to `langchain_google_vertexai.ChatVertexAI`. If not
        specified, the reader uses `gemini-1.0-pro-001`.
    """

    _default_config = "debates.toml"
    _speech_prefix = "debate-speech__"
    _source = (
        "transcripts taken from "
        "[TheyWorkForYou](https://www.theyworkforyou.com/)"
    )

    def _list_latest_pages(self) -> list[str]:
        """
        List all URLs associated with the days required.

        Returns
        -------
        pages : list[str]
            List of parliamentary URLs in time scope.
        """
        pages: list[str] = []
        for url in self.urls:
            pages.extend(f"{url}/?d={date.isoformat()}" for date in self.dates)

        return pages

    def _remove_multi_link_statements(
        self, latest_pages: list[str]
    ) -> list[str]:
        """Remove all .mh links.

        Note that these linked pages filter to departmental
        pages. These individual statements are already listed
        in the daily pages. This function mitigates that
        potential duplication.

        Parameters
        ----------
        latest_pages : list[str]
            List of all current URLs, including .mh pages.

        Returns
        -------
        latest_pages : list[str]
            Updated list of URLs.
        """
        suffix = ".mh"
        latest_pages = [
            page for page in latest_pages if not page.endswith(suffix)
        ]
        return latest_pages

    def retrieve_latest_entries(self) -> list[str]:
        """
        Pull down all the individual parliamentary entry pages.

        Returns
        -------
        entries : list[str]
            List of individual parliamentary entry URLs.
        """

        latest_pages = self._list_latest_pages()

        entries = []
        for url in latest_pages:
            soup = self.get(url, check=False)
            if soup is not None:
                links = soup.find_all(
                    "a", attrs={"class": "business-list__title"}
                )
                for link in links:
                    entries.append(
                        f"https://theyworkforyou.com{link.get('href')}"
                    )

        # remove .mh multi-statement references
        entries = self._remove_multi_link_statements(entries)

        return entries

    def _read_metadata(self, url: str, soup: BeautifulSoup) -> dict:
        """
        Extract the title, date, and storage metadata for a debate.

        In particular, we extract the following as strings:

        - `cat`: category of parliamentary debate. One of `lords`,
          `debates`, `whall`, `wms`, `wrans`. URL.
        - `idx`: index of the debate entry. URL.
        - `title`: plain-text title of the debate. Soup.
        - `date`: date of the debate in `YYYY-MM-DD` format. URL.

        Parameters
        ----------
        url : str
            URL of the entry.
        soup : bs4.BeautifulSoup
            HTML soup of the entry.

        Returns
        -------
        metadata : dict
            Dictionary containing the debate metadata.
        """

        *_, cat, idx = url.replace("?id=", "").split("/")

        block = soup.find("title").get_text()
        title = re.search(r"^.*(?=:\s*\d{1,2} \w{3} \d{4})", block).group()
        date = re.search(r"(?<=(\=))\d{4}-\d{2}-\d{2}(?=[\w\.])", url).group()

        metadata = dict(cat=cat, idx=idx, title=title, date=date, url=url)

        return metadata

    def _read_contents(self, soup: BeautifulSoup) -> dict:
        """
        Extract the text from HTML soup in a compact format.

        We convert the transcript into blocks like so:

        ```
        {
          "speeches": [
            {
              "name": "Sir Henry Wilde",
              "position": "Permanent Under-Secretary for Health",
              "text": "The ONS provided daily, robust statistics to
                       support leaders and health services to plan
                       during the pandemic."
            },
            {
              "name": "Lord Jackson of Richmond",
              "position": "Lord Speaker for Education",
              "text": "The Office for National Statistics would welcome
                       a more transparent sharing of statistics and data
                       about our children's attainment nationally."
            }
          ]
        }
        ```

        Parameters
        ----------
        soup : bs4.BeautifulSoup
            HTML soup of a webpage.

        Returns
        -------
        text : dict
            Dictionary with a single entry (`text`) containing a
            transcript of the debate in plain-text format.
        """

        raw_speeches = soup.find_all(
            "div", attrs={"class": f"{self._speech_prefix}speaker-and-content"}
        )

        speeches = map(self._process_speech, raw_speeches)

        return {"speeches": list(speeches)}

    def _process_speech(self, speech: BeautifulSoup) -> dict:
        """
        Process a speech block by extracting its details and contents.

        This function returns a compact dictionary form of the speech
        and its details. If the speech cannot be attributed to someone,
        the dictionary will be `None` for the speaker details.

        Parameters
        ----------
        speech : bs4.BeautifulSoup
            HTML soup of the speech block.

        Returns
        -------
        processed : dict
            Dictionary containing the speech components: speaker name,
            speaker position, speaker URL, and the text of the speech.
        """

        name, position, url = self._extract_speaker_details(speech)
        text = self._extract_speech_text(speech)

        return {"name": name, "position": position, "url": url, "text": text}

    def _extract_speaker_details(
        self, speech: BeautifulSoup
    ) -> tuple[None | str, None | str, None | str]:
        """
        Get the name, position, and URL of the speaker.

        Parameters
        ----------
        speech : bs4.BeautifulSoup
            HTML soup of the speech block.

        Returns
        -------
        name : None | str
            Speaker name if the speech can be attributed.
        position : None | str
            Position of the attributed speaker as it appears on TWFY.
        url : None | str
            URL on TWFY of the attributed speaker.
        """

        prefix = self._speech_prefix
        speaker = speech.find("h2", attrs={"class": f"{prefix}speaker"})

        name, position, url = None, None, None
        if isinstance(speaker, Tag):
            name_block = speaker.find(
                "strong", attrs={"class": f"{prefix}speaker__name"}
            )
            position_block = speaker.find(
                "small", attrs={"class": f"{prefix}speaker__position"}
            )
            name, position = map(
                self._get_detail_text, (name_block, position_block)
            )

            href_block = speaker.find(
                lambda tag: tag.name == "a" and "href" in tag.attrs
            )
            url = (
                f"https://theyworkforyou.com{href_block['href']}"
                if href_block
                else None
            )

        return name, position, url

    @staticmethod
    def _get_detail_text(detail: None | Tag | NavigableString) -> None | str:
        """
        Try to get the text of a speaker detail.

        The usual behaviour for this function (getting the text of a
        detail) should only fail when the detail is actually `None` and
        was not found in `_extract_speaker_details()`. In this scenario,
        we catch the `AttributeError` and return the detail as it was,
        i.e. as `None`.

        Parameters
        ----------
        detail : None | bs4.Tag
            The detail from which to extract text. If all is well, this
            is a `bs4.Tag` instance. If not, it should be `None`.

        Returns
        -------
        detail : None | str
            Text from the detail or `None`.
        """

        try:
            return detail.get_text()
        except AttributeError:
            pass

    def _extract_speech_text(self, speech: BeautifulSoup) -> str:
        """Get the text of a speech back."""

        text = speech.find(
            "div", attrs={"class": f"{self._speech_prefix}content"}
        )

        return text.get_text().strip()

    def analyse(self, page: dict) -> dict:
        """
        Analyse all relevant speeches on a page.

        Parameters
        ----------
        page : dict
            Dictionary format of a debate transcript.

        Returns
        -------
        page : dict
            Debate transcript with LLM responses attached.
        """

        for speech in page["speeches"]:
            if self.check_contains_terms(speech["text"]):
                speech = super().analyse(speech)

        return page

    def parliament_label(self, url: str) -> str:
        """Label debates with parliament name.

        Parameters
        ----------
        url : str
            URL of debate content.

        Returns
        -------
        parliament_tag : str
            Name of parliament/chamber in which debate occurred.
        """

        parli_labels = {
            "debates": "House of Commons",
            "lords": "House of Lords",
            "whall": "Westminster Hall",
            "wms": "UK Ministerial statement",
            "senedd": "Senedd / Welsh Parliament",
            "sp": "Scottish Parliament",
            "ni": "Northern Ireland Assembly",
        }

        tag = re.search(r"(?<=theyworkforyou.com\/)\w+(?=\/\?id\=)", url)
        if tag is None:
            return "Unclassified"

        return parli_labels[tag.group()]

    def render(self, transcript: dict) -> str:
        """
        Convert an entry's transcript into Markdown for publishing.

        Parameters
        ----------
        transcript : dict
            Dictionary containing all the details of the entry.

        Returns
        -------
        summary : str
            Stylised summary of the entry in Markdown syntax.
        """

        label = self.parliament_label(transcript["url"])

        title = f"## {label}: [{transcript['title']}]({transcript['url']})"
        processed = []
        for speech in transcript["speeches"]:
            if "response" in speech:
                if speech["name"]:
                    speaker = (
                        f"### [{speech['name']}]({speech['url']})"
                        f" ({speech['position']})"
                    )
                    processed.append(
                        "\n\n".join((speaker, speech["response"]))
                    )
                else:
                    # if no speaker, return placeholder and response
                    speaker = "### No speaker assigned"
                    processed.append(
                        "\n\n".join((speaker, speech["response"]))
                    )

        return "\n\n".join((title, *processed))


class WrittenAnswers(Debates):
    """
    Class to summarise ONS activity in written answers from Parliament.

    Like its parent class, this reader extracts relevant activity
    from TheyWorkForYou.

    Parameters
    ----------
    urls : list[str]
        List of URLs from which to gather content. Currently, only
        `https://theyworkforyou.com/wrans` is supported.
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

    Raises
    ------
    ValueError
        If `urls` contains an unsupported URL.
    """

    _default_config = "wrans.toml"
    _supported_urls = ["https://www.theyworkforyou.com/wrans"]

    def __init__(
        self,
        urls: list[str],
        terms: None | Iterable[str] = None,
        dates: None | list[dt.date] = None,
        outdir: str = "out",
        prompt: None | str = None,
        llm_name: None | str = None,
        llm: None | ChatOllama = None,
    ) -> None:
        if not isinstance(urls, list) or not set(urls).issubset(
            self._supported_urls
        ):
            supported = ", ".join(self._supported_urls)
            warnings.warn(
                "URLs must be a list of supported endpoints.\n"
                f"Currently, the only acceptable URLs are: {supported}",
                UserWarning,
            )

        super().__init__(
            urls,
            terms,
            dates,
            outdir,
            prompt,
            llm_name,
            llm,
        )

    def _read_metadata(self, url: str, soup: BeautifulSoup) -> dict:
        """
        Extract all metadata on a written answer to Parliament.

        These metadata comprise the following:

        - question title
        - ID of the entry
        - date of question
        - intended recipient (e.g. Cabinet Office, DfE, etc.)
        - date of answer

        We do not collect the category since they are all written
        answers with category `wrans`.

        Parameters
        ----------
        url : str
            URL of the entry.
        soup : bs4.BeautifulSoup
            HTML soup of the entry.

        Returns
        -------
        metadata : dict
            Dictionary containing the entry's metadat listed above.
        """

        metadata = super()._read_metadata(url, soup)

        recipient, on = self._read_metadata_from_lead(soup)
        metadata = dict(**metadata, recipient=recipient, answered=on)

        return metadata

    @staticmethod
    def _read_metadata_from_lead(soup: BeautifulSoup) -> tuple[str, str]:
        """
        Extract the date of answer and recipient from a lead block.

        Parameters
        ----------
        soup : bs4.BeautifulSoup
            HTML soup of the entry containing the `lead` block.

        Returns
        -------
        recipient : str
            Name of the intended recipient of the question.
        on : str
            Date question was answered in YYYY-MM-DD format.
        """

        lead = soup.find("p", attrs={"class": "lead"}).get_text().strip()

        recipient = re.search(r"^.*(?= written question)", lead).group()

        on = re.search(r"(?<=on)\s+\d{1,2} \w+ \d{4}", lead).group().strip()
        on = dt.datetime.strptime(on, "%d %B %Y").date().isoformat()

        return recipient, on

    def _read_contents(self, soup: BeautifulSoup) -> dict:
        """
        Extract the text of the written answer.

        Parameters
        ----------
        soup : bs4.BeautifulSoup
            HTML soup of the entry.

        Returns
        -------
        text : dict
            Dictionary with one entry (`answer`) containing the
            plain-text response to the question.
        """

        contents = super()._read_contents(soup)
        *questions, answer = contents["speeches"]

        return {"questions": questions, "answer": answer}

    def analyse(self, page: dict) -> dict:
        """
        Analyse the answer to a written question and answer entry.

        If the answer does not contain any search terms, there is no
        need to invoke the LLM.

        Parameters
        ----------
        page : dict
            Dictionary format of a written answer transcript.

        Returns
        -------
        page : dict
            Debate transcript with LLM responses attached.
        """

        if self.check_contains_terms(page["answer"]["text"]):
            page["answer"] = super(Debates, self).analyse(page["answer"])

        return page

    def render(self, transcript: dict) -> str:
        """
        Convert an entry's transcript into Markdown for publishing.

        Parameters
        ----------
        transcript : dict
            Dictionary containing all the details of an entry.

        Returns
        -------
        summary : str
            Stylised summary of the entry in Markdown syntax.
        """

        title = f"## [{transcript['title']}]({transcript['url']})"

        questions = []
        for question in transcript["questions"]:
            question_title = (
                "### Asked by "
                f"[{question['name']}]({question['url']}) "
                f"({question['position']})"
            )
            question_text = question["text"].strip()
            questions.append("\n\n".join((question_title, question_text)))

        addressed = f"Addressed to: {transcript['recipient']}."
        asked = f"Asked on: {transcript['date']}."
        answered = f"Answered on: {transcript['answered']}."
        metadata = " ".join((addressed, asked, answered))

        answer = self._render_answer(transcript["answer"])

        summary = "\n\n".join((title, *questions, metadata, answer))

        return summary

    @staticmethod
    def _render_answer(answer: dict) -> str:
        """
        Process a plain-text answer into something for a summary.

        If the answer mentions any search terms, we send it to the LLM
        for extraction. Otherwise, we say it makes no mention.

        Parameters
        ----------
        answer : dict
            Dictionary format for an answer.

        Returns
        -------
        processed : str
            A stylised answer block for adding to a Markdown summary.
        """

        title = (
            f"### Answered by [{answer['name']}]({answer['url']})"
            f" ({answer['position']})"
        )

        response = answer.get(
            "response", "Answer does not mention any search terms."
        )

        processed = "\n\n".join((title, response))

        return processed
