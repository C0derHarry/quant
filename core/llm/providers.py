"""Provider-agnostic LLM wrapper.

Exposes:
  PROVIDERS: static config (key URL, instructions, model list with free/paid tier).
  call_llm(provider, model, api_key, system, user_prompt) -> str
  validate_provider_model(provider, model) -> None  (raises ValueError on bad combo)
"""

from __future__ import annotations

PROVIDERS: dict[str, dict] = {
    "google": {
        "label": "Gemini (Google)",
        "key_url": "https://aistudio.google.com/apikey",
        "free_tier_available": True,
        "free_tier_note": (
            "Google AI Studio offers a free tier with no credit card required. "
            "Free-tier RPM varies by model and account; see aistudio.google.com/rate-limit "
            "for your project's actual limits."
        ),
        "instructions": [
            "Go to aistudio.google.com/apikey and sign in with a Google account",
            "Click 'Create API key' and select or create a Google Cloud project",
            "Copy the generated key (starts with AIza)",
            "For free tier, leave the project on the default (no billing)",
            "Paste the key here",
        ],
        "models": [
            {"id": "gemini-2.5-pro",        "label": "Gemini 2.5 Pro (most capable)",   "tier": "paid"},
            {"id": "gemini-2.5-flash",      "label": "Gemini 2.5 Flash (recommended)",  "tier": "free"},
            {"id": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash-Lite (fastest)", "tier": "free"},
            {"id": "gemini-2.0-flash",      "label": "Gemini 2.0 Flash (deprecated)",   "tier": "free"},
        ],
    },
    "anthropic": {
        "label": "Claude (Anthropic)",
        "key_url": "https://console.anthropic.com/settings/keys",
        "free_tier_available": False,
        "free_tier_note": (
            "Anthropic API has no free tier. claude.ai web chat is free but separate from "
            "API access. You must add a payment method and purchase credits."
        ),
        "instructions": [
            "Go to console.anthropic.com and sign in or create an account",
            "Add a payment method under Settings → Billing and purchase credits",
            "Open Settings → API Keys",
            "Click 'Create Key', name it, and copy the value (starts with sk-ant-)",
            "Paste the key here — it will not be shown again on Anthropic's side",
        ],
        "models": [
            {"id": "claude-opus-4-7",   "label": "Opus 4.7 (most capable)",       "tier": "paid"},
            {"id": "claude-sonnet-4-6", "label": "Sonnet 4.6 (balanced)",         "tier": "paid"},
            {"id": "claude-haiku-4-5",  "label": "Haiku 4.5 (fastest, cheapest)", "tier": "paid"},
        ],
    },
    "openai": {
        "label": "ChatGPT (OpenAI)",
        "key_url": "https://platform.openai.com/api-keys",
        "free_tier_available": False,
        "free_tier_note": (
            "OpenAI API has no ongoing free tier. New accounts may receive trial credits "
            "but these expire; sustained use requires pay-as-you-go billing."
        ),
        "instructions": [
            "Go to platform.openai.com and sign in or create an account",
            "Add a payment method under Settings → Billing and add credits",
            "Open platform.openai.com/api-keys",
            "Click 'Create new secret key', name it, and copy the value",
            "Paste the key here — OpenAI will not show it again",
        ],
        "models": [
            {"id": "gpt-4.1",     "label": "GPT-4.1 (recommended)",           "tier": "paid"},
            {"id": "gpt-4o",      "label": "GPT-4o",                          "tier": "paid"},
            {"id": "gpt-4o-mini", "label": "GPT-4o Mini (cheapest non-reasoning)", "tier": "paid"},
            {"id": "o3",          "label": "o3 (reasoning)",                  "tier": "paid"},
            {"id": "o3-mini",     "label": "o3-mini (reasoning, cheaper)",    "tier": "paid"},
        ],
    },
}


def validate_provider_model(provider: str, model: str) -> None:
    cfg = PROVIDERS.get(provider)
    if not cfg:
        raise ValueError(f"Unknown provider: {provider}")
    if model not in {m["id"] for m in cfg["models"]}:
        raise ValueError(f"Model {model!r} is not in the curated list for {provider}")


def _call_google(model: str, api_key: str, system: str, user_prompt: str) -> str:
    from google import genai
    from google.genai import types as genai_types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=genai_types.GenerateContentConfig(system_instruction=system),
    )
    return (response.text or "").strip()


def _call_anthropic(model: str, api_key: str, system: str, user_prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=8192,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    parts = []
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts).strip()


def _call_openai(model: str, api_key: str, system: str, user_prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    is_reasoning = model.startswith("o")
    kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_prompt},
        ],
    }
    if is_reasoning:
        kwargs["max_completion_tokens"] = 8192
    else:
        kwargs["max_tokens"]  = 8192
        kwargs["temperature"] = 0.4

    resp = client.chat.completions.create(**kwargs)
    return (resp.choices[0].message.content or "").strip()


def call_llm(provider: str, model: str, api_key: str, system: str, user_prompt: str) -> str:
    validate_provider_model(provider, model)
    if not api_key:
        raise ValueError("api_key is empty")

    if provider == "google":
        return _call_google(model, api_key, system, user_prompt)
    if provider == "anthropic":
        return _call_anthropic(model, api_key, system, user_prompt)
    if provider == "openai":
        return _call_openai(model, api_key, system, user_prompt)
    raise ValueError(f"Unhandled provider: {provider}")
