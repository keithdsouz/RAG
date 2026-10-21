from abc import ABC, abstractmethod
from collections.abc import Iterator

from ..models import Document


class Source(ABC):
    """A place content is pulled from. Subclasses yield Documents; the pipeline does the rest."""

    type: str = ''

    def __init__(self) -> None:
        self.skipped = 0

    @property
    @abstractmethod
    def label(self) -> str:
        """Short human-readable description used in index summaries."""

    @abstractmethod
    def documents(self) -> Iterator[Document]:
        """Yield every document in the source. Unreadable items should bump self.skipped, not raise."""
