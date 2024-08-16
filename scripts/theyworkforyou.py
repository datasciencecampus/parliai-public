"""Script for extracting parliamentary content from TheyWorkForYou."""

import argparse
import datetime as dt
import os

import tqdm

from parliai_public import dates
from parliai_public.readers import Debates, WrittenAnswers


def create_reader(
    reader_class: type[Debates] | type[WrittenAnswers],
    toml: None | str = None,
    date_list: None | list[dt.date] = None,
    llm_name: None | str = None,
):
    """
    Create an instance of a reader class.

    Parameters
    ----------
    reader_class : type[Debates] | type[WrittenAnswers]
        Class to instantiate.
    toml : str, optional
        Path to TOML configuration file. If not specified, the
        default for the class is used.
    date_list : list[dt.date], optional
        List of dates to cover. If not specified, the default
        for the reader class is used.
    llm_name : str, optional
        Name of model (only locally-installed Ollama-based LLMs
        in this demo). 'gemma' by default.

    Returns
    -------
    reader : Debates | WrittenAnswers
        An instantiated reader.
    """

    reader = reader_class.from_toml(toml)
    if date_list:
        reader.dates = date_list
    reader.llm_name = "gemma" if llm_name is None else llm_name

    return reader


def make_summary(
    reader: Debates | WrittenAnswers,
    header: str,
    save: bool = True,
) -> str:
    """
    Collect and summarise the latest entries in Parliament.

    Users have a choice for how they would like to define "latest":

    1. Providing a specific date.
    2. Defining a reporting period with start and end dates.
    3. Specifying a date and a number of days to look back over
       (inclusive of the provided end date).
    4. Providing nothing will have the reader only look at yesterday.

    Parameters
    ----------
    reader : Debates | WrittenAnswers
        Reader to use in analysis.
    header : str
        Section header for the reader.
    save : bool, default=True
        Whether to save the collected and analysed transcripts.

    Returns
    -------
    summary : str
        Stylised summary of entries in Markdown syntax.
    """

    entries = reader.retrieve_latest_entries()
    sections = []
    content = ""

    if entries:
        width = max(map(len, entries))
        for entry in (pbar := tqdm.tqdm(entries)):
            pbar.set_description(f"Processing {entry.ljust(width)}")
            page = reader.read(entry)
            if page:
                analysed = reader.analyse(page)
                rendering = reader.render(analysed)
                sections.append(rendering)
                if save:
                    reader.save(analysed)

        content = "\n\n".join(sections)

    if content == "":
        content = "No relevant content found for this period."

    summary = "\n\n".join((header, content))

    return summary


def main():
    """Summarise the latest communications in Parliament."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--start",
        type=str,
        required=False,
        help="start of reporting period (default format YYYY-MM-DD)",
    )
    parser.add_argument(
        "-d",
        "--end",
        type=str,
        required=False,
        help="end of reporting period (default format YYYY-MM-DD)",
    )
    parser.add_argument(
        "-n",
        "--window",
        type=int,
        required=False,
        help="length of reporting period (inclusive of `end`)",
    )
    parser.add_argument(
        "-f",
        "--form",
        type=str,
        default="%Y-%m-%d",
        help="date string format using directive notation (default %Y-%m-%d)",
    )
    parser.add_argument(
        "--debates-toml",
        type=str,
        required=False,
        help="path to debates TOML configuration file",
    )
    parser.add_argument(
        "--written-toml",
        type=str,
        required=False,
        help="path to written answers TOML configuration file",
    )
    parser.add_argument(
        "-w",
        "--weekly",
        required=False,
        action="store_true",
        help="trigger a weekly report from today",
    )
    parser.add_argument(
        "--no-save",
        required=False,
        action="store_true",
        help="do not save data from collected pages",
    )
    args = vars(parser.parse_args())

    start = args.get("start")
    end = args.get("end")
    window = args.get("window")
    form = args["form"]
    save = not args["no_save"]

    if args.get("weekly"):
        start, end, window = None, None, 8

    date_list = None
    if start or end or window:
        date_list = dates.list_dates(start, end, window, form)

    debates = create_reader(
        reader_class=Debates,
        toml=args.get("debates_toml"),
        date_list=date_list,
    )
    written = create_reader(
        reader_class=WrittenAnswers,
        toml=args.get("written_toml"),
        date_list=date_list,
    )

    # TODO: refactor to single LLM instantiation
    debates.instantiate_llm()
    written.instantiate_llm()

    debates.make_outdir()
    written.outdir = debates.outdir

    summary = "\n\n".join(
        (
            debates.make_header(urls=debates.urls + written.urls),
            make_summary(debates, "# Debates", save),
            make_summary(
                written, "# Written answers (UK Parliament only)", save
            ),
        )
    )

    print("Saving summary...")
    with open(os.path.join(debates.outdir, "summary.md"), "w") as f:
        f.write(summary)

    print("Done! ✅")


if __name__ == "__main__":
    main()
