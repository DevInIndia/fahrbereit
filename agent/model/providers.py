"""The only module in this repository that may import a model vendor.

Every provider returns a `BaseChatModel`, which is what `create_deep_agent` accepts.
Adding a vendor means adding one builder here and one value in `MODEL_PROVIDER`.
"""

from __future__ import annotations

import os

from langchain_core.language_models.chat_models import BaseChatModel


def _require(name: str, provider: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set, and MODEL_PROVIDER={provider} requires it. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


def build_gemini(model: str) -> BaseChatModel:
    """Google AI Studio. Free tier, no card, verified 2026-08-08.

    Note that this model family ignores `temperature` and warns when it is supplied,
    so determinism is not obtainable here. That is one more reason ranking is
    computed in Python rather than asked for.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    _require("GOOGLE_API_KEY", "gemini")
    return ChatGoogleGenerativeAI(model=model)


def build_openai_compatible(model: str, provider: str) -> BaseChatModel:
    """Cerebras and Groq, both free without a card and both OpenAI compatible.

    Not yet exercised. Neither has been verified for tool calling, which is the
    capability this agent lives on, so neither may be relied upon in a demonstration
    until it has been.
    """
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        api_key=_require("OPENAI_COMPATIBLE_API_KEY", provider),
        base_url=_require("OPENAI_COMPATIBLE_BASE_URL", provider),
    )


BUILDERS = {
    "gemini": lambda model: build_gemini(model),
    "cerebras": lambda model: build_openai_compatible(model, "cerebras"),
    "groq": lambda model: build_openai_compatible(model, "groq"),
}
