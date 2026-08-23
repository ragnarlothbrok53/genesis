import json

from genesis.core.config import settings

_litellm = None


def _extra_headers() -> dict | None:
    raw = settings.get("LLM_EXTRA_HEADERS")
    if not raw:
        return None
    return raw if isinstance(raw, dict) else json.loads(raw)


def _get_litellm():
    global _litellm
    if _litellm is None:
        import litellm

        litellm.telemetry = False
        _litellm = litellm
    return _litellm


def warm() -> None:
    _get_litellm()


def check() -> bool:
    return bool(settings.get("LLM_API_KEY") or _extra_headers())


def _base_params() -> dict:
    params = {"model": settings.LLM_MODEL}
    base_url = settings.get("LLM_BASE_URL")
    api_key = settings.get("LLM_API_KEY")
    if base_url:
        params["api_base"] = base_url
        params["custom_llm_provider"] = "openai"
    if api_key:
        params["api_key"] = api_key
    headers = _extra_headers()
    if headers:
        params["extra_headers"] = headers
        params.setdefault("api_key", "x")
    return params


def chat(prompt: str, system: str | None = None, model: str | None = None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return complete(messages, model=model).choices[0].message.content or ""


def complete(messages: list[dict], model: str | None = None, **kwargs):
    if not settings.get("LLM_API_KEY") and not _extra_headers():
        raise RuntimeError("No LLM auth configured; set LLM_API_KEY or LLM_EXTRA_HEADERS in .env")
    litellm = _get_litellm()
    params = _base_params()
    if model:
        params["model"] = model
    params.update(kwargs)
    return litellm.completion(messages=messages, **params)


def embed(text: str, model: str | None = None) -> list[float]:
    if not settings.get("LLM_API_KEY") and not _extra_headers():
        raise RuntimeError("No LLM auth configured; set LLM_API_KEY or LLM_EXTRA_HEADERS in .env")
    litellm = _get_litellm()
    params = _base_params()
    params["model"] = model or settings.get("LLM_EMBEDDING_MODEL", "openai/text-embedding-3-small")
    response = litellm.embedding(input=[text], **params)
    return response.data[0]["embedding"]


def similarity_search(
    model_class, query: str, k: int = 5, vector_field: str = "embedding"
) -> list[dict]:
    field = getattr(model_class, vector_field)
    query_vector = embed(query)
    return list(
        model_class.select().order_by(field.cosine_distance(query_vector)).limit(k).dicts()
    )
