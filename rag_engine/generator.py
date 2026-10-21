from .config import (
    LLM_API_KEY,
    LLM_API_URL,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_REQUIRE_API_KEY,
    LLM_TEMPERATURE,
)

LLM_TIMEOUT = 45

SYSTEM_PROMPT = (
    'You are a RAG answer generator. Answer only from the provided context. '
    'If the context is insufficient, say what is missing. Cite sources inline '
    'using bracketed source numbers like [1] or [2].'
)
USER_PROMPT = 'Question:\n{question}\n\nContext:\n{context}'


def generate_answer(query: str, results: list[dict], enabled: bool = False) -> dict:
    if not enabled:
        return {
            'mode': 'extractive',
            'answer': compose_extractive_answer(query, results),
            'used_llm': False,
        }

    if LLM_REQUIRE_API_KEY and not LLM_API_KEY:
        return {
            'mode': 'extractive-fallback',
            'answer': compose_extractive_answer(query, results),
            'used_llm': False,
            'reason': (
                'No LLM API key found. Set LLM_API_KEY (or ANTHROPIC_API_KEY / OPENAI_API_KEY), '
                'or LLM_REQUIRE_API_KEY=false for local no-auth endpoints.'
            ),
        }

    if not results:
        return {
            'mode': 'llm',
            'answer': 'I could not find relevant content in the indexed sources.',
            'used_llm': False,
        }

    try:
        answer = call_llm(query, results)
        return {
            'mode': 'llm',
            'answer': answer,
            'used_llm': True,
            'model': LLM_MODEL,
            'provider': LLM_PROVIDER,
        }
    except Exception as error:
        return {
            'mode': 'extractive-fallback',
            'answer': compose_extractive_answer(query, results),
            'used_llm': False,
            'reason': str(error),
        }


def build_llm():
    """Create the LangChain chat model for the configured provider."""
    options = {'temperature': LLM_TEMPERATURE} if LLM_TEMPERATURE is not None else {}

    if LLM_PROVIDER == 'anthropic':
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=LLM_MODEL,
            max_tokens=LLM_MAX_TOKENS,
            api_key=LLM_API_KEY,
            timeout=LLM_TIMEOUT,
            **options,
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=LLM_MODEL,
        max_tokens=LLM_MAX_TOKENS,
        **options,
        api_key=LLM_API_KEY or 'not-needed',  # local servers such as Ollama ignore the key
        base_url=LLM_API_URL.removesuffix('/chat/completions'),
        timeout=LLM_TIMEOUT,
    )


def call_llm(query: str, results: list[dict], llm=None) -> str:
    """Run prompt -> chat model -> text. `llm` can be any LangChain chat model (used by tests)."""
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    prompt = ChatPromptTemplate.from_messages([('system', SYSTEM_PROMPT), ('human', USER_PROMPT)])
    chain = prompt | (llm or build_llm()) | StrOutputParser()

    answer = chain.invoke({'question': query, 'context': build_context(results)}).strip()
    if not answer:
        raise RuntimeError('LLM response did not include any text.')
    return answer


def build_context(results: list[dict]) -> str:
    blocks = []
    for index, result in enumerate(results, start=1):
        text = result.get('text') or result.get('snippet') or ''
        uri = result.get('uri', 'unknown')
        title = result.get('title', uri)
        blocks.append(
            '\n'.join(
                [
                    f'[{index}] Source: {title} ({result.get("source_type", "unknown")})',
                    f'Location: {uri}',
                    f'Content: {text[:2500]}',
                ]
            )
        )
    return '\n\n'.join(blocks)


def compose_extractive_answer(query: str, results: list[dict]) -> str:
    if not results:
        return 'I could not find relevant content in the indexed sources.'

    top = results[:3]
    source_names = ', '.join(result['title'] for result in top)
    evidence = ' '.join(result['snippet'] for result in top)
    return (
        f'Based on the indexed sources, the strongest matches for "{query}" appear in {source_names}. '
        f'Key evidence: {evidence}'
    )
