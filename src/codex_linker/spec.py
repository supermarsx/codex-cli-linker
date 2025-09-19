"""Spec choices and defaults (provider ids, ports, labels)."""

from __future__ import annotations
from typing import Dict, List

DEFAULT_LMSTUDIO = "http://localhost:1234/v1"
DEFAULT_OLLAMA = "http://localhost:11434/v1"
DEFAULT_VLLM = "http://localhost:8000/v1"
DEFAULT_TGWUI = "http://localhost:5000/v1"  # Text-Gen-WebUI OpenAI plugin
DEFAULT_TGI_8080 = "http://localhost:8080/v1"  # HF TGI shim
DEFAULT_TGI_3000 = "http://localhost:3000/v1"
DEFAULT_OPENROUTER_LOCAL = "http://localhost:7000/v1"

COMMON_BASE_URLS: List[str] = [
    DEFAULT_LMSTUDIO,
    DEFAULT_OLLAMA,
    DEFAULT_VLLM,
    DEFAULT_TGWUI,
    DEFAULT_TGI_8080,
    DEFAULT_TGI_3000,
    DEFAULT_OPENROUTER_LOCAL,
]

PROVIDER_LABELS: Dict[str, str] = {
    "lmstudio": "LM Studio",
    "ollama": "Ollama",
    "vllm": "vLLM",
    "tgwui": "Text-Gen-WebUI",
    "tgi": "TGI",
    "openrouter": "OpenRouter Local",
}

__all__ = [
    "DEFAULT_LMSTUDIO",
    "DEFAULT_OLLAMA",
    "DEFAULT_VLLM",
    "DEFAULT_TGWUI",
    "DEFAULT_TGI_8080",
    "DEFAULT_TGI_3000",
    "DEFAULT_OPENROUTER_LOCAL",
    "COMMON_BASE_URLS",
    "PROVIDER_LABELS",
]
