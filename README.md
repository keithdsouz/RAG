# Local RAG Search Engine

A lightweight RAG-based search engine over multiple sources: files, databases and web pages.

It runs locally. Most of it is plain standard-library Python; [LangChain](https://python.langchain.com) handles chunking and LLM answer generation.

- Pulls documents from pluggable sources (files, SQL databases, web pages)
- Extracts text from common structured and unstructured formats
- Splits documents into chunks with LangChain's `RecursiveCharacterTextSplitter` (paragraph and sentence aware)
- Stores chunks in OpenSearch with BM25 lexical retrieval
- Supports embeddings (local Ollama or OpenAI-compatible) for semantic retrieval
- Returns source-grounded snippets
- Generates answers with a LangChain chat model (Claude, OpenAI or any OpenAI-compatible endpoint)
- Provides a web page, a CLI and an HTTP API

## Supported Files

Built-in extraction works for:

- Text/code/config: `.txt`, `.md`, `.py`, `.js`, `.ts`, `.html`, `.css`, `.json`, `.xml`, `.yaml`, `.yml`, `.cql`, `.sql`, `.log`, `.csv`
- Unknown extensions are attempted as UTF-8/Latin-1 text.

Optional formats:

- `.pdf` works if `pypdf` is installed.
- `.docx` works if `python-docx` is installed.

The engine skips binary files and common build/cache folders.

## Quick Start

```powershell
cd C:\Users\ksouza\Mycodebase\RAG

py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt

.\.venv\Scripts\python -m rag_engine.cli index --path C:\Users\ksouza\Mycodebase --name mycode
.\.venv\Scripts\python -m rag_engine.cli search --name mycode --query "where is the MCP stock quote tool implemented?"
```

Examples below write `py -m ...` for brevity; run them with the venv's Python (`.\.venv\Scripts\python`) so LangChain is available. Chunk size is set with `CHUNK_SIZE` / `CHUNK_OVERLAP` (characters) or `--chunk-size` / `--chunk-overlap`; re-index after changing it.

## Sources

Every source yields documents; chunking, embedding, indexing and search are identical for all of them. `index` rebuilds the named index from all sources you give it, and each search result carries `source_type` and `uri` so you can tell where it came from.

Quick flags (repeatable, can be combined):

```powershell
py -m rag_engine.cli index --name kb --path .\docs --url https://example.com/docs --depth 1 --max-pages 20
```

Or list everything in a config file (see [sources.example.json](sources.example.json)):

```powershell
py -m rag_engine.cli index --name kb --config sources.json
```

| `type` | Options | Notes |
| --- | --- | --- |
| `files` | `path` | File or folder, recursive. Skips binaries and build/cache folders. |
| `database` | `url`, `query`, `id_column`, `title_column`, `text_columns`, `name` | One document per row. `sqlite:///file.db` works out of the box (opened read-only); other databases need `sqlalchemy` plus a driver. Query must be `SELECT`/`WITH`. |
| `web` | `urls`, `depth`, `max_pages` | http(s) only. `depth > 0` follows same-host links. |

The HTTP API takes the same objects: `POST /index` with `{"index": "kb", "sources": [{"type": "web", "urls": ["https://..."]}]}`. `{"path": "..."}` still works for a single folder.

To add a new source type, subclass `Source` in [rag_engine/sources/base.py](rag_engine/sources/base.py), implement `label` and `documents()`, and register it in `SOURCE_TYPES` in [rag_engine/sources/__init__.py](rag_engine/sources/__init__.py).

Note: the API will read any path or URL a caller gives it, so keep it bound to localhost unless you add authentication.

## LLM-Backed Generation

Search works without an LLM. Generated answers use a LangChain chat model; pick a provider in `.env` (see [.env.example](.env.example)):

```text
# Claude
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-5-5
LLM_API_KEY=your-anthropic-key        # or set ANTHROPIC_API_KEY

# OpenAI or any OpenAI-compatible endpoint (including local Ollama, no key needed)
LLM_PROVIDER=openai-compatible
LLM_API_URL=http://localhost:11434/v1/chat/completions
LLM_REQUIRE_API_KEY=false
LLM_MODEL=llama3.1
```

Then use `--generate` on the CLI, `"generate": true` in the API, or the "LLM answer" box on the web page. If no key is configured or the call fails, the answer falls back to the extractive one and `generation.reason` says why. An LLM key is never used for embeddings.

## Embedding Search (semantic retrieval)

Without embeddings, search is keyword-only (BM25). With them, it also matches by meaning. Anthropic/Claude API keys cannot be used here because Anthropic has no embeddings API. Pick one of:

**Local, no key (Ollama):**

```powershell
winget install -e --id Ollama.Ollama
ollama pull nomic-embed-text
```

Then put this in `.env` (see [.env.example](.env.example) for all settings):

```text
EMBEDDING_API_URL=http://localhost:11434/v1/embeddings
EMBEDDING_REQUIRE_API_KEY=false
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSIONS=768
```

**OpenAI:**

```powershell
$env:EMBEDDING_API_KEY="your-openai-api-key"
$env:EMBEDDING_MODEL="text-embedding-3-small"
```

On Windows the vector engine is `lucene` (the `nmslib` native library is missing from OpenSearch's Windows build), which allows at most 1024 dimensions, so set `EMBEDDING_DIMENSIONS=1024` or lower for OpenAI. Override the engine with `KNN_ENGINE`.

After changing any embedding setting, run indexing again so vectors are stored in OpenSearch:

```powershell
py -m rag_engine.cli index --path C:\Users\ksouza\Mycodebase --name mycode
```

If you have ChatGPT Enterprise but no API key, ask your workspace or platform admin whether your company has an OpenAI API Platform organization/project or an Azure OpenAI deployment. A ChatGPT Enterprise workspace seat is separate from API Platform access, so the ChatGPT web login is not enough for local code to call a model.

Then run:

```powershell
py -m rag_engine.cli search `
  --name mycode `
  --query "where is the MCP stock quote tool implemented?" `
  --generate
```

## Start The API

```powershell
py -m rag_engine.server --host localhost --port 8500
```

Then open:

```text
http://localhost:8500/          web page: upload files, index them, search
http://localhost:8500/health    health check
```

The page saves uploads to `UPLOAD_DIR` (default `Desktop\rag_sample_data\docs`) and indexes that folder into an index called `uploads`. Re-run Index after uploading new files.

Search with PowerShell:

```powershell
$body = @{
  index = "mycode"
  query = "explain the stock agent"
  top_k = 5
  generate = $true
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8500/search `
  -ContentType "application/json" `
  -Body $body
```

## How It Works

```text
Sources (files | database | web)
  -> documents (extractors for files/HTML)
  -> chunks
  -> OpenSearch index (BM25 + optional embedding vectors)
  -> lexical + semantic retrieval
  -> source-grounded answer
  -> optional LLM generation
```

Code layout:

```text
rag_engine/
  sources/       files.py, database.py, web.py  -> yield Documents
  extractors.py  text extraction per file type / HTML parsing
  chunking.py    Document -> Chunks (LangChain RecursiveCharacterTextSplitter)
  embeddings.py  embedding API client
  indexer.py     sources -> chunks -> OpenSearch
  search.py      lexical + semantic retrieval and score fusion
  generator.py   extractive answer, or LangChain prompt | chat model | parser
  cli.py, server.py
```

## Notes

This is a local retrieval engine with OpenSearch retrieval and optional OpenAI-compatible embeddings + LLM generation. Keep `generate=false` for retrieval-only search, or set `generate=true` when an approved model endpoint is configured.

## Deploying For Others

`docker-compose.prod.yml` runs Caddy (automatic HTTPS), the app and OpenSearch on one VM. Only ports 80/443 are exposed; OpenSearch stays on the internal network.

```bash
cp .env.example .env
# set RAG_API_KEY (openssl rand -hex 32), DOMAIN, and your LLM / embedding settings
# for Ollama on the host use EMBEDDING_API_URL=http://host.docker.internal:11434/v1/embeddings
# (or leave EMBEDDING_ENABLED=false for keyword-only search)
docker compose -f docker-compose.prod.yml up -d --build
```

Point your domain's DNS at the VM and open ports 80 and 443. Users open `https://<DOMAIN>/` and sign in with any username and `RAG_API_KEY` as the password; API clients send `Authorization: Bearer <key>`. Give the VM at least 4 GB RAM (OpenSearch uses a 1 GB heap).

Hardening applied in this mode:

- `RAG_API_KEY` is required on every endpoint except `/health`.
- `RESTRICT_SOURCES=true` limits `/index` to the upload directory and public web pages; arbitrary filesystem paths, database sources, and private/loopback/link-local URLs (including via redirects) are rejected.
- Uploads and the OpenSearch index live in Docker volumes.

Everyone who has the key shares the same indexes and uploads; this is not per-user access control.
