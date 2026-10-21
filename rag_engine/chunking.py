import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import CHUNK_OVERLAP, CHUNK_SIZE
from .models import Chunk, Document


def chunk_document(document: Document, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[Chunk]:
    """Split on paragraphs, then lines, sentences and words, so chunks end at natural boundaries.

    Sizes are in characters (the default 1500 is roughly 220 words of English).
    """
    text = _tidy(document.text)
    if not text:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=min(chunk_overlap, chunk_size // 2),
        add_start_index=True,
    )

    chunks = []
    for piece in splitter.create_documents([text]):
        start = piece.metadata['start_index']
        chunks.append(
            Chunk(
                chunk_id=f'{document.doc_id}#{len(chunks)}',
                source_type=document.source_type,
                uri=document.uri,
                title=document.title,
                text=piece.page_content,
                start_char=start,
                end_char=start + len(piece.page_content),
            )
        )
    return chunks


def _tidy(text: str) -> str:
    """Normalise whitespace but keep line breaks, which the splitter uses as boundaries."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r' ?\n ?', '\n', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()
