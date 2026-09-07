import pytest
from flowslide.ai.providers import (
    normalize_base_url,
    build_api_url,
    is_reasoning_model,
    build_openai_completion_kwargs,
)
from flowslide.database.database import (
    ensure_database_initialized,
    db_manager,
    create_async_engine_safe,
)


def test_normalize_base_url():
    cases = [
        ("https://api.openai.com/v1/", "https://api.openai.com/v1"),
        ("https://api.openai.com/v1/chat/completions", "https://api.openai.com/v1"),
        ("https://api.deepseek.com/chat/completions", "https://api.deepseek.com"),
        ("https://api.openai.com/v1/models", "https://api.openai.com/v1"),
        ("https://api.openai.com/v1/completions/", "https://api.openai.com/v1"),
        ("  https://my-proxy.com/v1/chat/completions  ", "https://my-proxy.com/v1"),
        ("", ""),
        (None, ""),
    ]
    for raw, expected in cases:
        assert normalize_base_url(raw) == expected


def test_build_api_url():
    # Adding ensure_v1
    assert (
        build_api_url("https://api.openai.com", "chat/completions", ensure_v1=True)
        == "https://api.openai.com/v1/chat/completions"
    )
    # Suffix stripping in base_url
    assert (
        build_api_url("https://api.openai.com/v1/chat/completions", "models")
        == "https://api.openai.com/v1/models"
    )
    # Ensure no double slashes
    assert (
        build_api_url("https://api.deepseek.com/", "v1", "chat/completions")
        == "https://api.deepseek.com/v1/chat/completions"
    )


def test_is_reasoning_model():
    reasoning_models = [
        "o1",
        "o1-preview",
        "o1-mini",
        "o3",
        "o3-mini",
        "o4",
        "deepseek-reasoner",
        "deepseek-r1",
        "deepseek/deepseek-r1",
        "qwq-32b",
    ]
    for model in reasoning_models:
        assert (
            is_reasoning_model(model) is True
        ), f"Expected {model} to be recognized as reasoning model"

    non_reasoning_models = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-3.5-turbo",
        "claude-3-5-sonnet",
        "gemini-1.5-pro",
        "llama-3.1-8b",
        "",
        None,
    ]
    for model in non_reasoning_models:
        assert (
            is_reasoning_model(model) is False
        ), f"Expected {model} to NOT be recognized as reasoning model"


def test_build_openai_completion_kwargs_standard():
    msgs = [{"role": "user", "content": "hello"}]
    cfg = {"temperature": 0.5, "top_p": 0.9, "max_tokens": 1000}
    kwargs = build_openai_completion_kwargs("gpt-4o", msgs, cfg)
    assert kwargs["model"] == "gpt-4o"
    assert kwargs["messages"] == msgs
    assert kwargs["temperature"] == 0.5
    assert kwargs["top_p"] == 0.9
    assert kwargs["max_tokens"] == 1000
    assert "max_completion_tokens" not in kwargs


def test_build_openai_completion_kwargs_reasoning():
    msgs = [{"role": "user", "content": "solve math"}]
    cfg = {"temperature": 0.7, "top_p": 1.0, "max_tokens": 2048}
    kwargs = build_openai_completion_kwargs("o1-mini", msgs, cfg)
    assert kwargs["model"] == "o1-mini"
    assert kwargs["messages"] == msgs
    # Reasoning models must NOT include temperature or top_p
    assert "temperature" not in kwargs
    assert "top_p" not in kwargs
    # max_tokens should be mapped to max_completion_tokens
    assert kwargs["max_completion_tokens"] == 2048
    assert "max_tokens" not in kwargs


def test_build_openai_completion_kwargs_retry_mode():
    msgs = [{"role": "user", "content": "retry test"}]
    cfg = {"temperature": 0.7, "top_p": 1.0, "max_tokens": 512}
    kwargs = build_openai_completion_kwargs("custom-model", msgs, cfg, is_retry=True)
    assert kwargs["model"] == "custom-model"
    assert "temperature" not in kwargs
    assert "top_p" not in kwargs
    assert kwargs["max_completion_tokens"] == 512


def test_create_async_engine_safe_ssl():
    engine = create_async_engine_safe(
        "postgresql://user:pass@ep-test.neon.tech/db?sslmode=unverified"
    )
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "asyncpg"


def test_ensure_database_initialized_idempotent():
    ensure_database_initialized()
    assert db_manager.primary_engine is not None
