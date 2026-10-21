import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import opensearch_client
from .config import CHUNK_OVERLAP, CHUNK_SIZE, MAX_UPLOAD_BYTES, UPLOAD_DIR
from .indexer import build_index
from .search import search_index
from .sources import build_sources
from .uploads import UploadError, list_uploads, save_upload

STATIC_DIR = Path(__file__).parent / 'static'


class RagRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in {'/', '/index.html'}:
            self.respond_html((STATIC_DIR / 'index.html').read_bytes())
            return
        if parsed.path == '/health':
            self.respond(200, {'status': 'ok', 'service': 'local-rag-search'})
            return
        if parsed.path == '/indexes':
            try:
                self.respond(200, {'indexes': opensearch_client.list_indexes()})
            except opensearch_client.OpenSearchError as error:
                self.respond(503, {'message': f'OpenSearch is not reachable: {error}'})
            return
        if parsed.path == '/files':
            self.respond(200, {'directory': str(UPLOAD_DIR), 'files': list_uploads()})
            return
        self.respond(404, {'message': 'Not found'})

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == '/upload':
            self.handle_upload(parsed)
            return

        payload = self.read_json()

        try:
            if parsed.path == '/index':
                specs = list(payload.get('sources') or [])
                if payload.get('path'):
                    specs.append({'type': 'files', 'path': payload['path']})
                if not specs:
                    raise KeyError('sources')
                summary = build_index(
                    name=payload.get('index', 'default'),
                    sources=build_sources(specs),
                    chunk_size=int(payload.get('chunk_size', CHUNK_SIZE)),
                    chunk_overlap=int(payload.get('chunk_overlap', CHUNK_OVERLAP)),
                )
                self.respond(200, summary)
                return

            if parsed.path == '/search':
                result = search_index(
                    payload.get('index', 'default'),
                    payload['query'],
                    int(payload.get('top_k', 5)),
                    generate=bool(payload.get('generate', False)),
                )
                self.respond(200, result)
                return

            self.respond(404, {'message': 'Not found'})
        except KeyError as error:
            self.respond(400, {'message': f'Missing required field: {error}'})
        except FileNotFoundError as error:
            self.respond(404, {'message': str(error)})
        except ValueError as error:
            self.respond(400, {'message': str(error)})
        except opensearch_client.OpenSearchError as error:
            if opensearch_client.is_index_missing(error):
                name = payload.get('index', 'default')
                self.respond(
                    404,
                    {'message': f'Index "{name}" does not exist yet. Upload files and click "Index uploaded files" first, '
                                f'or pick an existing index from the list.'},
                )
            else:
                self.respond(502, {'message': str(error)})
        except Exception as error:
            self.respond(500, {'message': str(error)})

    def handle_upload(self, parsed):
        # Browsers can't send this header cross-site without a CORS preflight, which blocks drive-by uploads.
        if self.headers.get('x-requested-with') != 'rag-ui':
            self.respond(403, {'message': 'Missing X-Requested-With header.'})
            return

        length = int(self.headers.get('content-length', '0'))
        if length > MAX_UPLOAD_BYTES:
            self.respond(413, {'message': f'File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.'})
            return

        name = parse_qs(parsed.query).get('name', [''])[0]
        try:
            self.respond(200, save_upload(name, self.rfile.read(length)))
        except UploadError as error:
            self.respond(400, {'message': str(error)})

    def read_json(self):
        content_length = int(self.headers.get('content-length', '0'))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length).decode('utf-8')
        return json.loads(raw)

    def respond(self, status: int, payload: dict):
        body = json.dumps(payload, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('content-type', 'application/json')
        self.send_header('content-length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond_html(self, body: bytes):
        self.send_response(200)
        self.send_header('content-type', 'text/html; charset=utf-8')
        self.send_header('content-length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def main() -> None:
    parser = argparse.ArgumentParser(description='Local RAG HTTP server')
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=8500)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), RagRequestHandler)
    print(f'RAG search API listening on http://{args.host}:{args.port}')
    server.serve_forever()


if __name__ == '__main__':
    main()
