from __future__ import annotations

from pathlib import Path

import httpx

CONFIG_YAML = Path(__file__).resolve().parent.parent / "config.yaml"


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload=None,
        *,
        text=None,
        raise_json: bool = False,
    ):
        self.status_code = status_code
        self._payload = payload
        self._text = text
        self._raise_json = raise_json

    def json(self):
        if self._raise_json or self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self._i = 0
        self.calls = []  # list of (url, headers, payload)
        self.closed = False
        self.raise_on_post = None  # an exception to raise from post(), if set

    def post(self, url, *, headers=None, json=None, timeout=None):
        if self.raise_on_post is not None:
            raise self.raise_on_post
        self.calls.append((url, dict(headers or {}), dict(json or {})))
        resp = self._responses[min(self._i, len(self._responses) - 1)]
        self._i += 1
        return resp

    def close(self):
        self.closed = True


def make_transport_error():
    return httpx.ConnectError("boom")
