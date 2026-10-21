import re
from pathlib import Path

from .config import MAX_UPLOAD_BYTES, TEXT_EXTENSIONS, UPLOAD_DIR

ALLOWED_EXTENSIONS = TEXT_EXTENSIONS | {'.pdf', '.docx'}
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class UploadError(ValueError):
    pass


def safe_filename(name: str) -> str:
    """Reduce a client-supplied name to a plain file name; reject anything that isn't an allowed type."""
    cleaned = _UNSAFE_CHARS.sub('_', Path(name.replace('\\', '/')).name).strip(' .')
    if not cleaned:
        raise UploadError('File name is empty.')
    suffix = Path(cleaned).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise UploadError(f'File type "{suffix or "(none)"}" is not supported.')
    return cleaned


def save_upload(name: str, data: bytes) -> dict:
    if not data:
        raise UploadError('File is empty.')
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadError(f'File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.')

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOAD_DIR / safe_filename(name)
    counter = 1
    while target.exists():  # never overwrite an existing file
        target = UPLOAD_DIR / f'{Path(safe_filename(name)).stem} ({counter}){target.suffix}'
        counter += 1

    target.write_bytes(data)
    return {'name': target.name, 'size': len(data), 'path': str(target)}


def list_uploads() -> list[dict]:
    if not UPLOAD_DIR.exists():
        return []
    files = [path for path in UPLOAD_DIR.iterdir() if path.is_file()]
    files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return [{'name': path.name, 'size': path.stat().st_size} for path in files]
