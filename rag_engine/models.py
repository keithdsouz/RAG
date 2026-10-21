from dataclasses import dataclass


@dataclass
class Document:
    """One unit of content produced by a source (a file, a database row, a web page)."""

    doc_id: str
    source_type: str
    uri: str
    title: str
    text: str


@dataclass
class Chunk:
    chunk_id: str
    source_type: str
    uri: str
    title: str
    text: str
    start_char: int
    end_char: int
