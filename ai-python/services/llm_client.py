"""Injectable LLM boundary with bounded retry semantics."""

import asyncio
from typing import Any
from langchain_core.runnables import Runnable


class LLMRequestError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _status_code(error: BaseException) -> int | None:
    response = getattr(error, "response", None)
    return getattr(response, "status_code", None) or getattr(error, "status_code", None)


class InjectableLLM(Runnable[Any, Any]):
    """Small proxy around a LangChain chat model or a test double."""

    def __init__(self, delegate: Any, retries: int = 2, backoff_seconds: float = 0.1):
        self._delegate = delegate
        self._retries = max(0, retries)
        self._backoff = max(0.0, backoff_seconds)

    def bind_tools(self, *args: Any, **kwargs: Any) -> "InjectableLLM":
        return InjectableLLM(self._delegate.bind_tools(*args, **kwargs), self._retries, self._backoff)

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        if hasattr(self._delegate, "invoke"):
            return self._delegate.invoke(input, config=config, **kwargs)
        raise LLMRequestError("synchronous invoke is not supported by delegate")

    async def ainvoke(self, messages: Any, config: Any = None, **kwargs: Any) -> Any:
        attempt = 0
        while True:
            try:
                if config is None:
                    return await self._delegate.ainvoke(messages, **kwargs)
                return await self._delegate.ainvoke(messages, config=config, **kwargs)
            except Exception as exc:
                status = _status_code(exc)
                retryable = status in {408, 429} or status is None or status >= 500
                if not retryable or attempt >= self._retries:
                    raise LLMRequestError(str(exc), status) from exc
                await asyncio.sleep(self._backoff * (2**attempt))
                attempt += 1


def build_openai_llm(*, model: str, temperature: float, timeout: int, api_key: str, base_url: str, retries: int) -> InjectableLLM:
    from langchain_openai import ChatOpenAI

    kwargs = {"model": model, "temperature": temperature, "timeout": timeout, "api_key": api_key, "max_retries": 0}
    if base_url:
        kwargs["base_url"] = base_url
    return InjectableLLM(ChatOpenAI(**kwargs), retries=retries)
