import json
import urllib.error
import urllib.request

from .config import (
    EMBEDDING_API_KEY,
    EMBEDDING_API_URL,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_ENABLED,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    EMBEDDING_REQUIRE_API_KEY,
    EMBEDDING_TIMEOUT,
)


def embedding_ready() -> tuple[bool, str]:
    if not EMBEDDING_ENABLED:
        return False, 'Embedding generation is disabled by EMBEDDING_ENABLED=false.'

    if EMBEDDING_REQUIRE_API_KEY and not EMBEDDING_API_KEY:
        return (
            False,
            'EMBEDDING_API_KEY or OPENAI_API_KEY is not set. '
            'Set EMBEDDING_REQUIRE_API_KEY=false for local no-auth endpoints.',
        )

    if EMBEDDING_DIMENSIONS <= 0:
        return False, 'EMBEDDING_DIMENSIONS must be a positive integer.'

    return True, ''


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    ready, reason = embedding_ready()
    if not ready:
        raise RuntimeError(reason)

    payload = {
        'model': EMBEDDING_MODEL,
        'input': texts,
    }
    if EMBEDDING_MODEL.startswith('text-embedding-3'):
        payload['dimensions'] = EMBEDDING_DIMENSIONS

    data = json.dumps(payload).encode('utf-8')
    headers = {'content-type': 'application/json'}
    if EMBEDDING_API_KEY:
        headers['authorization'] = f'Bearer {EMBEDDING_API_KEY}'

    request = urllib.request.Request(
        EMBEDDING_API_URL,
        data=data,
        method='POST',
        headers=headers,
    )

    try:
        with urllib.request.urlopen(request, timeout=EMBEDDING_TIMEOUT) as response:
            body = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'Embedding request failed with HTTP {error.code}: {detail}') from error
    except urllib.error.URLError as error:
        raise RuntimeError(f'Embedding request could not reach {EMBEDDING_API_URL}: {error.reason}') from error

    data_rows = body.get('data') or []
    if len(data_rows) != len(texts):
        raise RuntimeError(
            f'Embedding response count mismatch. Expected {len(texts)}, got {len(data_rows)}.'
        )

    vectors = [None] * len(texts)
    for row in data_rows:
        idx = row.get('index')
        embedding = row.get('embedding')
        if idx is None or embedding is None:
            raise RuntimeError('Embedding response is missing index/embedding fields.')
        vectors[int(idx)] = embedding

    if any(vector is None for vector in vectors):
        raise RuntimeError('Embedding response is missing one or more vectors.')

    return vectors


def batched(items: list, size: int | None = None):
    batch_size = max(1, int(size or EMBEDDING_BATCH_SIZE))
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def embedding_metadata() -> dict:
    ready, reason = embedding_ready()
    return {
        'provider': EMBEDDING_PROVIDER,
        'model': EMBEDDING_MODEL,
        'dimensions': EMBEDDING_DIMENSIONS,
        'enabled': ready,
        'reason': reason or None,
    }

