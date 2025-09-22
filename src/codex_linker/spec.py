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
DEFAULT_OPENROUTER = "https://openrouter.ai/api/v1"
DEFAULT_ANTHROPIC = "https://api.anthropic.com/v1"
DEFAULT_GROQ = "https://api.groq.com/openai/v1"
DEFAULT_MISTRAL = "https://api.mistral.ai/v1"
DEFAULT_DEEPSEEK = "https://api.deepseek.com/v1"
DEFAULT_OPENAI = "https://api.openai.com/v1"

COMMON_BASE_URLS: List[str] = [
    DEFAULT_LMSTUDIO,
    DEFAULT_OLLAMA,
    DEFAULT_VLLM,
    DEFAULT_TGWUI,
    DEFAULT_TGI_8080,
    DEFAULT_TGI_3000,
    DEFAULT_OPENROUTER_LOCAL,
    DEFAULT_OPENROUTER,
    DEFAULT_ANTHROPIC,
    DEFAULT_GROQ,
    DEFAULT_MISTRAL,
    DEFAULT_DEEPSEEK,
]

PROVIDER_LABELS: Dict[str, str] = {
    "lmstudio": "LM Studio",
    "ollama": "Ollama",
    "vllm": "vLLM",
    "tgwui": "Text-Gen-WebUI",
    "tgi": "TGI",
    "openrouter": "OpenRouter Local",
    "openrouter-remote": "OpenRouter",
    "anthropic": "Anthropic",
    "azure": "Azure OpenAI",
    "groq": "Groq",
    "mistral": "Mistral",
    "deepseek": "DeepSeek",
    "openai": "OpenAI",
}

__all__ = [
    "DEFAULT_LMSTUDIO",
    "DEFAULT_OLLAMA",
    "DEFAULT_VLLM",
    "DEFAULT_TGWUI",
    "DEFAULT_TGI_8080",
    "DEFAULT_TGI_3000",
    "DEFAULT_OPENROUTER_LOCAL",
    "DEFAULT_OPENROUTER",
    "DEFAULT_ANTHROPIC",
    "DEFAULT_GROQ",
    "DEFAULT_MISTRAL",
    "DEFAULT_DEEPSEEK",
    "DEFAULT_OPENAI",
    "COMMON_BASE_URLS",
    "PROVIDER_LABELS",
]
