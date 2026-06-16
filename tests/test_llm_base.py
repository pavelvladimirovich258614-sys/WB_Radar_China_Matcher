from __future__ import annotations

import pytest

from core.llm.base import (
    DEFAULT_JSON_RETRIES,
    LLMAuthError,
    LLMError,
    LLMJSONError,
    LLMProvider,
    LLMRequestError,
    extract_json,
)


class FakeLLMProvider(LLMProvider):
    def __init__(self, replies, *, json_retries=None):
        self._replies = list(replies)
        self._i = 0
        self.calls: list[list[dict]] = []
        self.closed = False
        if json_retries is not None:
            self._json_retries = json_retries

    def complete(self, messages, **kw):
        self.calls.append([dict(m) for m in messages])
        text = self._replies[min(self._i, len(self._replies) - 1)]
        self._i += 1
        return text

    def close(self):
        self.closed = True


class RaisingLLMProvider(LLMProvider):
    def __init__(self, exc):
        self._exc = exc
        self.calls: list[list[dict]] = []

    def complete(self, messages, **kw):
        self.calls.append([dict(m) for m in messages])
        raise self._exc

    def close(self):
        pass


def test_extract_json_raw():
    assert extract_json('{"a":1}') == {"a": 1}


def test_extract_json_fenced_json():
    assert extract_json('```json\n{"a":1}\n```') == {"a": 1}


def test_extract_json_fenced_bare():
    assert extract_json('```\n{"a":1}\n```') == {"a": 1}


def test_extract_json_in_prose():
    assert extract_json('Sure! {"a":1,"b":2} hope that helps') == {"a": 1, "b": 2}


def test_extract_json_nested():
    assert extract_json('{"a":{"b":1}}') == {"a": {"b": 1}}


def test_extract_json_returns_none_on_garbage():
    assert extract_json("not json at all") is None


def test_extract_json_empty():
    assert extract_json("") is None
    assert extract_json("   ") is None


def test_complete_json_parses_on_first_try():
    p = FakeLLMProvider(['{"a":1,"b":2}'])
    assert p.complete_json([{"role": "user", "content": "q"}]) == {"a": 1, "b": 2}
    assert len(p.calls) == 1


def test_complete_json_parses_fenced():
    p = FakeLLMProvider(['```json\n{"a":1}\n```'])
    assert p.complete_json([{"role": "user", "content": "q"}]) == {"a": 1}


def test_complete_json_retries_then_succeeds():
    p = FakeLLMProvider(
        ["garbage", "still bad", '{"ok":true}'], json_retries=3
    )
    assert p.complete_json([{"role": "user", "content": "q"}]) == {"ok": True}
    assert len(p.calls) == 3
    # original call had 1 message; 2nd attempt must have appended a hint
    assert len(p.calls[0]) == 1
    assert len(p.calls[1]) == 2
    assert p.calls[1][-1]["role"] == "user"


def test_complete_json_appends_corrective_hint_only_to_local_copy():
    original = [{"role": "user", "content": "q"}]
    original_snapshot = [dict(m) for m in original]
    p = FakeLLMProvider(["garbage", '{"ok":true}'], json_retries=3)
    p.complete_json(original)
    # caller's list must be unchanged
    assert original == original_snapshot
    assert len(original) == 1


def test_complete_json_raises_after_exhaustion():
    p = FakeLLMProvider(["???"], json_retries=3)
    with pytest.raises(LLMJSONError):
        p.complete_json([{"role": "user", "content": "q"}])
    assert len(p.calls) == 3


def test_complete_json_json_retries_one():
    p = FakeLLMProvider(["garbage"], json_retries=1)
    with pytest.raises(LLMJSONError):
        p.complete_json([{"role": "user", "content": "q"}])
    assert len(p.calls) == 1
    # only one call → no hint appended on the single (exhausted) attempt
    assert len(p.calls[0]) == 1


def test_complete_json_schema_required_ok():
    p = FakeLLMProvider(['{"a":1,"b":2}'])
    assert (
        p.complete_json(
            [{"role": "user", "content": "q"}], schema={"required": ["a", "b"]}
        )
        == {"a": 1, "b": 2}
    )


def test_complete_json_schema_required_missing_retries_and_raises():
    p = FakeLLMProvider(['{"a":1}'], json_retries=3)
    with pytest.raises(LLMJSONError):
        p.complete_json(
            [{"role": "user", "content": "q"}], schema={"required": ["a", "b"]}
        )


def test_complete_json_schema_none_skips_check():
    p = FakeLLMProvider(['{"x":1}'])
    assert (
        p.complete_json([{"role": "user", "content": "q"}], schema=None)
        == {"x": 1}
    )


def test_complete_json_top_level_non_dict_retries_and_raises():
    p = FakeLLMProvider(["[1,2,3]"], json_retries=2)
    with pytest.raises(LLMJSONError):
        p.complete_json([{"role": "user", "content": "q"}])
    assert len(p.calls) == 2


def test_complete_json_propagates_llmrequesterror():
    p = RaisingLLMProvider(LLMRequestError("boom"))
    with pytest.raises(LLMRequestError):
        p.complete_json([{"role": "user", "content": "q"}])
    assert len(p.calls) == 1


def test_complete_json_propagates_llmautherror():
    p = RaisingLLMProvider(LLMAuthError("nope"))
    with pytest.raises(LLMAuthError):
        p.complete_json([{"role": "user", "content": "q"}])
    assert len(p.calls) == 1


def test_llmprovider_abstract_not_instantiable():
    with pytest.raises(TypeError):
        LLMProvider()

    class MissingComplete(LLMProvider):
        def close(self):
            pass

    with pytest.raises(TypeError):
        MissingComplete()


def test_context_manager_calls_close():
    with FakeLLMProvider(["x"]) as p:
        assert not p.closed
    assert p.closed


def test_default_json_retries_constant():
    assert DEFAULT_JSON_RETRIES == 3
