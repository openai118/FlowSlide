"""
AI provider implementations
"""

import logging
import asyncio
import random
from typing import Any, AsyncGenerator, Dict, List, Optional

from ..core.config import ai_config
from .base import AIMessage, AIProvider, AIResponse, MessageRole

logger = logging.getLogger(__name__)


def normalize_base_url(base_url: Optional[str]) -> str:
    """Clean and normalize AI provider base URL by stripping trailing slashes and common endpoint suffixes."""
    if not base_url:
        return ""
    url = str(base_url).strip().rstrip("/")
    for suffix in ("/chat/completions", "/completions", "/models"):
        if url.endswith(suffix):
            url = url[: -len(suffix)].rstrip("/")
    return url


def build_api_url(base_url: str, *parts: str, ensure_v1: bool = False) -> str:
    """Safe join of base_url and parts for AI provider endpoints."""
    if not base_url:
        return "/" + "/".join(p.strip("/") for p in parts if p)
    base = normalize_base_url(base_url)
    if ensure_v1 and not base.endswith("/v1"):
        base = base + "/v1"
    suffix = "/".join(p.strip("/") for p in parts if p)
    return f"{base}/{suffix}" if suffix else base


def is_reasoning_model(model_name: Optional[str]) -> bool:
    """Check if model is an OpenAI or compatible reasoning model (o1, o3, deepseek-reasoner, etc.)."""
    if not model_name:
        return False
    name = model_name.lower()
    if any(p in name for p in ["reasoner", "qwq"]):
        return True
    if any(
        part in ("o1", "o3", "o4", "r1")
        for part in name.replace("-", " ").replace("_", " ").replace("/", " ").split()
    ):
        return True
    if name.startswith(("o1", "o3", "o4", "deepseek-r1", "qwq")):
        return True
    return False


def build_openai_completion_kwargs(
    model: str,
    openai_messages: List[Dict[str, str]],
    config: Dict[str, Any],
    is_retry: bool = False,
) -> Dict[str, Any]:
    """Build kwargs for OpenAI completions, adapting parameters for reasoning models."""
    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": openai_messages,
    }
    is_reasoning = is_retry or is_reasoning_model(model)

    max_tokens = config.get("max_tokens") or config.get("max_completion_tokens")
    if max_tokens is not None:
        try:
            tokens_val = int(max_tokens)
            if is_reasoning:
                kwargs["max_completion_tokens"] = tokens_val
            else:
                kwargs["max_tokens"] = tokens_val
        except (ValueError, TypeError):
            pass

    if not is_reasoning:
        if "temperature" in config and config["temperature"] is not None:
            try:
                kwargs["temperature"] = float(config["temperature"])
            except (ValueError, TypeError):
                kwargs["temperature"] = 0.7
        else:
            kwargs["temperature"] = 0.7

        if "top_p" in config and config["top_p"] is not None:
            try:
                kwargs["top_p"] = float(config["top_p"])
            except (ValueError, TypeError):
                kwargs["top_p"] = 1.0
        else:
            kwargs["top_p"] = 1.0

    return kwargs


