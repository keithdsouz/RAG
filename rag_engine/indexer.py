from dataclasses import asdict

from . import embeddings, opensearch_client
from .chunking import chunk_document
from .config import CHUNK_OVERLAP, CHUNK_SIZE, OPENSEARCH_BULK_BATCH
from .models import Chunk
from .sources import Source


def build_index(
    name: str,
    sources: list[Source],
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> dict:
    """Rebuild index `name` from every source: documents -> chunks -> (embeddings) -> OpenSearch."""
    embedding_info = embeddings.embedding_metadata()
    embedding_enabled = embedding_info['enabled']
    embedding_warning = embedding_info.get('reason')

    opensearch_client.delete_index(name)
    opensearch_client.create_index(
        name,
        vector_dimensions=embedding_info['dimensions'] if embedding_enabled else None,
    )

    pending_actions: list[dict] = []
    source_summaries = []
    total_chunks = 0

    for source in sources:
        documents_indexed = 0
        chunks_indexed = 0

        for document in source.documents():
            chunks = chunk_document(document, chunk_size, chunk_overlap)
            if not chunks:
                source.skipped += 1
                continue
            documents_indexed += 1

            for chunk_batch in embeddings.batched(chunks):
                vectors = None
                if embedding_enabled:
                    try:
                        vectors = embeddings.embed_texts([chunk.text for chunk in chunk_batch])
                    except Exception as error:
                        embedding_enabled = False
                        embedding_warning = str(error)
                pending_actions.extend(_to_actions(chunk_batch, vectors))
                chunks_indexed += len(chunk_batch)

                if len(pending_actions) >= OPENSEARCH_BULK_BATCH:
                    _flush(name, pending_actions)
                    pending_actions = []

        total_chunks += chunks_indexed
        source_summaries.append(
            {
                'type': source.type,
                'source': source.label,
                'documents_indexed': documents_indexed,
                'chunks_indexed': chunks_indexed,
                'skipped': source.skipped,
            }
        )

    if pending_actions:
        _flush(name, pending_actions)

    opensearch_client.refresh(name)

    return {
        'index': opensearch_client.sanitize_index_name(name),
        'sources': source_summaries,
        'documents_indexed': sum(item['documents_indexed'] for item in source_summaries),
        'chunks_indexed': total_chunks,
        'opensearch_url': opensearch_client.OPENSEARCH_URL,
        'embedding': {
            **embedding_info,
            'enabled': embedding_enabled,
            'reason': embedding_warning,
        },
    }


def _to_actions(chunks: list[Chunk], vectors: list[list[float]] | None) -> list[dict]:
    actions = []
    for position, chunk in enumerate(chunks):
        source = asdict(chunk)
        if vectors is not None:
            source['embedding'] = vectors[position]
        actions.append({'_id': chunk.chunk_id, '_source': source})
    return actions


def _flush(name: str, actions: list[dict]) -> None:
    response = opensearch_client.bulk(name, actions)
    if response.get('errors'):
        first_error = None
        for item in response.get('items', []):
            error = item.get('index', {}).get('error')
            if error:
                first_error = error
                break
        raise opensearch_client.OpenSearchError(
            f'OpenSearch bulk indexing reported errors. First error: {first_error}'
        )
