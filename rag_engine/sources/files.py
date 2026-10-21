from collections.abc import Iterator
from pathlib import Path

from ..config import MAX_FILE_BYTES, SKIP_DIRS
from ..extractors import extract_text
from ..models import Document
from .base import Source


class FileSource(Source):
    type = 'files'

    def __init__(self, path: str) -> None:
        super().__init__()
        self.root = Path(path).expanduser().resolve()
        if not self.root.exists():
            raise FileNotFoundError(f'Path does not exist: {self.root}')

    @property
    def label(self) -> str:
        return str(self.root)

    def documents(self) -> Iterator[Document]:
        paths = [self.root] if self.root.is_file() else self._walk()
        for path in paths:
            try:
                text = extract_text(path)
            except Exception:
                self.skipped += 1
                continue
            if not text.strip():
                self.skipped += 1
                continue
            yield Document(
                doc_id=f'file:{path.as_posix()}',
                source_type=self.type,
                uri=str(path),
                title=path.name,
                text=text,
            )

    def _walk(self) -> Iterator[Path]:
        for path in self.root.rglob('*'):
            if path.is_dir():
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            yield path
