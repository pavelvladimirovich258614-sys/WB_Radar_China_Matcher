from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_JSON_RETRIES = 3


class LLMError(Exception):
    pass


class LLMAuthError(LLMError):
    pass


class LLMRequestError(LLMError):
    pass


class LLMJSONError(LLMError):
    pass


def extract_json(text: str) -> object | None:
    if not isinstance(text, str) or not text.strip():
        return None

    stripped = text.strip()

    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    fenced = stripped
    if fenced.startswith("```"):
        first_newline = fenced.find("\n")
        if first_newline != -1:
            opening = fenced[:first_newline].strip()
            if opening == "```" or opening == "```json":
                fenced = fenced[first_newline + 1 :]
        if fenced.endswith("```"):
            fenced = fenced[: -3]
        fenced = fenced.strip()
        try:
            return json.loads(fenced)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    first_obj = stripped.find("{")
    last_obj = stripped.rfind("}")
    if first_obj != -1 and last_obj != -1 and last_obj > first_obj:
        try:
            return json.loads(stripped[first_obj : last_obj + 1])
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    first_arr = stripped.find("[")
    last_arr = stripped.rfind("]")
    if first_arr != -1 and last_arr != -1 and last_arr > first_arr:
        try:
            return json.loads(stripped[first_arr : last_arr + 1])
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    return None


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[dict], **kw) -> str:
        ...

    @abstractmethod
    def close(self) -> None:
        ...

    def __enter__(self) -> "LLMProvider":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def complete_json(
        self,
        messages: list[dict],
        schema: dict | None = None,
        *,
        json_retries: int | None = None,
        **kw,
    ) -> dict:
        retries = (
            json_retries
            if json_retries is not None
            else getattr(self, "_json_retries", DEFAULT_JSON_RETRIES)
        )
        retries = max(1, int(retries))

        required: list[str] | None = None
        if schema is not None and isinstance(schema, dict):
            raw_required = schema.get("required")
            if isinstance(raw_required, list):
                required = [str(key) for key in raw_required]

        msgs: list[dict[str, Any]] = list(messages)
        last_text = ""
        for attempt in range(1, retries + 1):
            text = self.complete(msgs, **kw)
            last_text = text
            parsed = extract_json(text)
            if parsed is None or not isinstance(parsed, dict):
                if attempt < retries:
                    msgs.append(
                        {
                            "role": "user",
                            "content": (
                                "Your previous reply was not valid JSON or was not "
                                "a JSON object. Output ONLY the JSON object, no "
                                "surrounding text."
                            ),
                        }
                    )
                continue
            if required and not all(key in parsed for key in required):
                if attempt < retries:
                    msgs.append(
                        {
                            "role": "user",
                            "content": (
                                "Your JSON is missing required keys. Output ONLY "
                                "the JSON object with all required keys."
                            ),
                        }
                    )
                continue
            return parsed

        raise LLMJSONError(
            f"failed to extract valid JSON after {retries} attempts; "
            f"last response: {last_text!r}"
        )


__all__ = [
    "extract_json",
    "LLMProvider",
    "LLMError",
    "LLMAuthError",
    "LLMRequestError",
    "LLMJSONError",
]
