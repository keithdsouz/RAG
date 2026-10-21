import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from .config import (
    KNN_ENGINE,
    OPENSEARCH_PASSWORD,
    OPENSEARCH_REQUEST_TIMEOUT,
    OPENSEARCH_URL,
    OPENSEARCH_USER,
    OPENSEARCH_VERIFY_TLS,
)


class OpenSearchError(RuntimeError):
    pass


def sanitize_index_name(name: str) -> str:
    cleaned = re.sub(r'[^a-z0-9_\-]+', '-', name.lower()).strip('-_')
    if not cleaned:
        raise ValueError('Index name is empty after sanitization.')
    if cleaned[0] in '-_+':
        cleaned = f'idx-{cleaned}'
    return cleaned[:255]


def create_index(name: str, mapping: dict | None = None, vector_dimensions: int | None = None) -> dict:
    body = mapping or default_mapping(vector_dimensions=vector_dimensions)
    return _request('PUT', f'/{sanitize_index_name(name)}', body=body)


def delete_index(name: str) -> dict:
    try:
        return _request('DELETE', f'/{sanitize_index_name(name)}')
    except OpenSearchError as error:
        if '404' in str(error):
            return {'acknowledged': True, 'already_absent': True}
        raise


def bulk(name: str, actions: list[dict]) -> dict:
    if not actions:
        return {'errors': False, 'items': []}

    lines = []
    for action in actions:
        lines.append(json.dumps({'index': {'_id': action['_id']}}))
        lines.append(json.dumps(action['_source']))
    payload = ('\n'.join(lines) + '\n').encode('utf-8')

    return _request(
        'POST',
        f'/{sanitize_index_name(name)}/_bulk',
        raw_body=payload,
        content_type='application/x-ndjson',
    )


def list_indexes() -> list[dict]:
    """User indexes with their chunk counts (OpenSearch's own dot-prefixed indexes are hidden)."""
    rows = _request('GET', '/_cat/indices?format=json&h=index,docs.count')
    return sorted(
        ({'name': row['index'], 'chunks': int(row.get('docs.count') or 0)} for row in rows if not row['index'].startswith('.')),
        key=lambda item: item['name'],
    )


def is_index_missing(error: Exception) -> bool:
    return 'index_not_found_exception' in str(error)


def refresh(name: str) -> dict:
    return _request('POST', f'/{sanitize_index_name(name)}/_refresh')


def search(name: str, query_body: dict) -> dict:
    return _request('POST', f'/{sanitize_index_name(name)}/_search', body=query_body)


def default_mapping(vector_dimensions: int | None = None) -> dict:
    properties = {
        'source_type': {'type': 'keyword'},
        'uri': {'type': 'keyword'},
        'title': {'type': 'text', 'analyzer': 'rag_text'},
        'text': {'type': 'text', 'analyzer': 'rag_text'},
        'chunk_id': {'type': 'keyword'},
        'start_char': {'type': 'integer'},
        'end_char': {'type': 'integer'},
    }
    if vector_dimensions:
        properties['embedding'] = {
            'type': 'knn_vector',
            'dimension': vector_dimensions,
            'method': {
                'name': 'hnsw',
                'space_type': 'cosinesimil',
                'engine': KNN_ENGINE,
            },
        }

    index_settings = {
        'number_of_shards': 1,
        'number_of_replicas': 0,
        'similarity': {'default': {'type': 'BM25'}},
    }
    if vector_dimensions:
        # Without this flag OpenSearch stores vectors but builds no HNSW graph, so k-NN queries return nothing.
        index_settings['knn'] = True

    return {
        'settings': {
            'index': index_settings,
            'analysis': {
                'analyzer': {
                    'rag_text': {
                        'type': 'standard',
                        'stopwords': '_english_',
                    }
                }
            },
        },
        'mappings': {
            'properties': properties
        },
    }


def _request(
    method: str,
    path: str,
    body: dict | None = None,
    raw_body: bytes | None = None,
    content_type: str = 'application/json',
) -> dict:
    url = OPENSEARCH_URL.rstrip('/') + path
    headers = {'content-type': content_type, 'accept': 'application/json'}

    if OPENSEARCH_USER and OPENSEARCH_PASSWORD:
        token = base64.b64encode(f'{OPENSEARCH_USER}:{OPENSEARCH_PASSWORD}'.encode('utf-8')).decode('ascii')
        headers['authorization'] = f'Basic {token}'

    data = raw_body if raw_body is not None else (json.dumps(body).encode('utf-8') if body is not None else None)
    request = urllib.request.Request(url, data=data, method=method, headers=headers)

    context = None
    if url.startswith('https://') and not OPENSEARCH_VERIFY_TLS:
        import ssl

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(request, timeout=OPENSEARCH_REQUEST_TIMEOUT, context=context) as response:
            raw = response.read()
            if not raw:
                return {}
            return json.loads(raw.decode('utf-8'))
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', errors='replace')
        raise OpenSearchError(f'{method} {path} failed with HTTP {error.code}: {detail}') from error
    except urllib.error.URLError as error:
        raise OpenSearchError(f'{method} {path} could not reach {OPENSEARCH_URL}: {error.reason}') from error
