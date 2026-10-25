import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue

        key, value = stripped.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env_file(PROJECT_ROOT / '.env')

CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '1500'))
CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', '250'))

# 'anthropic' (Claude) or 'openai-compatible' (OpenAI, Ollama, or any /chat/completions endpoint).
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'openai-compatible')
LLM_API_URL = os.getenv('LLM_API_URL', 'https://api.openai.com/v1/chat/completions')
if LLM_PROVIDER == 'anthropic':
    LLM_API_KEY = os.getenv('LLM_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
    LLM_MODEL = os.getenv('LLM_MODEL', 'claude-sonnet-5-5')
else:
    LLM_API_KEY = os.getenv('LLM_API_KEY') or os.getenv('OPENAI_API_KEY')
    LLM_MODEL = os.getenv('LLM_MODEL', 'gpt-4o-mini')
# Recent Claude models reject non-default temperatures, so it is only sent when set (or for other providers).
_temperature = os.getenv('LLM_TEMPERATURE') or (None if LLM_PROVIDER == 'anthropic' else '0.2')
LLM_TEMPERATURE = float(_temperature) if _temperature is not None else None
LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', '700'))
LLM_REQUIRE_API_KEY = os.getenv('LLM_REQUIRE_API_KEY', 'true').lower() in {'1', 'true', 'yes'}

EMBEDDING_PROVIDER = os.getenv('EMBEDDING_PROVIDER', 'openai')
EMBEDDING_API_URL = os.getenv('EMBEDDING_API_URL', 'https://api.openai.com/v1/embeddings')
# Deliberately no fallback to LLM_API_KEY: that key may belong to a different provider (e.g. Anthropic).
EMBEDDING_API_KEY = os.getenv('EMBEDDING_API_KEY') or os.getenv('OPENAI_API_KEY')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
EMBEDDING_DIMENSIONS = int(os.getenv('EMBEDDING_DIMENSIONS', '1536'))
EMBEDDING_ENABLED = os.getenv('EMBEDDING_ENABLED', 'true').lower() in {'1', 'true', 'yes'}
EMBEDDING_REQUIRE_API_KEY = os.getenv('EMBEDDING_REQUIRE_API_KEY', 'true').lower() in {'1', 'true', 'yes'}
EMBEDDING_BATCH_SIZE = int(os.getenv('EMBEDDING_BATCH_SIZE', '32'))
EMBEDDING_TIMEOUT = int(os.getenv('EMBEDDING_TIMEOUT', '45'))
VECTOR_CANDIDATES = int(os.getenv('VECTOR_CANDIDATES', '40'))

OPENSEARCH_URL = os.getenv('OPENSEARCH_URL', 'http://localhost:9200')
OPENSEARCH_USER = os.getenv('OPENSEARCH_USER', '')
OPENSEARCH_PASSWORD = os.getenv('OPENSEARCH_PASSWORD', '')
OPENSEARCH_VERIFY_TLS = os.getenv('OPENSEARCH_VERIFY_TLS', 'true').lower() in {'1', 'true', 'yes'}
OPENSEARCH_REQUEST_TIMEOUT = int(os.getenv('OPENSEARCH_REQUEST_TIMEOUT', '30'))
# The nmslib native library is not shipped in OpenSearch's Windows build (loading it crashes the node);
# lucene is pure Java. Note lucene allows at most 1024 vector dimensions in OpenSearch 2.13.
KNN_ENGINE = os.getenv('KNN_ENGINE') or ('lucene' if os.name == 'nt' else 'nmslib')
OPENSEARCH_BULK_BATCH =int(os.getenv('OPENSEARCH_BULK_BATCH', '200'))

# Deployment hardening. With RAG_API_KEY set, every endpoint except /health requires it
# (Bearer token, X-API-Key header, or the password of HTTP Basic auth so browsers get a login prompt).
# With RESTRICT_SOURCES on, /index only reads UPLOAD_DIR and public http(s) URLs (no arbitrary paths,
# no databases, no private/loopback addresses).
RAG_API_KEY = os.getenv('RAG_API_KEY', '')
RESTRICT_SOURCES = os.getenv('RESTRICT_SOURCES', 'false').lower() in {'1', 'true', 'yes'}

MAX_FILE_BYTES = int(os.getenv('MAX_FILE_BYTES', str(25 * 1024 * 1024)))

UPLOAD_DIR = Path(os.getenv('UPLOAD_DIR') or Path.home() / 'Desktop' / 'rag_sample_data' / 'docs')
MAX_UPLOAD_BYTES = int(os.getenv('MAX_UPLOAD_BYTES', str(50 * 1024 * 1024)))

WEB_TIMEOUT =int(os.getenv('WEB_TIMEOUT', '20'))
WEB_MAX_BYTES = int(os.getenv('WEB_MAX_BYTES', str(5 * 1024 * 1024)))
WEB_USER_AGENT = os.getenv('WEB_USER_AGENT', 'local-rag-search/1.0')

SKIP_DIRS = {
    '.git',
    '.hg',
    '.svn',
    '.venv',
    'venv',
    '__pycache__',
    'node_modules',
    'dist',
    'build',
    'target',
    '.next',
    '.angular',
}

TEXT_EXTENSIONS = {
    '.bat',
    '.c',
    '.cfg',
    '.conf',
    '.cql',
    '.cpp',
    '.cs',
    '.css',
    '.csv',
    '.dockerfile',
    '.env',
    '.go',
    '.h',
    '.htm',
    '.html',
    '.ini',
    '.java',
    '.js',
    '.json',
    '.jsx',
    '.log',
    '.md',
    '.ps1',
    '.py',
    '.rb',
    '.rs',
    '.sh',
    '.sql',
    '.toml',
    '.ts',
    '.tsx',
    '.txt',
    '.xml',
    '.yaml',
    '.yml',
}
