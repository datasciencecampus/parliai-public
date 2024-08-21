"""Using LLMs to capture coverage of organisations, people or themes in UK political debate."""

from . import dates
from .readers import Debates, WrittenAnswers

__version__ = "0.0.1"

__all__ = [
    "__version__",
    "Debates",
    "WrittenAnswers",
    "dates",
]
