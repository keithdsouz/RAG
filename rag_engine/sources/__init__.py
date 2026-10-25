import json
from pathlib import Path

from .base import Source
from .database import DatabaseSource
from .files import FileSource
from ..config import RESTRICT_SOURCES, UPLOAD_DIR
from .web import WebSource, require_public_url

SOURCE_TYPES = {
    FileSource.type: FileSource,
    DatabaseSource.type: DatabaseSource,
    WebSource.type: WebSource,
}


def build_source(spec: dict) -> Source:
    """Create a Source from a config dict such as {"type": "files", "path": "./docs"}."""
    spec = dict(spec)
    source_type = spec.pop('type', None)
    source_class = SOURCE_TYPES.get(source_type)
    if source_class is None:
        raise ValueError(f'Unknown source type "{source_type}". Expected one of: {", ".join(SOURCE_TYPES)}.')
    try:
        return source_class(**spec)
    except TypeError as error:
        raise ValueError(f'Invalid options for "{source_type}" source: {error}') from error


def build_sources(specs: list[dict]) -> list[Source]:
    return [build_source(spec) for spec in specs]


def validate_specs(specs: list[dict]) -> None:
    """In RESTRICT_SOURCES mode, only allow uploaded files and public web pages."""
    if not RESTRICT_SOURCES:
        return
    root = UPLOAD_DIR.resolve()
    for spec in specs:
        source_type = spec.get('type')
        if source_type == 'files':
            path = Path(str(spec.get('path', ''))).expanduser().resolve()
            if path != root and root not in path.parents:
                raise ValueError('Only the upload directory can be indexed on this server.')
        elif source_type == 'web':
            for url in spec.get('urls') or []:
                require_public_url(url)
        else:
            raise ValueError(f'Source type "{source_type}" is disabled on this server.')


def load_source_specs(config_path: Path) -> list[dict]:
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    specs = config.get('sources') if isinstance(config, dict) else config
    if not isinstance(specs, list) or not specs:
        raise ValueError('Sources config must be a non-empty list, or an object with a "sources" list.')
    return specs


__all__ = [
    'DatabaseSource',
    'FileSource',
    'SOURCE_TYPES',
    'Source',
    'WebSource',
    'build_source',
    'build_sources',
    'load_source_specs',
]
