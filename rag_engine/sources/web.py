import urllib.error
import urllib.request
from collections import deque
from collections.abc import Iterator
from urllib.parse import urldefrag, urljoin, urlparse

from ..config import WEB_MAX_BYTES, WEB_TIMEOUT, WEB_USER_AGENT
from ..extractors import parse_html
from ..models import Document
from .base import Source

_TEXT_TYPES = ('text/html', 'application/xhtml+xml', 'text/plain', 'text/markdown')


class WebSource(Source):
    """Fetch web pages. With depth > 0 it follows same-host links, up to max_pages in total."""

    type = 'web'

    def __init__(self, urls: list[str], depth: int = 0, max_pages: int = 20) -> None:
        super().__init__()
        if not urls:
            raise ValueError('Web source needs at least one URL.')
        for url in urls:
            _require_http(url)
        self.urls = urls
        self.depth = max(0, int(depth))
        self.max_pages = max(1, int(max_pages))

    @property
    def label(self) -> str:
        return ', '.join(self.urls)

    def documents(self) -> Iterator[Document]:
        seen: set[str] = set()
        queue = deque((urldefrag(url)[0], 0) for url in self.urls)
        fetched = 0

        while queue and fetched < self.max_pages:
            url, level = queue.popleft()
            if url in seen:
                continue
            seen.add(url)

            try:
                body, content_type = _fetch(url)
            except Exception:
                self.skipped += 1
                continue
            fetched += 1

            if 'html' in content_type:
                title, text, links = parse_html(body)
            else:
                title, text, links = '', body, []

            if text.strip():
                yield Document(
                    doc_id=f'web:{url}',
                    source_type=self.type,
                    uri=url,
                    title=title or url,
                    text=text,
                )
            else:
                self.skipped += 1

            if level < self.depth:
                host = urlparse(url).netloc
                for href in links:
                    target = urldefrag(urljoin(url, href))[0]
                    parsed = urlparse(target)
                    if parsed.scheme in {'http', 'https'} and parsed.netloc == host and target not in seen:
                        queue.append((target, level + 1))


def _require_http(url: str) -> None:
    if urlparse(url).scheme not in {'http', 'https'}:
        raise ValueError(f'Only http(s) URLs are supported: {url}')


def _fetch(url: str) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={'user-agent': WEB_USER_AGENT})
    with urllib.request.urlopen(request, timeout=WEB_TIMEOUT) as response:
        content_type = (response.headers.get_content_type() or '').lower()
        if content_type not in _TEXT_TYPES:
            raise ValueError(f'Unsupported content type: {content_type}')
        data = response.read(WEB_MAX_BYTES + 1)
        if len(data) > WEB_MAX_BYTES:
            raise ValueError('Response too large')
        charset = response.headers.get_content_charset() or 'utf-8'
    return data.decode(charset, errors='replace'), content_type
