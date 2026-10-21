from . import embeddings, opensearch_client
from .config import VECTOR_CANDIDATES
from .generator import generate_answer
from .tokenizer import tokenize


def search_index(name: str, query: str, top_k: int = 5, generate: bool = False) -> dict:
    candidate_count = max(top_k, VECTOR_CANDIDATES)
    lexical_hits = _search_lexical(name, query, candidate_count)

    semantic_hits = []
    semantic_warning = None
    if embeddings.embedding_ready()[0]:
        try:
            query_vector = embeddings.embed_texts([query])[0]
            semantic_hits = _search_semantic(name, query_vector, candidate_count)
        except Exception as error:
            semantic_warning = str(error)

    results = _merge_hits(query, lexical_hits, semantic_hits, top_k)
    generation = generate_answer(query, results, enabled=generate)
    used_semantic = len(semantic_hits) > 0

    return {
        'query': query,
        'index': opensearch_client.sanitize_index_name(name),
        'top_k': top_k,
        'results': results,
        'answer': generation['answer'],
        'generation': generation,
        'retrieval': {
            'lexical_hits': len(lexical_hits),
            'semantic_hits': len(semantic_hits),
            'used_semantic': used_semantic,
            'semantic_warning': semantic_warning,
        },
    }


def _search_lexical(name: str, query: str, size: int) -> list[dict]:
    response = opensearch_client.search(
        name,
        {
            'size': size,
            '_source': ['chunk_id', 'source_type', 'uri', 'title', 'text', 'start_char', 'end_char'],
            'query': {
                'multi_match': {
                    'query': query,
                    'fields': ['title^2', 'text'],
                }
            },
        },
    )
    return response.get('hits', {}).get('hits', [])


def _search_semantic(name: str, query_vector: list[float], size: int) -> list[dict]:
    response = opensearch_client.search(
        name,
        {
            'size': size,
            '_source': ['chunk_id', 'source_type', 'uri', 'title', 'text', 'start_char', 'end_char'],
            'query': {
                'knn': {
                    'embedding': {
                        'vector': query_vector,
                        'k': size,
                    }
                }
            },
        },
    )
    return response.get('hits', {}).get('hits', [])


def _merge_hits(query: str, lexical_hits: list[dict], semantic_hits: list[dict], top_k: int) -> list[dict]:
    tokenized_query = tokenize(query)
    lexical_norm = _normalize_scores(lexical_hits)
    semantic_norm = _normalize_scores(semantic_hits)

    merged = {}
    lexical_weight = 0.65
    semantic_weight = 0.35

    for hit in lexical_hits:
        doc_id = hit.get('_id') or (hit.get('_source') or {}).get('chunk_id')
        if not doc_id:
            continue
        source = hit.get('_source') or {}
        lexical_score = lexical_norm.get(doc_id, 0.0)
        entry = merged.setdefault(doc_id, {'source': source, 'lexical_score': 0.0, 'semantic_score': 0.0})
        entry['lexical_score'] = max(entry['lexical_score'], lexical_score)

    for hit in semantic_hits:
        doc_id = hit.get('_id') or (hit.get('_source') or {}).get('chunk_id')
        if not doc_id:
            continue
        source = hit.get('_source') or {}
        semantic_score = semantic_norm.get(doc_id, 0.0)
        entry = merged.setdefault(doc_id, {'source': source, 'lexical_score': 0.0, 'semantic_score': 0.0})
        entry['semantic_score'] = max(entry['semantic_score'], semantic_score)

    ranked = sorted(
        merged.values(),
        key=lambda item: (item['lexical_score'] * lexical_weight) + (item['semantic_score'] * semantic_weight),
        reverse=True,
    )[:top_k]

    results = []
    for item in ranked:
        source = item['source']
        text = source.get('text', '')
        results.append(
            {
                **source,
                'score': round((item['lexical_score'] * lexical_weight) + (item['semantic_score'] * semantic_weight), 4),
                'lexical_score': round(item['lexical_score'], 4),
                'semantic_score': round(item['semantic_score'], 4),
                'snippet': make_snippet(text, tokenized_query),
            }
        )
    return results


def _normalize_scores(hits: list[dict]) -> dict:
    if not hits:
        return {}
    raw_scores = [(hit.get('_id'), float(hit.get('_score') or 0.0)) for hit in hits if hit.get('_id')]
    if not raw_scores:
        return {}
    values = [score for _, score in raw_scores]
    min_score = min(values)
    max_score = max(values)
    if max_score <= min_score:
        return {doc_id: 1.0 for doc_id, _ in raw_scores}
    return {
        doc_id: (score - min_score) / (max_score - min_score)
        for doc_id, score in raw_scores
    }


def make_snippet(text: str, query_tokens: list[str], window_words: int = 55) -> str:
    words = text.split()
    if not words:
        return ''
    lowered = [word.lower() for word in words]
    first_hit = 0

    for index, word in enumerate(lowered):
        if any(token in word for token in query_tokens):
            first_hit = index
            break

    start = max(0, first_hit - window_words // 2)
    end = min(len(words), start + window_words)
    prefix = '...' if start > 0 else ''
    suffix = '...' if end < len(words) else ''
    return f'{prefix}{" ".join(words[start:end])}{suffix}'

