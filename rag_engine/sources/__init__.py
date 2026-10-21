import json
from pathlib import Path

from .base import Source
from .database import DatabaseSource
from .files import FileSource
from .web import WebSource

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
