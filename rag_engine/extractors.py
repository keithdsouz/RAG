import csv
import importlib
import json
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree


class _HtmlTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.links = []
        self.title = ''
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self._skip_depth += 1
        elif tag == 'title':
            self._in_title = True
        elif tag == 'a':
            href = dict(attrs).get('href')
            if href:
                self.links.append(href)

    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag == 'title':
            self._in_title = False

    def handle_data(self, data):
        cleaned = data.strip()
        if not cleaned or self._skip_depth:
            return
        if self._in_title:
            self.title = f'{self.title} {cleaned}'.strip()
        else:
            self.parts.append(cleaned)

    def text(self):
        return '\n'.join(self.parts)


def parse_html(raw: str) -> tuple[str, str, list[str]]:
    """Return (title, body text, hrefs) for an HTML string."""
    parser = _HtmlTextExtractor()
    parser.feed(raw)
    return parser.title, parser.text(), parser.links


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix == '.json':
        return _extract_json(path)
    if suffix == '.csv':
        return _extract_csv(path)
    if suffix in {'.html', '.htm'}:
        return _extract_html(path)
    if suffix == '.xml':
        return _extract_xml(path)
    if suffix == '.pdf':
        return _extract_pdf(path)
    if suffix == '.docx':
        return _extract_docx(path)
    return _read_text(path)


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    if _looks_binary(data):
        return ''

    for encoding in ('utf-8', 'utf-16', 'latin-1'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue

    return ''


def _extract_json(path: Path) -> str:
    raw = _read_text(path)
    if not raw:
        return ''

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw

    return _flatten_json(parsed)


def _flatten_json(value, prefix='') -> str:
    lines = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_prefix = f'{prefix}.{key}' if prefix else str(key)
            lines.append(_flatten_json(item, child_prefix))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            child_prefix = f'{prefix}[{index}]'
            lines.append(_flatten_json(item, child_prefix))
    else:
        lines.append(f'{prefix}: {value}')

    return '\n'.join(line for line in lines if line)


def _extract_csv(path: Path) -> str:
    raw = _read_text(path)
    if not raw:
        return ''

    rows = []
    for row in csv.reader(raw.splitlines()):
        rows.append(' | '.join(cell.strip() for cell in row))
    return '\n'.join(rows)


def _extract_html(path: Path) -> str:
    return parse_html(_read_text(path))[1]


def _extract_xml(path: Path) -> str:
    raw = _read_text(path)
    if not raw:
        return ''

    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        return raw

    lines = []
    for element in root.iter():
        text = (element.text or '').strip()
        if text:
            lines.append(f'{element.tag}: {text}')
    return '\n'.join(lines)


def _extract_pdf(path: Path) -> str:
    try:
        pypdf = importlib.import_module('pypdf')
    except ImportError:
        return ''

    reader = pypdf.PdfReader(str(path))
    return '\n'.join(page.extract_text() or '' for page in reader.pages)


def _extract_docx(path: Path) -> str:
    try:
        docx_module = importlib.import_module('docx')
    except ImportError:
        return ''

    document = docx_module.Document(str(path))
    return '\n'.join(paragraph.text for paragraph in document.paragraphs)


def _looks_binary(data: bytes) -> bool:
    if not data:
        return False
    sample = data[:4096]
    if b'\x00' in sample:
        return True
    text_chars = bytes(range(32, 127)) + b'\n\r\t\b'
    non_text = sample.translate(None, text_chars)
    return len(non_text) / max(1, len(sample)) > 0.3

