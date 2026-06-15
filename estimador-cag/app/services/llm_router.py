import litellm
from litellm import Router
from app.config import get_settings

settings = get_settings()

litellm.drop_params = True  # silently ignore params unsupported by a given provider


def _build_router() -> Router:
    model_list: list[dict] = []
    fallback_names: list[str] = []

    def _add(name: str, litellm_params: dict, primary: bool = False) -> None:
        model_list.append({"model_name": name, "litellm_params": litellm_params})
        if not primary:
            fallback_names.append(name)

    if settings.LLM_PROVIDER == "ollama":
        ollama_models = [m.strip() for m in settings.OLLAMA_MODELS.split(",") if m.strip()]
        for i, m in enumerate(ollama_models):
            name = "estimator" if i == 0 else f"estimator-ollama-{i}"
            _add(name, {"model": f"ollama/{m}", "api_base": settings.OLLAMA_API_BASE}, primary=(i == 0))
        if settings.ANTHROPIC_API_KEY:
            _add("estimator-anthropic", {"model": settings.ANTHROPIC_MODEL, "api_key": settings.ANTHROPIC_API_KEY})
        if settings.OPENAI_API_KEY:
            _add("estimator-openai", {"model": settings.OPENAI_MODEL, "api_key": settings.OPENAI_API_KEY})

    elif settings.LLM_PROVIDER == "openai":
        _add("estimator", {"model": settings.OPENAI_MODEL, "api_key": settings.OPENAI_API_KEY}, primary=True)
        if settings.ANTHROPIC_API_KEY:
            _add("estimator-anthropic", {"model": settings.ANTHROPIC_MODEL, "api_key": settings.ANTHROPIC_API_KEY})
        if settings.OLLAMA_API_BASE:
            for i, m in enumerate(m.strip() for m in settings.OLLAMA_MODELS.split(",") if m.strip()):
                _add(f"estimator-ollama-{i}", {"model": f"ollama/{m}", "api_base": settings.OLLAMA_API_BASE})

    else:  # anthropic (default)
        _add("estimator", {"model": settings.ANTHROPIC_MODEL, "api_key": settings.ANTHROPIC_API_KEY}, primary=True)
        if settings.OPENAI_API_KEY:
            _add("estimator-openai", {"model": settings.OPENAI_MODEL, "api_key": settings.OPENAI_API_KEY})
        if settings.OLLAMA_API_BASE:
            for i, m in enumerate(m.strip() for m in settings.OLLAMA_MODELS.split(",") if m.strip()):
                _add(f"estimator-ollama-{i}", {"model": f"ollama/{m}", "api_base": settings.OLLAMA_API_BASE})

    fallbacks = [{"estimator": fallback_names}] if fallback_names else []

    return Router(
        model_list=model_list,
        fallbacks=fallbacks,
        num_retries=2,
        allowed_fails=1,
    )


router: Router = _build_router()


def default_model_name() -> str:
    if settings.LLM_PROVIDER == "ollama":
        return settings.OLLAMA_MODELS.split(",")[0].strip()
    if settings.LLM_PROVIDER == "openai":
        return settings.OPENAI_MODEL
    return settings.ANTHROPIC_MODEL


def infer_provider(model: str) -> str:
    m = model.lower()
    if "claude" in m:
        return "anthropic"
    if any(x in m for x in ("gpt-", "o1-", "o3-", "o4-")):
        return "openai"
    if "ollama" in m or settings.LLM_PROVIDER == "ollama":
        return "ollama"
    return "litellm"
