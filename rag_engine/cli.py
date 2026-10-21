import argparse
import json
import sys
from pathlib import Path

from .config import CHUNK_OVERLAP, CHUNK_SIZE
from .indexer import build_index
from .opensearch_client import OpenSearchError
from .search import search_index
from .sources import build_sources, load_source_specs


def main() -> None:
    parser = argparse.ArgumentParser(description='Local RAG search engine')
    subparsers = parser.add_subparsers(dest='command', required=True)

    index_parser = subparsers.add_parser('index', help='Build an index from files, databases and/or web pages')
    index_parser.add_argument('--config', help='JSON file listing sources (see sources.example.json)')
    index_parser.add_argument('--path', action='append', default=[], help='File or folder to index (repeatable)')
    index_parser.add_argument('--url', action='append', default=[], help='Web page to index (repeatable)')
    index_parser.add_argument('--depth', type=int, default=0, help='Follow same-site links this many levels from --url')
    index_parser.add_argument('--max-pages', type=int, default=20, help='Page limit for --url crawling')
    index_parser.add_argument('--name', default='default', help='Index name')
    index_parser.add_argument('--chunk-size', type=int, default=CHUNK_SIZE, help='Chunk size in characters')
    index_parser.add_argument('--chunk-overlap', type=int, default=CHUNK_OVERLAP, help='Overlap in characters')

    search_parser = subparsers.add_parser('search', help='Search an existing index')
    search_parser.add_argument('--name', default='default', help='Index name')
    search_parser.add_argument('--query', required=True, help='Search query')
    search_parser.add_argument('--top-k', type=int, default=5)
    search_parser.add_argument('--generate', action='store_true', help='Use the configured LLM to generate an answer')

    args = parser.parse_args()

    try:
        if args.command == 'index':
            specs = _collect_specs(args)
            if not specs:
                parser.error('index needs at least one of --config, --path or --url')
            summary = build_index(
                name=args.name,
                sources=build_sources(specs),
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
            )
            print(json.dumps(summary, indent=2))
            return

        if args.command == 'search':
            result = search_index(args.name, args.query, args.top_k, generate=args.generate)
            print(json.dumps(result, indent=2))
            return
    except OpenSearchError as error:
        print(
            json.dumps(
                {
                    'error': str(error),
                    'hint': 'Ensure OpenSearch is running and reachable at OPENSEARCH_URL (default: http://localhost:9200).',
                    'quick_start': 'docker compose up -d',
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from error
    except (ValueError, FileNotFoundError, RuntimeError) as error:
        print(json.dumps({'error': str(error)}, indent=2), file=sys.stderr)
        raise SystemExit(1) from error


def _collect_specs(args) -> list[dict]:
    specs = load_source_specs(Path(args.config)) if args.config else []
    specs += [{'type': 'files', 'path': path} for path in args.path]
    if args.url:
        specs.append({'type': 'web', 'urls': args.url, 'depth': args.depth, 'max_pages': args.max_pages})
    return specs


if __name__ == '__main__':
    main()
