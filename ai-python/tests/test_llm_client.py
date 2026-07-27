import asyncio

import pytest

from services.llm_client import InjectableLLM, LLMRequestError


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class FakeError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.response = FakeResponse(status_code)


class FakeLLM:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    async def ainvoke(self, _messages, **_kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def test_success_and_retryable_429():
    fake = FakeLLM([FakeError(429), {"riskItems": []}])
    result = asyncio.run(InjectableLLM(fake, retries=1).ainvoke([]))
    assert result == {"riskItems": []}
    assert fake.calls == 2


@pytest.mark.parametrize("status", [400, 500])
def test_non_retryable_400_and_exhausted_500(status):
    fake = FakeLLM([FakeError(status), FakeError(status)])
    with pytest.raises(LLMRequestError) as error:
        asyncio.run(InjectableLLM(fake, retries=1).ainvoke([]))
    assert error.value.status_code == status
    assert fake.calls == (1 if status == 400 else 2)


def test_timeout_is_retried_then_raises():
    fake = FakeLLM([TimeoutError("deadline"), TimeoutError("deadline")])
    with pytest.raises(LLMRequestError):
        asyncio.run(InjectableLLM(fake, retries=1).ainvoke([]))
    assert fake.calls == 2