class OpenAIProvider(AIProvider):
    """OpenAI API provider"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        try:
            import openai

            raw_base_url = config.get("base_url")
            base_url = (
                raw_base_url.strip()
                if isinstance(raw_base_url, str) and raw_base_url.strip()
                else None
            )
            if base_url:
                base_url = base_url.rstrip("/")
                for suffix in ("/chat/completions", "/completions", "/models"):
                    if base_url.endswith(suffix):
                        base_url = base_url[: -len(suffix)].rstrip("/")
            self.client = openai.AsyncOpenAI(api_key=config.get("api_key"), base_url=base_url)
        except ImportError:
            logger.warning("OpenAI library not installed. Install with: pip install openai")
            self.client = None

    async def chat_completion(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """Generate chat completion using OpenAI"""
        if not self.client:
            raise RuntimeError("OpenAI client not available")

        config = self._merge_config(**kwargs)

        # Normalize incoming messages to AIMessage to be robust to dicts or other models
        normalized: List[AIMessage] = []
        for m in messages:
            if isinstance(m, AIMessage):
                normalized.append(m)
            elif isinstance(m, dict):
                role = m.get("role", "user")
                content = m.get("content", "")
                name = m.get("name")
                try:
                    normalized.append(
                        AIMessage(role=MessageRole(role), content=str(content), name=name)
                    )
                except Exception:
                    normalized.append(AIMessage(role=MessageRole.USER, content=str(content)))
            elif hasattr(m, "role") and hasattr(m, "content"):
                # Pydantic-like object
                try:
                    normalized.append(
                        AIMessage(
                            role=MessageRole(getattr(m, "role")), content=str(getattr(m, "content"))
                        )
                    )
                except Exception:
                    normalized.append(
                        AIMessage(role=MessageRole.USER, content=str(getattr(m, "content", "")))
                    )
            else:
                normalized.append(AIMessage(role=MessageRole.USER, content=str(m)))
        messages = normalized

        # Convert messages to OpenAI format
        openai_messages = [{"role": msg.role.value, "content": msg.content} for msg in messages]

        model_name = config.get("model", self.model)
        openai_kwargs = build_openai_completion_kwargs(model_name, openai_messages, config)

        # Apply configurable timeout and retry logic to mitigate transient network/API issues.
        request_timeout = config.get("request_timeout", 30)
        max_retries = int(config.get("max_retries", 3))

        last_exc: Optional[BaseException] = None
        for attempt in range(1, max_retries + 1):
            try:
                coro = self.client.chat.completions.create(**openai_kwargs)

                response = await asyncio.wait_for(coro, timeout=request_timeout)

                choice = response.choices[0]

                return AIResponse(
                    content=choice.message.content,
                    model=response.model,
                    usage={
                        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                        "total_tokens": getattr(response.usage, "total_tokens", 0),
                    },
                    finish_reason=choice.finish_reason,
                    metadata={"provider": "openai"},
                )

            except asyncio.TimeoutError as te:
                last_exc = te
                logger.error(
                    "OpenAI request timed out (attempt %d/%d) after %s seconds",
                    attempt,
                    max_retries,
                    request_timeout,
                )
                # If final attempt, raise the timeout so caller can handle it
                if attempt >= max_retries:
                    raise
                # Exponential backoff with jitter
                await asyncio.sleep(min(2**attempt + random.random(), 10))
                continue
            except Exception as e:
                last_exc = e
                err_str = str(e).lower()
                if any(
                    param_kw in err_str
                    for param_kw in (
                        "temperature",
                        "top_p",
                        "max_tokens",
                        "max_completion_tokens",
                        "unsupported_parameter",
                        "param",
                    )
                ):
                    logger.warning(
                        "OpenAI API parameter error on attempt %d/%d: %s; retrying with reasoning kwargs",
                        attempt,
                        max_retries,
                        e,
                    )
                    openai_kwargs = build_openai_completion_kwargs(
                        model_name, openai_messages, config, is_retry=True
                    )
                else:
                    logger.error("OpenAI API error on attempt %d/%d: %s", attempt, max_retries, e)
                if attempt >= max_retries:
                    raise
                await asyncio.sleep(min(2**attempt + random.random(), 10))

        # If we exit loop without returning, raise the last seen exception
        if last_exc:
            raise last_exc

    async def text_completion(self, prompt: str, **kwargs) -> AIResponse:
        """Generate text completion using OpenAI chat format"""
        messages = [AIMessage(role=MessageRole.USER, content=prompt)]
        return await self.chat_completion(messages, **kwargs)

    async def stream_chat_completion(
        self, messages: List[AIMessage], **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion using OpenAI"""
        if not self.client:
            raise RuntimeError("OpenAI client not available")

        config = self._merge_config(**kwargs)

        # Normalize incoming messages
        normalized: List[AIMessage] = []
        for m in messages:
            if isinstance(m, AIMessage):
                normalized.append(m)
            elif isinstance(m, dict):
                role = m.get("role", "user")
                content = m.get("content", "")
                name = m.get("name")
                try:
                    normalized.append(
                        AIMessage(role=MessageRole(role), content=str(content), name=name)
                    )
                except Exception:
                    normalized.append(AIMessage(role=MessageRole.USER, content=str(content)))
            elif hasattr(m, "role") and hasattr(m, "content"):
                try:
                    normalized.append(
                        AIMessage(
                            role=MessageRole(getattr(m, "role")), content=str(getattr(m, "content"))
                        )
                    )
                except Exception:
                    normalized.append(
                        AIMessage(role=MessageRole.USER, content=str(getattr(m, "content", "")))
                    )
            else:
                normalized.append(AIMessage(role=MessageRole.USER, content=str(m)))
        messages = normalized

        # Convert messages to OpenAI format
        openai_messages = [{"role": msg.role.value, "content": msg.content} for msg in messages]

        model_name = config.get("model", self.model)
        openai_kwargs = build_openai_completion_kwargs(model_name, openai_messages, config)
        openai_kwargs["stream"] = True

        try:
            request_timeout = config.get("request_timeout", 60)
            try:
                coro = self.client.chat.completions.create(**openai_kwargs)
                stream = await asyncio.wait_for(coro, timeout=request_timeout)
            except Exception as first_err:
                err_str = str(first_err).lower()
                if any(
                    param_kw in err_str
                    for param_kw in (
                        "temperature",
                        "top_p",
                        "max_tokens",
                        "max_completion_tokens",
                        "unsupported_parameter",
                        "param",
                    )
                ):
                    logger.warning(
                        "OpenAI streaming parameter error: %s; retrying with reasoning kwargs",
                        first_err,
                    )
                    retry_kwargs = build_openai_completion_kwargs(
                        model_name, openai_messages, config, is_retry=True
                    )
                    retry_kwargs["stream"] = True
                    coro = self.client.chat.completions.create(**retry_kwargs)
                    stream = await asyncio.wait_for(coro, timeout=request_timeout)
                else:
                    raise first_err

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except asyncio.TimeoutError:
            logger.error("OpenAI streaming request timed out after %s seconds", request_timeout)
            raise
        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            raise

    async def stream_text_completion(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """Stream text completion using OpenAI chat format"""
        messages = [AIMessage(role=MessageRole.USER, content=prompt)]
        async for chunk in self.stream_chat_completion(messages, **kwargs):
            yield chunk


class AnthropicProvider(AIProvider):
    """Anthropic Claude API provider"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        try:
            import anthropic

            self.client = anthropic.AsyncAnthropic(
                api_key=config.get("api_key"), base_url=config.get("base_url")
            )
        except ImportError:
            logger.warning("Anthropic library not installed. Install with: pip install anthropic")
            self.client = None

    async def chat_completion(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """Generate chat completion using Anthropic Claude"""
        if not self.client:
            raise RuntimeError("Anthropic client not available")

        config = self._merge_config(**kwargs)

        # Normalize incoming messages
        normalized: List[AIMessage] = []
        for m in messages:
            if isinstance(m, AIMessage):
                normalized.append(m)
            elif isinstance(m, dict):
                role = m.get("role", "user")
                content = m.get("content", "")
                name = m.get("name")
                try:
                    normalized.append(
                        AIMessage(role=MessageRole(role), content=str(content), name=name)
                    )
                except Exception:
                    normalized.append(AIMessage(role=MessageRole.USER, content=str(content)))
            elif hasattr(m, "role") and hasattr(m, "content"):
                try:
                    normalized.append(
                        AIMessage(
                            role=MessageRole(getattr(m, "role")), content=str(getattr(m, "content"))
                        )
                    )
                except Exception:
                    normalized.append(
                        AIMessage(role=MessageRole.USER, content=str(getattr(m, "content", "")))
                    )
            else:
                normalized.append(AIMessage(role=MessageRole.USER, content=str(m)))
        messages = normalized

        # Convert messages to Anthropic format
        system_message = None
        claude_messages = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_message = msg.content
            else:
                claude_messages.append({"role": msg.role.value, "content": msg.content})

        # Apply configurable timeout and retry logic similar to OpenAI provider
        request_timeout = config.get("request_timeout", 30)
        max_retries = int(config.get("max_retries", 3))

        last_exc: Optional[BaseException] = None
        for attempt in range(1, max_retries + 1):
            try:
                coro = self.client.messages.create(
                    model=config.get("model", self.model),
                    # max_tokens=config.get("max_tokens", 2000),
                    temperature=config.get("temperature", 0.7),
                    system=system_message,
                    messages=claude_messages,
                )

                response = await asyncio.wait_for(coro, timeout=request_timeout)

                content = response.content[0].text if response.content else ""

                return AIResponse(
                    content=content,
                    model=response.model,
                    usage={
                        "prompt_tokens": getattr(response.usage, "input_tokens", 0),
                        "completion_tokens": getattr(response.usage, "output_tokens", 0),
                        "total_tokens": (
                            getattr(response.usage, "input_tokens", 0)
                            + getattr(response.usage, "output_tokens", 0)
                        ),
                    },
                    finish_reason=getattr(response, "stop_reason", None),
                    metadata={"provider": "anthropic"},
                )

            except asyncio.TimeoutError as te:
                last_exc = te
                logger.error(
                    "Anthropic request timed out (attempt %d/%d) after %s seconds",
                    attempt,
                    max_retries,
                    request_timeout,
                )
                if attempt >= max_retries:
                    raise
                await asyncio.sleep(min(2**attempt + random.random(), 10))
                continue
            except Exception as e:
                last_exc = e
                logger.error("Anthropic API error on attempt %d/%d: %s", attempt, max_retries, e)
                if attempt >= max_retries:
                    raise
                await asyncio.sleep(min(2**attempt + random.random(), 10))

        if last_exc:
            raise last_exc

    async def text_completion(self, prompt: str, **kwargs) -> AIResponse:
        """Generate text completion using Anthropic chat format"""
        messages = [AIMessage(role=MessageRole.USER, content=prompt)]
        return await self.chat_completion(messages, **kwargs)


class GoogleProvider(AIProvider):
    """Google Gemini API provider"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # Always capture config bits we need
        self.api_key = config.get("api_key")
        # Normalize base_url and ensure no trailing slash
        self.base_url = config.get("base_url") or ("https://generativelanguage.googleapis.com")
        self.base_url = self.base_url.rstrip("/")
        self._use_rest = False

        try:
            import google.generativeai as genai

            # If using default base URL and SDK is available, prefer SDK path
            if self.base_url == "https://generativelanguage.googleapis.com":
                genai.configure(api_key=self.api_key)
                self.client = genai
                self.model_instance = genai.GenerativeModel(config.get("model", "gemini-1.5-flash"))
            else:
                # Custom base URL requested – fall back to REST implementation
                self.client = None
                self.model_instance = None
                self._use_rest = True
        except ImportError:
            logger.warning(
                "Google Generative AI library not installed."
                " Install with: pip install google-generativeai"
            )
            # If SDK missing, fall back to REST (works for default or custom base URL)
            self.client = None
            self.model_instance = None
            self._use_rest = True

    async def chat_completion(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """Generate chat completion using Google Gemini"""
        # If REST mode, use REST call (supports custom base URL/proxies)
        if self._use_rest:
            # Normalize incoming messages
            normalized: List[AIMessage] = []
            for m in messages:
                if isinstance(m, AIMessage):
                    normalized.append(m)
                elif isinstance(m, dict):
                    role = m.get("role", "user")
                    content = m.get("content", "")
                    name = m.get("name")
                    try:
                        normalized.append(
                            AIMessage(role=MessageRole(role), content=str(content), name=name)
                        )
                    except Exception:
                        normalized.append(AIMessage(role=MessageRole.USER, content=str(content)))
                elif hasattr(m, "role") and hasattr(m, "content"):
                    try:
                        normalized.append(
                            AIMessage(
                                role=MessageRole(getattr(m, "role")),
                                content=str(getattr(m, "content")),
                            )
                        )
                    except Exception:
                        normalized.append(
                            AIMessage(role=MessageRole.USER, content=str(getattr(m, "content", "")))
                        )
                else:
                    normalized.append(AIMessage(role=MessageRole.USER, content=str(m)))
            messages = normalized
            prompt = []
            for msg in messages:
                if msg.role == MessageRole.SYSTEM:
                    prompt.append(f"System: {msg.content}")
                elif msg.role == MessageRole.USER:
                    prompt.append(f"User: {msg.content}")
                elif msg.role == MessageRole.ASSISTANT:
                    prompt.append(f"Assistant: {msg.content}")
            prompt_text = "\n".join(prompt)

            return await self._chat_via_rest(prompt_text, **kwargs)

        if not self.client or not self.model_instance:
            raise RuntimeError("Google Gemini client not available")

        config = self._merge_config(**kwargs)

        # Convert messages to Gemini format
        # Gemini uses a different conversation format
        # Normalize incoming messages
        normalized: List[AIMessage] = []
        for m in messages:
            if isinstance(m, AIMessage):
                normalized.append(m)
            elif isinstance(m, dict):
                role = m.get("role", "user")
                content = m.get("content", "")
                name = m.get("name")
                try:
                    normalized.append(
                        AIMessage(role=MessageRole(role), content=str(content), name=name)
                    )
                except Exception:
                    normalized.append(AIMessage(role=MessageRole.USER, content=str(content)))
            elif hasattr(m, "role") and hasattr(m, "content"):
                try:
                    normalized.append(
                        AIMessage(
                            role=MessageRole(getattr(m, "role")), content=str(getattr(m, "content"))
                        )
                    )
                except Exception:
                    normalized.append(
                        AIMessage(role=MessageRole.USER, content=str(getattr(m, "content", "")))
                    )
            else:
                normalized.append(AIMessage(role=MessageRole.USER, content=str(m)))
        messages = normalized
        conversation_parts = []
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                # System messages are handled differently in Gemini
                conversation_parts.append(f"System: {msg.content}")
            elif msg.role == MessageRole.USER:
                conversation_parts.append(f"User: {msg.content}")
            elif msg.role == MessageRole.ASSISTANT:
                conversation_parts.append(f"Assistant: {msg.content}")

        # Combine all parts into a single prompt
        prompt = "\n".join(conversation_parts)

        try:
            # Configure generation parameters
            # 确保max_tokens不会太小，至少1000个token用于生成内容
            # (max tokens handled by generation config when needed)
            generation_config = {
                "temperature": config.get("temperature", 0.7),
                "top_p": config.get("top_p", 1.0),
            }

            # 配置安全设置 - 设置为较宽松的安全级别以减少误拦截
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_ONLY_HIGH",
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_ONLY_HIGH",
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_ONLY_HIGH",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_ONLY_HIGH",
                },
            ]

            # Apply configurable timeout and retries for SDK generation
            request_timeout = config.get("request_timeout", 60)
            max_retries = int(config.get("max_retries", 3))

            last_exc: Optional[BaseException] = None
            for attempt in range(1, max_retries + 1):
                try:
                    coro = self._generate_async(prompt, generation_config, safety_settings)
                    response = await asyncio.wait_for(coro, timeout=request_timeout)
                    break
                except asyncio.TimeoutError as te:
                    last_exc = te
                    logger.error(
                        "Google SDK request timed out (attempt %d/%d) after %s seconds",
                        attempt,
                        max_retries,
                        request_timeout,
                    )
                    if attempt >= max_retries:
                        raise
                    await asyncio.sleep(min(2**attempt + random.random(), 10))
                    continue
                except Exception as e:
                    last_exc = e
                    logger.error("Google SDK error on attempt %d/%d: %s", attempt, max_retries, e)
                    if attempt >= max_retries:
                        raise
                    await asyncio.sleep(min(2**attempt + random.random(), 10))

            if last_exc and not (hasattr(last_exc, "__traceback__")):
                # ensure response variable exists; if we exhausted retries the exception will have been raised
                pass
            logger.debug(f"Google Gemini API response: {response}")

            # 检查响应状态和安全过滤
            finish_reason = "stop"
            content = ""

            if response.candidates:
                candidate = response.candidates[0]
                finish_reason = (
                    candidate.finish_reason.name
                    if hasattr(candidate.finish_reason, "name")
                    else str(candidate.finish_reason)
                )

                # 检查是否被安全过滤器阻止或其他问题
                if finish_reason == "SAFETY":
                    logger.warning("Content was blocked by safety filters")
                    content = "[内容被安全过滤器阻止]"
                elif finish_reason == "RECITATION":
                    logger.warning("Content was blocked due to recitation")
                    content = "[内容因重复而被阻止]"
                elif finish_reason == "MAX_TOKENS":
                    logger.warning("Response was truncated due to max tokens limit")
                    # 尝试获取部分内容
                    try:
                        if (
                            hasattr(candidate, "content")
                            and candidate.content
                            and hasattr(candidate.content, "parts")
                            and candidate.content.parts
                        ):
                            content = (
                                candidate.content.parts[0].text
                                if candidate.content.parts[0].text
                                else "[响应因token限制被截断，无内容]"
                            )
                        else:
                            content = "[响应因token限制被截断，无内容]"
                    except Exception as text_error:
                        logger.warning(f"Failed to get truncated response text: {text_error}")
                        content = "[响应因token限制被截断，无法获取内容]"
                elif finish_reason == "OTHER":
                    logger.warning("Content was blocked for other reasons")
                    content = "[内容被其他原因阻止]"
                else:
                    # 正常情况下获取文本
                    try:
                        if (
                            hasattr(candidate, "content")
                            and candidate.content
                            and hasattr(candidate.content, "parts")
                            and candidate.content.parts
                        ):
                            content = (
                                candidate.content.parts[0].text
                                if candidate.content.parts[0].text
                                else ""
                            )
                        else:
                            # 回退到response.text
                            content = (
                                response.text if hasattr(response, "text") and response.text else ""
                            )
                    except Exception as text_error:
                        logger.warning(f"Failed to get response text: {text_error}")
                        content = "[无法获取响应内容]"
            else:
                logger.warning("No candidates in response")
                content = "[响应中没有候选内容]"

            return AIResponse(
                content=content,
                model=self.model,
                usage={
                    "prompt_tokens": (
                        response.usage_metadata.prompt_token_count
                        if hasattr(response, "usage_metadata")
                        else 0
                    ),
                    "completion_tokens": (
                        response.usage_metadata.candidates_token_count
                        if hasattr(response, "usage_metadata")
                        else 0
                    ),
                    "total_tokens": (
                        response.usage_metadata.total_token_count
                        if hasattr(response, "usage_metadata")
                        else 0
                    ),
                },
                finish_reason=finish_reason,
                metadata={"provider": "google"},
            )

        except Exception as e:
            logger.error(f"Google Gemini API error: {e}")
            raise

    async def _chat_via_rest(self, prompt_text: str, **kwargs) -> AIResponse:
        """Use REST API to call Gemini, honoring custom base_url."""
        import aiohttp

        config = self._merge_config(**kwargs)
        model = config.get("model", self.model)
        url = f"{self.base_url}/v1beta/models/{model}:generateContent?key={self.api_key}"

        generation_config = {
            "temperature": config.get("temperature", 0.7),
            "topP": config.get("top_p", 1.0),
            # "maxOutputTokens": max(config.get("max_tokens", 16384), 1000),
        }

        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": generation_config,
        }

        # Apply configurable timeout and retry logic for REST path
        request_timeout = int(config.get("request_timeout", 60))
        max_retries = int(config.get("max_retries", 3))

        last_exc: Optional[BaseException] = None
        for attempt in range(1, max_retries + 1):
            try:
                timeout_obj = aiohttp.ClientTimeout(total=request_timeout)
                async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                    async with session.post(url, json=payload) as resp:
                        if resp.status != 200:
                            text = await resp.text()
                            raise RuntimeError(f"Google REST API error {resp.status}: {text[:200]}")
                        data = await resp.json()
                        break
            except asyncio.TimeoutError as te:
                last_exc = te
                logger.error(
                    "Google REST request timed out (attempt %d/%d) after %s seconds",
                    attempt,
                    max_retries,
                    request_timeout,
                )
                if attempt >= max_retries:
                    raise
                await asyncio.sleep(min(2**attempt + random.random(), 10))
                continue
            except Exception as e:
                last_exc = e
                logger.error("Google REST error on attempt %d/%d: %s", attempt, max_retries, e)
                if attempt >= max_retries:
                    raise
                await asyncio.sleep(min(2**attempt + random.random(), 10))

        # If data wasn't set because all retries failed, raise the last exception
        if last_exc and "data" not in locals():
            raise last_exc

        # Extract text
        content = ""
        try:
            candidates = data.get("candidates") or []
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [{}])
                content = parts[0].get("text", "")
        except Exception:
            content = ""

        return AIResponse(
            content=content,
            model=model,
            usage=self._calculate_usage(prompt_text, content),
            finish_reason="stop",
            metadata={"provider": "google", "transport": "rest"},
        )

    async def _generate_async(
        self, prompt: str, generation_config: Dict[str, Any], safety_settings=None
    ):
        """Async wrapper for Gemini generation"""
        import asyncio

        loop = asyncio.get_event_loop()

        def _generate_sync():
            kwargs = {"generation_config": generation_config}
            if safety_settings:
                kwargs["safety_settings"] = safety_settings

            return self.model_instance.generate_content(prompt, **kwargs)

        return await loop.run_in_executor(None, _generate_sync)

    async def text_completion(self, prompt: str, **kwargs) -> AIResponse:
        """Generate text completion using Google Gemini"""
        messages = [AIMessage(role=MessageRole.USER, content=prompt)]
        return await self.chat_completion(messages, **kwargs)


