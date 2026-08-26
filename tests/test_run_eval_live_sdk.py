"""Regression for the live-target Anthropic SDK call shape.

Weekly eval 2026-08-24 (run 32710690372) died on:

    TypeError: Messages.create() got an unexpected keyword argument 'temperature'

because `pip install anthropic` unpinned pulled SDK 1.0.0 (2026-08-20), which
dropped temperature/top_p/top_k from Messages.create. The HTTP API still
accepts temperature for models that honor it; the 1.0 path is extra_body.

This file never talks to the network. It stubs `anthropic.Anthropic` the way
SDK 1.0's signature behaves, so the weekly live job cannot silently regress
to the 0.x keyword again.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import run_eval  # noqa: E402


class _Sdk1Messages:
    """Mimic anthropic 1.0: reject temperature= as a named argument."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        if "temperature" in kwargs:
            raise TypeError(
                "Messages.create() got an unexpected keyword argument 'temperature'"
            )
        self.calls.append(kwargs)
        block = types.SimpleNamespace(type="text", text="ok")
        return types.SimpleNamespace(content=[block])


class _Sdk1Client:
    def __init__(self) -> None:
        self.messages = _Sdk1Messages()


def test_live_target_survives_sdk_1_without_temperature_kwarg(monkeypatch):
    """A production change that puts temperature= back on messages.create
    must fail this test the same way the 2026-08-24 weekly job failed."""
    client = _Sdk1Client()
    fake_mod = types.SimpleNamespace(Anthropic=lambda: client)
    monkeypatch.setitem(sys.modules, "anthropic", fake_mod)

    target = run_eval.make_live_target()
    out = target("system prompt", "user input")

    assert out == "ok"
    assert len(client.messages.calls) == 1
    call = client.messages.calls[0]
    assert "temperature" not in call
    assert call.get("extra_body", {}).get("temperature") == 0
    assert call["model"] == run_eval.MODEL_ID
    assert call["system"] == "system prompt"
    assert call["messages"] == [{"role": "user", "content": "user input"}]
