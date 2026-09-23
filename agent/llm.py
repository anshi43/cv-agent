"""Ollama client (free, local, offline).

Talks to the Ollama HTTP API at OLLAMA_HOST (default http://localhost:11434).
Everything stays on your machine — no API key, no cloud, no cost.
"""
from __future__ import annotations

import json
import os
import re

import requests

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "600"))


class LLMUnavailable(RuntimeError):
    pass


def available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def chat(system: str, user: str, model: str | None = None,
         temperature: float = 0.3, json_mode: bool = False) -> str:
    """One-shot chat completion against Ollama."""
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": 8192},
    }
    if json_mode:
        payload["format"] = "json"
    try:
        r = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=TIMEOUT)
    except requests.exceptions.RequestException as e:
        raise LLMUnavailable(
            f"Cannot reach Ollama at {OLLAMA_HOST}. Is `ollama serve` running? ({e})"
        ) from e
    if r.status_code == 404:
        raise LLMUnavailable(
            f"Model '{payload['model']}' not found. Run: ollama pull {payload['model']}"
        )
    r.raise_for_status()
    return r.json().get("message", {}).get("content", "").strip()


def chat_json(system: str, user: str, model: str | None = None,
              temperature: float = 0.2) -> dict:
    """Chat expecting a JSON object back; tolerant of code fences / prose."""
    raw = chat(system, user, model=model, temperature=temperature, json_mode=True)
    return _extract_json(raw)


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Model did not return valid JSON:\n{raw[:600]}")