class OllamaProvider(AIProvider):
    """Ollama local model provider"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        try:
            import ollama

            self.client = ollama.AsyncClient(host=config.get("base_url", "http://localhost:11434"))
        except ImportError:
            logger.warning("Ollama library not installed. Install with: pip install ollama")
            self.client = None

    async def chat_completion(self, messages: List[AIMessage], **kwargs) -> AIResponse:
        """Generate chat completion using Ollama"""
        if not self.client:
            raise RuntimeError("Ollama client not available")

        config = self._merge_config(**kwargs)

        # Normalize incoming messages
        normalized: List[AIMessage] = []
        for m in messages:
            if isinstance(m, AIMessage):
                normalized.append(m)
            elif isinstance(m, dict):
                role = m.get("role", "user")
                content = m.get("content", "")
                name = m.get("name")
                try:
                    normalized.append(
                        AIMessage(role=MessageRole(role), content=str(content), name=name)
                    )
                except Exception:
                    normalized.append(AIMessage(role=MessageRole.USER, content=str(content)))
            elif hasattr(m, "role") and hasattr(m, "content"):
                try:
                    normalized.append(
                        AIMessage(
                            role=MessageRole(getattr(m, "role")), content=str(getattr(m, "content"))
                        )
                    )
                except Exception:
                    normalized.append(
                        AIMessage(role=MessageRole.USER, content=str(getattr(m, "content", "")))
                    )
            else:
                normalized.append(AIMessage(role=MessageRole.USER, content=str(m)))
        messages = normalized

        # Convert messages to Ollama format
        ollama_messages = [{"role": msg.role.value, "content": msg.content} for msg in messages]

        try:
            response = await self.client.chat(
                model=config.get("model", self.model),
                messages=ollama_messages,
                options={
                    "temperature": config.get("temperature", 0.7),
                    "top_p": config.get("top_p", 1.0),
                    # "num_predict": config.get("max_tokens", 2000)
                },
            )

            content = response.get("message", {}).get("content", "")

            return AIResponse(
                content=content,
                model=config.get("model", self.model),
                usage=self._calculate_usage(" ".join([msg.content for msg in messages]), content),
                finish_reason="stop",
                metadata={"provider": "ollama"},
            )

        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            raise

    async def text_completion(self, prompt: str, **kwargs) -> AIResponse:
        """Generate text completion using Ollama"""
        messages = [AIMessage(role=MessageRole.USER, content=prompt)]
        return await self.chat_completion(messages, **kwargs)


class AIProviderFactory:
    """Factory for creating AI providers"""

    _providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "google": GoogleProvider,
        "gemini": GoogleProvider,  # Alias for google
        "ollama": OllamaProvider,
    }

    @classmethod
    def create_provider(
        cls, provider_name: str, config: Optional[Dict[str, Any]] = None
    ) -> AIProvider:
        """Create an AI provider instance"""
        if config is None:
            config = ai_config.get_provider_config(provider_name)

        # Built-in providers
        if provider_name not in cls._providers:
            raise ValueError(f"Unknown provider: {provider_name}")

        provider_class = cls._providers[provider_name]
        return provider_class(config)

    @classmethod
    def get_available_providers(cls) -> List[str]:
        """Get list of available providers"""
        return list(cls._providers.keys())


class AIProviderManager:
    """Manager for AI provider instances with caching and reloading"""

    def __init__(self):
        self._provider_cache = {}
        self._config_cache = {}

    def get_provider(self, provider_name: Optional[str] = None) -> AIProvider:
        """Get AI provider instance with caching"""
        if provider_name is None:
            provider_name = ai_config.default_ai_provider

        # Get current config for the provider
        current_config = ai_config.get_provider_config(provider_name)

        # Check if we have a cached provider and if config has changed
        cache_key = provider_name
        if (
            cache_key in self._provider_cache
            and cache_key in self._config_cache
            and self._config_cache[cache_key] == current_config
        ):
            return self._provider_cache[cache_key]

        # Create new provider instance
        provider = AIProviderFactory.create_provider(provider_name, current_config)

        # Cache the provider and config
        self._provider_cache[cache_key] = provider
        self._config_cache[cache_key] = current_config

        return provider

    def clear_cache(self):
        """Clear provider cache to force reload"""
        self._provider_cache.clear()
        self._config_cache.clear()

    def reload_provider(self, provider_name: str):
        """Reload a specific provider"""
        cache_key = provider_name
        if cache_key in self._provider_cache:
            del self._provider_cache[cache_key]
        if cache_key in self._config_cache:
            del self._config_cache[cache_key]


# Global provider manager
_provider_manager = AIProviderManager()


def get_ai_provider(provider_name: Optional[str] = None) -> AIProvider:
    """Get AI provider instance"""
    return _provider_manager.get_provider(provider_name)


def reload_ai_providers():
    """Reload all AI providers (clear cache)"""
    _provider_manager.clear_cache()
